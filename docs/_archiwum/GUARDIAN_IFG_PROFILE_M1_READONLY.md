# Guardian IFG Profile — M1 Read-Only

**Status:** M1 complete  
**Date:** 2026-06-26  
**Entry point:** `python3 -m scripts.guardian_platform ifg …`

---

## Cel M1

Zastąpienie `profiles/ifg_scaffold` realnym profilem IFG z komendami **tylko read-only**, bez mutacji, deployu ani zmian DB. Stary Guardian (`scripts/guardian.py`, `scripts/guardian2.py`, `scripts/ifg_guardian/`) pozostaje nietknięty.

---

## Co zostało przeniesione

### Struktura profilu

```
scripts/guardian_platform/profiles/ifg/
  profile.py              # rejestracja komend
  config/defaults.py      # stałe IFG (DS723, ścieżki, markery KSeF)
  infra/
    ssh.py                # SSH + remote git
    compose.py            # docker compose ps / health
    git.py                # lokalny git
  checks/
    frontend.py           # dist freshness, KSeF connect fix
  commands/
    doctor.py             # bridge → ifg_guardian.modules.ifg_doctor
    deploy_check.py       # port z ifg_guardian.modules.deploy (read-only)
    frontend_check.py     # port z ifg_guardian.modules.frontend
    ksef_check.py         # port z ifg_guardian.modules.ksef
    prod_health.py        # port z ifg_guardian.modules.production (read-only)
  repo_audit/             # placeholder M2
  workflows/              # placeholder M2
```

### Komendy

| Komenda | Implementacja M1 | Źródło |
|---------|------------------|--------|
| `ifg ping` | natywna | heartbeat profilu |
| `ifg doctor` | **bridge** | `ifg_guardian.modules.ifg_doctor.run_ifg_doctor` |
| `ifg deploy check` | **port** | logika z `ifg_guardian.modules.deploy` |
| `ifg frontend check` | **port** | logika z `ifg_guardian.modules.frontend` |
| `ifg ksef check` | **port** | logika z `ifg_guardian.modules.ksef` |
| `ifg prod health` | **port** | read-only część `ifg_guardian.modules.production` |
| `ifg repo audit` | **bridge** | `ifg_guardian.modules.repo_audit.run_repo_audit` |

### Kompatybilność `ifg_scaffold`

- `profiles/ifg_scaffold/profile.py` → alias `IFGScaffoldProfile = IFGProfile`
- Loader mapuje `ifg_scaffold` → profil `ifg` (deduplikacja po `profile.id`)
- `.guardian.yml`: aktywny profil `ifg` (zamiast `ifg_scaffold`)

### Core neutrality

Po M1 w `scripts/guardian_platform/core/`:

```
grep -ri "KSeF"           → 0
grep -ri "ds723"          → 0
grep -ri "frontend-react" → 0
```

Jedyna zmiana w core: `loader.py` — rejestracja profilu `ifg` + alias/deduplikacja `ifg_scaffold`.

---

## Działające komendy IFG

```bash
python3 -m scripts.guardian_platform ifg ping
python3 -m scripts.guardian_platform ifg doctor
python3 -m scripts.guardian_platform ifg deploy check
python3 -m scripts.guardian_platform ifg frontend check
python3 -m scripts.guardian_platform ifg ksef check
python3 -m scripts.guardian_platform ifg prod health
python3 -m scripts.guardian_platform ifg repo audit
```

---

## Co nadal zostaje w starym Guardianie

| Obszar | Lokalizacja |
|--------|-------------|
| CLI główne | `scripts/guardian.py`, `scripts/guardian2.py` |
| Cały runtime IFG | `scripts/ifg_guardian/` |
| Workflow engine, pluginy, executory deploy | `ifg_guardian/core/`, `ifg_guardian/plugins/` |
| **Mutacje** | `ifg deploy run`, `ifg prod recover`, git restore, DB, alembic upgrade |
| Doctor/repo audit workflow definitions | `ifg_guardian/plugins/ifg/doctor/`, `ifg_guardian/core/repo_audit/` |

M1 **nie usuwa** starych entry pointów — oba systemy współistnieją.

---

## Wyniki testów (2026-06-26)

| Test | Wynik |
|------|-------|
| `python3 -m scripts.guardian_platform plugin list` | ✅ OK — profile: core, ifg (0.2.0-m1), psag |
| `ifg doctor` | ✅ działa (exit 1 — BLOCKED: brak alembic lokalnie, oczekiwane) |
| `ifg deploy check` | ✅ działa (exit 1 — commit różny, dist lokalnie nieaktualny) |
| `ifg frontend check` | ✅ działa (exit 1 — dist wymaga rebuild) |
| `ifg ksef check` | ✅ działa (exit 1 — dist wymaga rebuild) |
| `ifg prod health` | ✅ OK (exit 0 — api/worker/db + /health) |
| `ifg repo audit` | ✅ działa (exit 1 — WARNING, HIGH risk) |
| `psag ping` | ✅ OK |
| `python3 scripts/guardian.py doctor` | ✅ działa (legacy nietknięty) |
| `.venv/bin/python -m pytest tests/unit/test_guardian_*.py` | ✅ **104 passed** |
| Core grep neutrality | ✅ 0 / 0 / 0 |

> Uwaga: exit code ≠ 1 oznacza błąd środowiska (stary dist, różne commity), nie błąd platformy.

---

## Ryzyka

1. **Bridge doctor/repo audit** — M1 deleguje do `ifg_guardian`; pełna migracja workflow do profilu dopiero w M2+.
2. **Duplikacja logiki** — deploy/frontend/ksef/prod health skopiowane do profilu; przy zmianach w starym Guardianie trzeba synchronizować ręcznie do pełnej migracji.
3. **SSH zależność** — deploy check / prod health wymagają dostępu do `ds723`; bez SSH zwracają czytelny błąd.
4. **Dwa entry pointy** — użytkownicy mogą mylić `guardian.py` vs `guardian_platform ifg`; dokumentacja i deprecation dopiero później.
5. **`ifg_scaffold` alias** — tymczasowy; usunąć gdy wszyscy przejdą na `ifg` w `.guardian.yml`.

---

## Następny etap (M2+)

**Nie w M1 — dopiero później:**

- `ifg deploy run` (dry-run + LIVE)
- `ifg prod recover`
- migracja workflow doctor/repo audit z bridge → natywne `profiles/ifg/workflows/`
- rozszerzenia `profiles/ifg/repo_audit/`
- mutating guards, rollback, DB/alembic
- deprecacja `scripts/guardian.py` / `ifg_guardian/` (po pełnej migracji)

---

## Akceptacja M1

| # | Kryterium | Status |
|---|-----------|--------|
| 1 | Profil `ifg/` z read-only komendami | ✅ |
| 2 | `ifg_scaffold` jako alias (bez usuwania) | ✅ |
| 3 | Brak mutacji / deploy run / recover | ✅ |
| 4 | Stary Guardian nietknięty | ✅ |
| 5 | Entry point `python3 -m scripts.guardian_platform ifg …` | ✅ |
| 6 | Core neutralny (grep 0) | ✅ |
| 7 | Testy legacy 104 passed | ✅ |

**Werdykt: GUARDIAN_IFG_PROFILE_M1_READONLY — ACCEPTED**
