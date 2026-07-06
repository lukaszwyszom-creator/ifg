# GWO-IFG-002A — Guardian Container Cutover Prep

**Data:** 2026-07-06  
**GWO:** GWO-IFG-002A  
**Runbook:** [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md) (APPROVED)  
**Status:** **WORKFLOW READY** — migracja **nie wykonana**

---

## 1. Czy Guardian potrafi wykonać cutover end-to-end?

**Tak** — po dodaniu workflow **`ifg.container.cutover`** (Profile plugin, bez zmian Guardian Core).

| Zakres runbooka | Guardian |
|-----------------|----------|
| Backup SQL (osobny krok) | ✅ `backup` stage |
| git pull | ✅ `git_pull` stage |
| compose config gate | ✅ `compose_config_gate` stage |
| Preflight + Safety Gate | ✅ `preflight` stage |
| Legacy `docker-*` Exited, nie rm | ✅ `legacy_containers` stage |
| `compose up -d` tylko po GO | ✅ `cutover_up` (po Safety Gate GO) |
| Health + sanity SQL + worker logs | ✅ `post_health` stage |
| Guardian verify | ✅ `guardian_verify` stage (`deploy check`) |
| Checklist funkcjonalna | ⚠️ **Operator** — `--confirm-functional` |
| `docker rm docker-*` | ✅ `cleanup` stage (tylko `--confirm-functional --cleanup`) |
| Rollback | ✅ `ifg cutover rollback --yes` |
| Raport wszystkich kroków | ✅ `summary` + transaction JSON |

**Nie automatyzowane:** testy UI/KSeF (logowanie, lista faktur) — wymagają operatora i flagi `--confirm-functional`.

---

## 2. Mapowanie runbook → workflow

| # | Runbook | Stage ID | Automatyczny |
|---|---------|----------|--------------|
| 1 | Backup | `backup` | ✅ |
| 2 | git pull | `git_pull` | ✅ |
| 3 | compose config | `compose_config_gate` | ✅ |
| 4 | Preflight / Exited | `preflight` + `legacy_containers` | ✅ |
| 5 | Start projektu ifg | `cutover_up` | ✅ (po GO) |
| 6 | Health | `post_health` | ✅ |
| 7 | Guardian verify | `guardian_verify` | ✅ |
| 8 | Test funkcjonalny | `functional_gate` | ⚠️ operator |
| 9 | docker rm | `cleanup` | ✅ (po flagach) |
| 10 | Raport | `summary` | ✅ |

---

## 3. Kroki automatyczne vs operator

### Automatyczne (LIVE z `--yes`)

1. Zapis `backups/pre_cutover_commit.txt`
2. Tymczasowy start `db` (projekt `docker`) jeśli Exited → `pg_dump` → stop `db`
3. `git pull origin production` na DS723+
4. Walidacja `compose config` (`name: ifg`, `docker_postgres_data`, `external`)
5. Preflight Engine + **Safety Gate** (NO_GO = halt przed cutover)
6. Weryfikacja `docker-*` Exited (nie Running)
7. `docker compose up -d` (projekt `ifg`)
8. Health, `pg_isready`, `COUNT(*) FROM invoices`, worker logs, wolumen
9. `guardian deploy check` z Mac mini

### Wymaga operatora (GO/NO-GO)

| Moment | Mechanizm |
|--------|-----------|
| **Start operacji** | `--yes` (LIVE) — jawna zgoda |
| **Safety Gate NO_GO** | Workflow **zatrzymuje się** przed `cutover_up` |
| **Test funkcjonalny IFG** | Operator wykonuje checklist UI; potem `--confirm-functional` |
| **Usunięcie `docker-*`** | `--cleanup` (wymaga `--confirm-functional`) |
| **Rollback** | Osobna komenda `ifg cutover rollback --yes` |

---

## 4. Dokładne komendy uruchomienia

### Faza A — symulacja (bez mutacji, bez DS723+ SSH)

```bash
cd /Users/lukasz/projekty/ifg_standalone
python3 scripts/guardian.py ifg cutover run --dry-run
```

Alternatywa (workflow engine):

```bash
python3 scripts/guardian.py workflow run ifg.container.cutover --dry-run
```

### Faza B — cutover LIVE (bez cleanup)

Wykonuje runbook kroki 1–7. **Nie usuwa** `docker-*`.

```bash
cd /Users/lukasz/projekty/ifg_standalone
python3 scripts/guardian.py ifg cutover run --yes
```

### Faza C — po testach funkcjonalnych (cleanup)

Operator wykonuje checklist z runbooka (login, faktury, KSeF), potem:

```bash
python3 scripts/guardian.py ifg cutover run --yes --confirm-functional --cleanup
```

Uwaga: ponowne uruchomienie wykona backup i pull od nowa. **Zalecane:** jeśli cutover z Fazy B już OK, cleanup można wykonać ręcznie jednym poleceniem z runbooka — lub uruchomić workflow tylko gdy stack jeszcze nie był migrowany. W praktyce po Fazie B wystarczy:

```bash
ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && sudo docker rm docker-api-1 docker-worker-1 docker-db-1'
```

…po `--confirm-functional` w procesie operatora. Workflow `--cleanup` jest dla pełnej ścieżki jednym przebiegiem.

### Rollback

```bash
python3 scripts/guardian.py ifg cutover rollback --yes
```

Dry-run rollback:

```bash
python3 scripts/guardian.py ifg cutover rollback --dry-run
```

Ręczny rollback (z runbooka):

```bash
ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && \
  sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop && \
  git checkout $(cat backups/pre_cutover_commit.txt) -- docker/docker-compose.prod.yml && \
  sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d'
```

---

## 5. Raporty i artefakty

| Artefakt | Lokalizacja |
|----------|-------------|
| Cutover report | `docs/guardian/IFG_CONTAINER_CUTOVER_*.md` |
| Preflight report | `docs/guardian/CUTOVER_PRECHECK_*.md` |
| Transaction JSON | `.guardian/workflows/<workflow_id>/transaction.json` |
| Latest transaction | `.guardian/latest/ifg_container_cutover.json` |

---

## 6. Weryfikacja lokalna (prep)

```bash
.venv/bin/pytest tests/unit/test_guardian_container_cutover_workflow.py -q -p no:cov
python3 scripts/guardian.py ifg cutover run --dry-run
```

Wynik dry-run (2026-07-06): **SUCCESS**, Safety Gate GO (remote skipped), raport zapisany.

**Migracja produkcyjna nie wykonana** w tej sesji.

---

## 7. Lista zmienionych / dodanych plików

### Nowe

| Plik |
|------|
| `scripts/ifg_guardian/plugins/ifg/container_cutover/__init__.py` |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/models.py` |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/remote.py` |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/service.py` |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/stages.py` |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/workflow.py` |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/report.py` |
| `scripts/ifg_guardian/modules/ifg_container_cutover.py` |
| `tests/unit/test_guardian_container_cutover_workflow.py` |
| `docs/reports/GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md` |

### Zmodyfikowane

| Plik | Zmiana |
|------|--------|
| `scripts/ifg_guardian/plugins/ifg/plugin.py` | Rejestracja workflow |
| `scripts/ifg_guardian/cli.py` | `ifg cutover run` / `rollback` |
| `scripts/ifg_guardian/core/workflow/transaction.py` | Pole `cutover_run` |
| `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` | Sekcja Guardian |

### Bez zmian

- Guardian Core (`/Users/lukasz/projekty/guardian`)
- `docker/docker-compose.prod.yml`
- DS723+ (brak połączenia / mutacji)

---

## 8. Końcowa rekomendacja

| Aspekt | Werdykt |
|--------|---------|
| Workflow end-to-end | ✅ Gotowy |
| Zgodność z runbookiem | ✅ (UI test = operator) |
| Preflight + Safety Gate | ✅ Obowiązkowe przed cutover |
| Rollback | ✅ Komenda + raport |
| Gotowość do migracji | ✅ Po `git push` compose prep + operator `--yes` |

**Procedura operatora:**

1. `ifg cutover run --dry-run` — weryfikacja planu
2. `ifg cutover run --yes` — cutover LIVE
3. Checklist funkcjonalna (ręcznie)
4. Cleanup legacy kontenerów (`--confirm-functional --cleanup` lub ręczny `docker rm` z runbooka)
5. Container Manager UI → Project `ifg`

**NO-GO:** Safety Gate FAIL, compose config gate FAIL, backup FAIL, health FAIL — użyj `ifg cutover rollback --yes`.

---

*Prep zakończony. Brak operacji na DS723+.*
