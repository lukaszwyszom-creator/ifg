# IFG DS723+ — Pull Unblock & Cutover Dry-Run

**Data:** 2026-07-06  
**Host:** DS723+ (`ds723:32122`)  
**Repo:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Wykonawca:** Guardian (`SSHExecutor` / `run_remote_readonly`)  
**LIVE cutover:** **nie wykonany** (świadomie poza zakresem)

---

## 1. Podsumowanie

| Etap | Wynik |
|------|--------|
| Remote inspect | ✅ |
| Pre-pull unblock | ✅ |
| `git pull origin production` | ✅ **Fast-forward** |
| `git status` po pull | ✅ tracked clean |
| `ifg cutover run --dry-run` | ✅ **SUCCESS** |
| LIVE cutover | ❌ nie wykonany |

---

## 2. HEAD przed i po pull

| Moment | SHA | Opis |
|--------|-----|------|
| **Przed pull** | `a4056464e1c1f8890e778b9e9c02ec8ba159879d` | Stan DS723+ przed synchronizacją |
| **Po pull** | `0cbaebab2d26854a93eaaed0d77796b508f17ecc` | `0cbaeba` — zgodny z lokalnym `production` (cutover prep + `repo.eol_check`) |
| **Aktualny (weryfikacja)** | `0cbaebab2d26854a93eaaed0d77796b508f17ecc` | Bez zmian od pull |

**Branch:** `production` (przed i po).

---

## 3. Przyczyna blokady pull

`git pull` na DS723+ został zatrzymany przez **lokalnie zmodyfikowany tracked plik**:

```
 M frontend-react/dist/index.html
```

**Interpretacja:** artefakt buildu frontendu (Vite) — plik historycznie śledzony w repo, zmieniony lokalnie na serwerze (hash assetów / mount). Po pull z Mac (`f25c54b`) katalog `frontend-react/dist/` został **usunięty z indeksu Git**; lokalna kopia `index.html` na DS723+ pozostała i blokowała merge.

Dodatkowo na serwerze (nie blokujące pull):

```
?? backups/
?? logs/
```

---

## 4. Sposób odblokowania (Guardian)

**Narzędzie:** `scripts/ifg_guardian/modules/ds723_pull_unblock.py`  
**Transport:** `SSHExecutor` + `DS723Config` (`scripts/ds723.env`)

### Kroki wykonane na DS723+

1. `git status --short` — potwierdzenie blokady (`M frontend-react/dist/index.html`).
2. Weryfikacja: **jedyny** tracked modified to `frontend-react/dist/index.html` (inne `M` brak).
3. **Backup** pliku blokującego:
   - `backups/pull_unblock_20260706_224806/index.html.bak`
   - `.guardian/pull_unblock/index.html.20260706_224806.bak`
4. `git checkout HEAD -- frontend-react/dist/index.html` — **tylko ten plik**.
5. `git fetch origin production` + `git pull origin production`.

**Nie wykonano:** kasowania danych DB, `docker rm`, zmian compose, deployu, LIVE cutover.

---

## 5. Wynik `git pull`

```
Updating a405646..0cbaeba
Fast-forward
```

Pull zakończony **sukcesem** (fast-forward, 51 plików w ramach 9 commitów cutover prep). W tym m.in.:

- `docker/docker-compose.prod.yml` (project `ifg`, external volume/network)
- `scripts/ifg_guardian/` — Preflight Engine, `ifg.container.cutover`, `repo.eol_check`
- dokumentacja runbook + GWO-IFG-002
- usunięcie śledzonych plików `frontend-react/dist/*` z indeksu (pliki na dysku serwera po pull — zgodnie z commitem housekeeping)

---

## 6. Wynik `git status`

### Przed unblock

```
 M frontend-react/dist/index.html
?? backups/
?? logs/
```

### Po restore + pull (stan końcowy)

```
?? backups/
?? logs/
```

**Tracked:** brak `M` / `D` / `A` — **repo nie blokuje operacji Git**.  
**Untracked** `backups/`, `logs/` — katalogi runtime na serwerze; nie wpływają na cutover workflow.

---

## 7. Wynik `ifg cutover run --dry-run`

**Komenda (Mac mini, Guardian → SSH DS723+):**

```bash
PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --dry-run
```

| Pole | Wartość |
|------|---------|
| **Workflow status** | **SUCCESS** |
| **Safety Gate** | **GO** |
| **Health** | **OK** (`Post-health: PASS`) |
| Cutover executed | `False` (dry-run) |
| Guardian verify | **PASS** |
| Backup (simulated) | `backups/pre_ifg_project_DRYRUN.sql` |
| Raport Guardian | `docs/guardian/IFG_CONTAINER_CUTOVER_2026_07_06.md` |

### Stages (skrót z raportu dry-run)

| Stage | Status |
|-------|--------|
| init | pass |
| backup | pass (simulated) |
| git_pull | pass (simulated) |
| compose_config_gate | pass |
| preflight | pass — Safety Gate GO |
| legacy_containers | pass (simulated) |
| cutover_up | pass (simulated) |
| post_health | pass (simulated) |
| guardian_verify | pass (simulated) |
| functional_gate | **warn** — brak `--confirm-functional` |
| cleanup | skip |

**Uwaga:** Preflight zgłosił 14 warningów (nie CRITICAL); Safety Gate pozostał **GO**.

---

## 8. Werdykt LIVE cutover

# LIVE_CUTOVER_NO_GO

| Kryterium | Status |
|-----------|--------|
| DS723+ na `production` @ `0cbaeba` | ✅ |
| Cutover workflow w HEAD | ✅ |
| `git pull` | ✅ |
| Dry-run SUCCESS | ✅ |
| Safety Gate GO | ✅ |
| Health OK | ✅ |
| Checklist funkcjonalna (runbook) | ❌ nie potwierdzona |
| `--confirm-functional` | ❌ brak |
| `--yes` operatora (LIVE) | ❌ nie wydane |
| LIVE cutover wykonany | ❌ świadomie nie |

**Uzasadnienie NO_GO:** ścieżka techniczna (repo + dry-run + gate + health) jest **domknięta audytowo**, ale LIVE cutover wymaga jeszcze:

1. Checklisty funkcjonalnej z `RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md`
2. Jawnej zgody operatora: `ifg cutover run --yes --confirm-functional`
3. Okna maintenance (operator)

Po spełnieniu powyższych warunków werdykt może przejść na **LIVE_CUTOVER_GO** — **nie jest to automatyczne**.

---

## 9. Następny krok operatora (poza Guardianem — tylko po decyzji)

```bash
# 1. Checklist funkcjonalna (runbook)
# 2. LIVE (tylko po GO operatora):
PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --yes --confirm-functional
```

**Nie wykonywać** `--cleanup` przed pełną walidacją produkcji.

---

## 10. Pliki `.md` związane z tą operacją

| Plik | Akcja |
|------|-------|
| `docs/reports/2026-07-06_IFG_DS723_PULL_UNBLOCK_AND_DRY_RUN.md` | **utworzony** (ten raport) |
| `docs/guardian/IFG_CONTAINER_CUTOVER_2026_07_06.md` | wygenerowany przez dry-run (runtime) |

---

*Raport audytowy. LIVE cutover, deploy i dodatkowe zmiany na DS723+ nie wykonano.*
