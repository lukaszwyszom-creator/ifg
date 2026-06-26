# Guardian IFG Profile — M3 Mutating Commands

**Status:** M3 complete  
**Date:** 2026-06-26  
**Profile version:** `0.4.0-m3`

---

## Nowe workflow

| ID | Etapy | Mutujące |
|----|-------|----------|
| `ifg.deploy.run` | init → repository → git_validation → execution → deploy_report | tak |
| `ifg.prod.recover` | init → repository_validation → docker_status → restart_services → health → worker_verification → ksef_verification → recovery_report | tak |

### ifg.deploy.run — pipeline w execution

1. git validation  
2. backup database (PostgreSQL pg_dump)  
3. alembic upgrade  
4. frontend build  
5. docker build  
6. container restart  
7. health verification  
8. smoke tests  

### ifg.prod.recover

1. Repository validation (remote git)  
2. Docker status (compose ps)  
3. Restart services (`up -d db`, `up -d api worker`)  
4. Health (`/health`)  
5. Worker verification  
6. KSeF verification (openapi)  
7. Recovery report  

---

## Nowe komendy

| Komenda | Flagi | Opis |
|---------|-------|------|
| `ifg deploy run` | `--dry-run`, `--yes` | Pełny pipeline deployu |
| `ifg prod recover` | `--dry-run`, `--yes` | Recovery produkcji DS723+ |

Bez `--yes` (i bez `--dry-run`) → **blokada** (exit 2, core guard).

---

## Bezpieczeństwo

- Wszystkie komendy mutujące: `mutating=True`, `supports_dry_run=True`
- Core `ensure_mutating_allowed`: LIVE wymaga `--yes`
- `--dry-run`: symulacja przez `profiles/ifg/infra/exec.py` (brak subprocess mutacji)
- Rollback: `rollback_available=True` w stanie deploy (hook przygotowany, **bez auto-rollback**)
- Health/smoke fail → workflow halt + raport (bez automatycznego rollbacku)

---

## Raporty

Zapis do `docs/reports/`:

- `guardian_deploy_YYYYMMDD_HHMM.md`
- `guardian_recover_YYYYMMDD_HHMM.md`

Helper: `profiles/ifg/lib/deploy_reporting.py`

---

## Nowe moduły (profil IFG)

```
profiles/ifg/
  deploy/          models, pipeline, stages, runner, report, service
  recover/         models, stages, runner, report, service
  infra/exec.py    run_local, run_remote (dry-run aware)
  lib/deploy_reporting.py
  commands/deploy_run.py
  commands/prod_recover.py
  workflows/deploy_run.py
  workflows/prod_recover.py
```

**Core platformy:** bez zmian architektonicznych.

---

## Nowe testy

| Plik | Zakres |
|------|--------|
| `test_deploy_run.py` | workflow, pipeline, CLI, halt |
| `test_prod_recover.py` | workflow, runner, CLI, live mock |
| `test_ifg_mutating.py` | guards, mutating flags |
| `test_m3_coverage.py` | pipeline details, serialization |

---

## Wyniki testów (2026-06-26)

| Pakiet | Wynik |
|--------|-------|
| `tests/guardian_platform/` | **223 passed** |
| `tests/unit/ -k guardian` (legacy) | **104 passed** |
| **Łącznie Guardian** | **327** |

### CLI acceptance

| Komenda | Wynik |
|---------|-------|
| `ifg deploy run --dry-run` | ✅ DRY-RUN COMPLETE + raport |
| `ifg deploy run` (bez --yes) | ✅ exit 2, requires --yes |
| `ifg prod recover --dry-run` | ✅ DRY-RUN COMPLETE + raport |
| `ifg prod recover` (bez --yes) | ✅ exit 2 |

---

## Nadal w starym Guardianie

| Element | Lokalizacja |
|---------|-------------|
| Entry point CLI | `scripts/guardian.py`, `scripts/guardian2.py` |
| Runtime + pluginy | `scripts/ifg_guardian/` |
| Release plan workflow | `ifg.release.plan` (deploy run M3 nie wymaga dependency) |
| Deploy executors (SSH/Docker szczegółowe) | `ifg_guardian/core/workflow/executors/` |
| `recover-prod` oryginał | `scripts/guardian2.py` |
| Testy legacy | `tests/unit/test_guardian_*.py` (104, nietknięte) |

Profil IFG M3 **nie importuje** `ifg_guardian.modules.*`.

---

## Gotowość do M4

**Tak — z zastrzeżeniami:**

- M4: przepięcie entry pointów (`guardian.py` → platform), deprecacja starego runtime
- M4+: auto-rollback wykorzystujący `rollback_available` + `RollbackPoint`
- M4+: integracja z `ifg.release.plan` (opcjonalna dependency workflow)
- M4+: granularne komendy (`restart api`, `backup db`) jako osobne CLI

**Werdykt: GUARDIAN_IFG_PROFILE_M3_MUTATING — ACCEPTED**
