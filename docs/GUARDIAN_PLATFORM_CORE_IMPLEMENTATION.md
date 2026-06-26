# Guardian Platform Core — Implementation Report

**Data:** 2026-06-26  
**Status:** Etap zamknięty — neutralna platforma gotowa  
**Następny etap:** [GUARDIAN_IFG_PROFILE_IMPLEMENTATION.md](GUARDIAN_IFG_PROFILE_IMPLEMENTATION.md) *(profil IFG — nie rozpoczęty)*

---

## Cel etapu

Zbudować **neutralną Guardian Platform** jako fundament pod profile projektowe.

**Nie w scope tego etapu:**
- profil IFG (logika domenowa)
- deploy, KSeF, magazyn, DS723, frontend-react, docker-compose, alembic
- migracja / modyfikacja starego `scripts/ifg_guardian`
- podłączenie `scripts/guardian.py` jako entrypoint platformy
- osobne repo `guardian`

---

## Co zostało zbudowane

### Struktura

```
scripts/guardian_platform/
  __init__.py              # version 0.1.0
  __main__.py              # python3 -m guardian_platform
  core/
    cli/                   # dynamic command resolution
    config/                # .guardian.yml loader
    registry/              # commands, profiles, workflows
    profiles/              # GuardianProfile API, loader, CoreProfile
    reporting/             # terminal / json / markdown
    runtime/               # CommandContext, ExecutionMode, mutating guard
    shell/                 # subprocess runner
    git/                   # neutral git client
    filesystem/            # path helpers
    environment/           # hostname, python, CI detection
    workflow/              # engine, executors, core.ping
  profiles/
    ifg_scaffold/          # guardian ifg ping
    psag_scaffold/         # guardian psag ping
```

### Konfiguracja projektu

- `.guardian.yml` w root repo IFG (aktywne profile: `ifg_scaffold`, `psag_scaffold`)
- Loader przeszukuje katalogi w górę (działa z `scripts/` i root)

### Core dostarcza

| Obszar | Status |
|--------|--------|
| Ładowanie `.guardian.yml` | ✓ |
| Registry profili | ✓ |
| Registry komend (`CommandSpec`) | ✓ |
| Dynamiczny CLI (bez argparse w profilach) | ✓ |
| Globalne flagi `--dry-run`, `--yes`, `--format` | ✓ |
| Blokada mutating bez `--yes` | ✓ |
| Raportowanie terminal/json/markdown | ✓ |
| Profile loader | ✓ |
| Workflow engine (neutralny) | ✓ |
| `core.ping` workflow | ✓ |

### Scaffoldy (tylko test architektury)

| Profil | Komenda | Output |
|--------|---------|--------|
| `ifg_scaffold` → id `ifg` | `ifg ping` | `ifg scaffold active` |
| `psag_scaffold` → id `psag` | `psag ping` | `psag scaffold active` |

Zero logiki IFG. PSAG scaffold **nie importuje** IFG.

---

## Działające komendy

Uruchomienie: `cd scripts && python3 -m guardian_platform <command>`

| Komenda | Wynik (2026-06-26) |
|---------|-------------------|
| `plugin list` | core, ifg, psag — exit 0 |
| `platform doctor` | status DEGRADED (dirty git) — exit 1 |
| `workflow list` | `core.ping` — exit 0 |
| `workflow run core.ping` | SUCCESS, 20ms — exit 0 |
| `ifg ping` | `ifg scaffold active` — exit 0 |
| `psag ping` | `psag scaffold active` — exit 0 |
| `repo status` | branch production, dirty — exit 0 |
| `repo audit --format json` | generic audit JSON — exit 0 |
| `platform mutate-test` | blocked bez `--yes` — exit 2 |
| `platform mutate-test --yes` | executed — exit 0 |

---

## Weryfikacja grep (core neutrality)

```bash
grep -ri "KSeF" scripts/guardian_platform/core/           # 0
grep -ri "ds723" scripts/guardian_platform/core/          # 0
grep -ri "frontend-react" scripts/guardian_platform/core/   # 0
grep -r "ifg_guardian" scripts/guardian_platform/core/      # 0
grep -r "profiles.ifg" scripts/guardian_platform/profiles/psag_scaffold/  # 0
```

---

## Stary Guardian

- `scripts/ifg_guardian/` — **nietknięty**
- `scripts/guardian.py` — **nietknięty** (smoke: `python3 scripts/guardian.py doctor` działa)
- Testy legacy: **104 passed** (`python3.11 -m pytest tests/unit/test_guardian_*.py`)

---

## Acceptance Checklist

| # | Kryterium | Status |
|---|-----------|--------|
| 1 | Platforma uruchamia się przez `python3 -m guardian_platform` | ✓ |
| 2 | Core bez logiki IFG (grep) | ✓ |
| 3 | `ifg_scaffold` i `psag_scaffold` działają niezależnie | ✓ |
| 4 | Dynamiczny CLI z registry | ✓ |
| 5 | Mutating bez `--yes` blokowany | ✓ |
| 6 | Raportowanie terminal (+ json/markdown) | ✓ |
| 7 | Stary Guardian nietknięty | ✓ |
| 8 | `plugin list` → core + ifg + psag | ✓ |
| 9 | PSAG scaffold bez importu IFG | ✓ |
| 10 | Dokumentacja: IFG dopiero w następnym etapie | ✓ |

---

## Co NIE zostało zrobione

- Profil IFG produkcyjny (doctor, release plan, deploy, KSeF, warehouse, …)
- Przeniesienie kodu z `ifg_guardian/` do platformy
- Podłączenie `scripts/guardian.py` → platforma
- Sunset `guardian2.py`
- Osobne repo `guardian`
- Testy jednostkowe platformy (osobny pakiet testów — TODO)
- Pełny repo audit (CRLF, extensions z profili)
- Entry points pip / pyproject.toml
- Persystencja `.guardian/workflows/` w platformie (engine minimalny, bez zapisu JSON)

---

## Następny etap

**GUARDIAN_IFG_PROFILE_IMPLEMENTATION**

- Przenieść logikę IFG do `guardian_platform/profiles/ifg/` (zastąpić `ifg_scaffold`)
- Podłączyć workflows: `ifg.doctor`, `ifg.release.plan`, `ifg.deploy.run`
- Przenieść deploy executors, DS723 config, repo audit extensions
- Wrapper `scripts/ifg_guardian/cli.py` → bootstrap platformy + legacy aliasy
- Bez zmian w core poza ewentualnymi hookami rejestracji

---

## Powiązane dokumenty

- [GUARDIAN_PLATFORM_ARCHITECTURE.md](GUARDIAN_PLATFORM_ARCHITECTURE.md)
- [GUARDIAN_CORE_PROFILE_SPLIT.md](GUARDIAN_CORE_PROFILE_SPLIT.md)
- [GUARDIAN_V1_RELEASE.md](GUARDIAN_V1_RELEASE.md)
