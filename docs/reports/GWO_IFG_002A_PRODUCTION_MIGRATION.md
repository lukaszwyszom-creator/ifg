# GWO-IFG-002A — Produkcja: migracja IFG → Container Manager Project

| Pole | Wartość |
|------|---------|
| **ID** | GWO-IFG-002A |
| **Type** | Production Migration |
| **Risk** | HIGH |
| **Rollback** | REQUIRED |
| **Preflight** | REQUIRED |
| **Production Validation** | REQUIRED |
| **Status** | **PLANNING** |
| **Data wykonania** | 2026-07-06 (Etap 0–1 + diagnostyka; Etap 2–5 **nie wykonane**) |
| **Operator** | Guardian (Mac mini) → DS723+ |
| **Architektura** | Guardian v1.0 — ComposeBackend (bez SynologyProjectBackend) |

Powiązane dokumenty:
- [GWO-IFG-002_PROJECT_MIGRATION_PLAN.md](./GWO_IFG_002_PROJECT_MIGRATION_PLAN.md)
- [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md)
- [GWO_G003A_PREFLIGHT_ENGINE.md](./GWO_G003A_PREFLIGHT_ENGINE.md)
- Preflight artifact: [PRECHECK_REPORT_2026_07_05.md](../guardian/PRECHECK_REPORT_2026_07_05.md)

---

## Streszczenie wykonawcze

| Aspekt | Wynik |
|--------|-------|
| Migracja compose (`name: ifg`) | **NIE wykonana** |
| Projekt IFG w Container Manager | **NIE istnieje** |
| Stack produkcyjny | **Zatrzymany** (projekt `docker`, kontenery Exited) |
| Preflight (dry-run) | **GO** (6 ostrzeżeń) |
| Preflight (LIVE — prognoza) | **NO_GO** (brak backupu) |
| Guardian deploy --dry-run | **PASS** (workflow SUCCESS; Doctor BLOCKED = WARN) |
| Guardian verify (doctor) | **FAIL** (BLOCKED — brak lokalnego `.env`, dirty tree) |
| **Decyzja końcowa** | **NOT PRODUCTION PROVEN** |
| **Status GWO** | **PLANNING** (nie COMPLETED) |

> **Wniosek:** Procedura migracji została **rozpoczęta i udokumentowana**, ale **zatrzymana przed Etapem 2** zgodnie z Safety Gate i brakiem warunków wstępnych. **Nie wykonano** `compose up` z nową nazwą projektu.

---

## Cel biznesowy

Po zakończeniu (docelowo):

```
Container Manager → Projekt → IFG
```

— jedyny sposób zarządzania produkcją. **Obecnie:** projekt Compose = `docker`, luźne kontenery `docker-*-1`, **brak** projektu `ifg`.

---

## Etap 0 — Weryfikacja stanu wyjściowego

**Wykonano:** 2026-07-06, SSH read-only na DS723+ + lokalne repo.

### 0.1 Commit i branch

| Check | Mac mini (lokalnie) | DS723+ (prod) | Wynik |
|-------|----------------------|---------------|-------|
| Branch | `production` | `production` | **PASS** |
| Commit | `a405646` | `a405646` | **PASS** |
| Git clean | **50+ niezcommitowanych zmian** | n/d (tylko tracked) | **FAIL** (lokalnie) |

### 0.2 Compose

```bash
# DS723+ 2026-07-06
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config | grep -E '^name:|^    name:'
```

| Pole | Wartość | Wynik |
|------|---------|-------|
| `name:` (projekt) | **`docker`** | **PASS** (stan przed migracją) |
| Sieć | `docker_ifg_prod` | **PASS** |
| Wolumen DB | `docker_postgres_data` | **PASS** |
| `name: ifg` w pliku compose | **brak** (repo lokalne i DS723+) | **FAIL** (wymagane przed migracją) |

### 0.3 Volume PostgreSQL

```
Name=docker_postgres_data
Mountpoint=/volume1/@docker/volumes/docker_postgres_data/_data
```

| Check | Wynik |
|-------|-------|
| Wolumen istnieje | **PASS** |
| Wolumen nie dotknięty | **PASS** |

### 0.4 Network

| Nazwa | Wynik |
|-------|-------|
| `docker_ifg_prod` | **PASS** |

### 0.5 Kontenery

| Kontener | Status (2026-07-06 ~22:21 UTC+2) | Wynik |
|----------|----------------------------------|-------|
| `docker-api-1` | Exited (137) ~22 h temu | **PASS** (zatrzymany — okno migracji) |
| `docker-worker-1` | Exited (137) | **PASS** |
| `docker-db-1` | Exited (0) | **PASS** |
| `ifg-*` | brak | **PASS** (brak równoległego stacku) |

### 0.6 Backup

```
ls /volume1/docker/ifg_v2/backups → NO_BACKUP_DIR
```

| Check | Wynik |
|-------|-------|
| Katalog backupu | **FAIL** |
| Artefakt backupu | **FAIL** |

### 0.7 Health

```
curl http://127.0.0.1:8000/health → HEALTH_UNREACHABLE
```

| Check | Wynik |
|-------|-------|
| Health API | **FAIL** (stack zatrzymany — oczekiwane) |

### 0.8 Dysk

| Wolne | Wynik |
|-------|-------|
| 71 GB (27% użycia) | **PASS** |

### Etap 0 — podsumowanie

| Obszar | Wynik |
|--------|-------|
| Commit/branch DS723+ | **PASS** |
| Compose (pre-migration) | **PASS** |
| Volume DB | **PASS** |
| Backup | **FAIL** |
| Health | **FAIL** (stack down) |
| Compose diff `name: ifg` | **FAIL** (nie wdrożony) |

**Etap 0:** **FAIL** — brak backupu i brak diff compose blokują migrację.

---

## Etap 1 — Guardian Preflight

**Wykonano:** 2026-07-06

```bash
cd /Users/lukasz/projekty/ifg_standalone
PYTHONPATH=scripts python3.11 -m ifg_guardian ifg deploy run --dry-run
```

### Wynik Safety Gate

| Tryb | Decision | Raport |
|------|----------|--------|
| DRY_RUN | **GO** | [PRECHECK_REPORT_2026_07_05.md](../guardian/PRECHECK_REPORT_2026_07_05.md) |
| LIVE (prognoza) | **NO_GO** | Backup → FAIL na LIVE |

### Tabela preflight (skrót)

| Status | Check | Opis |
|--------|-------|------|
| PASS | Repo accessible | OK |
| PASS | Compose file exists | OK |
| WARNING | Local .env | brak lokalnie |
| PASS | Branch | production |
| WARNING | Git clean | 50 zmian |
| PASS | SSH | ds723 OK |
| PASS | Docker / Compose | 24.0.2 / 2.20.1 |
| PASS | Compose config valid | OK |
| PASS | Compose validation | project=docker, volume=docker_postgres_data |
| PASS | Remote .env | OK na DS723+ |
| PASS | PostgreSQL volume | docker_postgres_data |
| WARNING | External volume pin | pre-migration — OK |
| **WARNING** | **Backup exists** | **brak backupu** |
| WARNING | Backup freshness | brak |
| WARNING | Health | unreachable |
| PASS | Disk / permissions | OK |

**Podsumowanie:** 12 PASS, 6 WARNING, 0 FAIL (dry-run).

### Decyzja Etap 1

| Tryb migracji | Safety Gate | Działanie |
|---------------|-------------|-----------|
| Dry-run deploy | GO | Dozwolony test pipeline |
| **LIVE migracja** | **NO_GO** (backup) | **STOP — procedura zatrzymana** |

**Etap 1:** **FAIL** dla LIVE migracji (backup). Zgodnie z wymaganiem: *„Jeżeli jakikolwiek punkt zwróci NO_GO — cała procedura zostaje zatrzymana.”*

---

## Etap 2 — Migracja compose (IFG_CONTAINER_MANAGER_MIGRATION.md)

**Status:** **NIE WYKONANY**

### Warunki wstępne (nie spełnione)

| # | Warunek | Stan |
|---|---------|------|
| 1 | Merge `name: ifg` + `external: true` na `production` | **NIE** |
| 2 | Backup wolumenu DB na DS723+ | **NIE** |
| 3 | Safety Gate GO (LIVE) | **NIE** |
| 4 | Akceptacja operatora | **NIE** (ten GWO) |

### Procedura (do wykonania po GO)

Zgodnie z [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md) — **bez zmian**:

1. `git pull origin production` (po merge compose diff)
2. **Gate:** `compose config | grep docker_postgres_data` — **nie** `ifg_postgres_data`
3. `compose up -d` z repo root
4. Weryfikacja health + COUNT invoices
5. Usunięcie starych kontenerów `docker-*-1` (tylko kontenery)
6. Container Manager → Projekt **`ifg`**

**Etap 2:** **SKIP** (zatrzymany przez Etap 1).

---

## Etap 3 — Walidacja post-migracyjna

**Status:** **NIE WYKONANY** (brak migracji)

| Check | Oczekiwany wynik | Wynik |
|-------|------------------|-------|
| Health | JSON `"status":"ok"` | **SKIP** |
| API | Up, healthy | **SKIP** |
| Worker | Up, bez crash loop | **SKIP** |
| DB | pg_isready + COUNT > 0 | **SKIP** |
| Frontend | dist w kontenerze api | **SKIP** |
| KSeF endpoint | `/api/v1/ksef/status` (po sesji) | **SKIP** |
| Docker status | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` Up | **SKIP** |
| Project status | CM → Projekt **ifg** | **SKIP** |

**Etap 3:** **SKIP**

---

## Etap 4 — Guardian deploy --dry-run i verify

**Wykonano częściowo:** 2026-07-06

### 4.1 deploy --dry-run

```bash
python3.11 -m ifg_guardian ifg deploy run --dry-run
```

| Pole | Wartość |
|------|---------|
| Workflow ID | `2026-07-05T222137Z_ifg_deploy_run` |
| Outcome | **SUCCESS** |
| Preflight stage | **PASS** (Safety Gate GO) |
| Blockers | 2 (Doctor BLOCKED — WARN w dry-run) |
| Simulated steps | 7/7 |
| Raport | `docs/guardian/IFG_DEPLOY_RUN_2026_07_05.md` |

| Check | Wynik |
|-------|-------|
| deploy --dry-run | **PASS** |

### 4.2 verify (ifg doctor --dry-run)

```bash
python3.11 -m ifg_guardian ifg doctor --dry-run
```

| Check | Wynik |
|-------|-------|
| Doctor overall | **BLOCKED** |
| Compose config (lokalnie) | **FAIL** — brak `.env.production` lokalnie |
| Remote containers | skipped dry-run |

| Check | Wynik |
|-------|-------|
| Guardian verify | **FAIL** |

**Etap 4:** **FAIL** (verify BLOCKED).

---

## Etap 5 — Validation checklist

| # | Punkt | PASS / FAIL | Uwagi |
|---|-------|-------------|-------|
| 1 | IFG widoczny jako Project w CM | **FAIL** | Projekt nadal `docker` / brak `ifg` |
| 2 | Nie istnieje drugi stack | **PASS** | Brak `ifg-*`; tylko zatrzymane `docker-*` |
| 3 | API odpowiada | **FAIL** | Stack zatrzymany |
| 4 | Worker działa | **FAIL** | Stack zatrzymany |
| 5 | DB działa | **FAIL** | Stack zatrzymany |
| 6 | Frontend działa | **FAIL** | Stack zatrzymany |
| 7 | Health OK | **FAIL** | HEALTH_UNREACHABLE |
| 8 | Guardian Preflight PASS (LIVE) | **FAIL** | NO_GO — brak backupu |
| 9 | Guardian verify PASS | **FAIL** | Doctor BLOCKED |
| 10 | Guardian deploy --dry-run PASS | **PASS** | Workflow SUCCESS |
| 11 | Rollback zweryfikowany | **FAIL** | Nie wykonano próby rollback (brak migracji) |

**Etap 5:** **FAIL** (9/11 FAIL)

---

## Production Proven — checklist

| Kryterium | Spełnione |
|-----------|-----------|
| □ IFG widoczny jako Project | **NIE** |
| □ Nie istnieje drugi stack | **TAK** (pre-migration) |
| □ API odpowiada | **NIE** |
| □ Worker działa | **NIE** |
| □ DB działa | **NIE** |
| □ Frontend działa | **NIE** |
| □ Health OK | **NIE** |
| □ Guardian Preflight PASS | **NIE** (LIVE) |
| □ Guardian verify PASS | **NIE** |
| □ Guardian deploy --dry-run PASS | **TAK** |
| □ Rollback zweryfikowany | **NIE** |

**Production Proven:** **0 / 11** (z czego 1 częściowo spełniony pre-migration)

---

## Rollback — procedura (z każdego etapu)

Dane produkcyjne: wolumen **`docker_postgres_data`** — **nigdy nie usuwać**.

### Z Etapu 0 (przed migracją)

**Akcja:** Nic nie zmieniać. Stack już zatrzymany.

**Rollback:** N/D — stan wyjściowy zachowany.

### Z Etapu 1 (preflight tylko odczyt)

**Akcja:** Brak mutacji.

**Rollback:** N/D.

### Z Etapu 2 (po `git pull` + `compose up` z `name: ifg`)

**Jeśli gate FAIL lub zły wolumen:**

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop
git checkout <commit_przed_migracja> -- docker/docker-compose.prod.yml
sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d
curl -fsS http://127.0.0.1:8000/health
# COUNT invoices w DB
```

**Jeśli utworzono `ifg_postgres_data` przez pomyłkę:**

1. **STOP** — nie uruchamiać aplikacji na tym wolumenie
2. Zweryfikować `docker_postgres_data` nienaruszony
3. Usunąć pusty `ifg_postgres_data` dopiero po potwierdzeniu
4. Przywrócić compose z pinem `external: true`

### Z Etapu 3 (po walidacji FAIL)

Ten sam rollback co Etap 2 — powrót do projektu `docker`.

### Przywrócenie z backupu (ostateczność)

```bash
BACKUP_DIR="/volume1/docker/ifg_v2/backups/pre-ifg-migration-YYYYMMDD"
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop db
sudo tar xzf "$BACKUP_DIR/docker_postgres_data.tgz" \
  -C /volume1/@docker/volumes/docker_postgres_data
sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d db
```

**Rollback zweryfikowany w tej sesji:** **NIE** (dry-run procedury tylko).

---

## Zidentyfikowane problemy

| # | Problem | Poważność | Działanie |
|---|---------|-----------|-----------|
| P1 | Brak katalogu backupu na DS723+ | **Krytyczne** | Utworzyć backup przed Etapem 2 (GWO-IFG-002 §4 Faza 1) |
| P2 | Brak diff compose (`name: ifg`) w `production` | **Krytyczne** | Commit + merge Wariant A |
| P3 | Stack produkcyjny zatrzymany | Wysokie | Podnieść po migracji lub rollback do `docker` |
| P4 | Lokalne niezcommitowane zmiany (50+) | Średnie | Commit/stash przed deploy LIVE |
| P5 | Doctor BLOCKED (dist stale, brak lokalnego .env) | Średnie | `npm run build` + sync przed deploy |
| P6 | KSeF sesja | Info | Wymaga ponownego logowania po restarcie |

---

## Kolejność działań do Production Proven

1. **Backup** — `tar` wolumenu `docker_postgres_data` → `/volume1/docker/ifg_v2/backups/`
2. **Commit compose** — `name: ifg` + `external: true` (Wariant A) → `production`
3. **Preflight LIVE** — oczekiwany **GO** po backupie
4. **Etap 2** — migracja według IFG_CONTAINER_MANAGER_MIGRATION.md
5. **Etap 3** — health, API, worker, DB, frontend, KSeF, CM Project
6. **Etap 4** — `ifg doctor` PASS + `deploy --dry-run` PASS
7. **Rollback drill** — symulacja na zatrzymanym stacku (optional)
8. **Aktualizacja tego GWO** → Status **COMPLETED**, decyzja **PRODUCTION PROVEN**

---

## Decyzja końcowa

### **NOT PRODUCTION PROVEN**

Migracja Container Manager Project **nie została wykonana**. Procedura zatrzymana na Safety Gate (brak backupu LIVE) i braku diff compose w repozytorium produkcyjnym.

### Status GWO

| Status | Uzasadnienie |
|--------|--------------|
| **PLANNING** | Kryteria Production Proven **nie spełnione** |
| ~~COMPLETED~~ | **Niedozwolone** — brak projektu IFG, brak działającego stacku |

---

## Załączniki

| Artefakt | Ścieżka |
|----------|---------|
| Preflight report | [docs/guardian/PRECHECK_REPORT_2026_07_05.md](../guardian/PRECHECK_REPORT_2026_07_05.md) |
| Deploy dry-run report | `docs/guardian/IFG_DEPLOY_RUN_2026_07_05.md` |
| Doctor report | `docs/guardian/IFG_DOCTOR_2026_07_05.md` |
| Deploy transaction | `.guardian/workflows/2026-07-05T222137Z_ifg_deploy_run/transaction.json` |

---

**Koniec raportu GWO-IFG-002A.**  
Następny krok: backup DS723+ → merge compose → ponowny preflight LIVE → wznowienie Etapu 2.
