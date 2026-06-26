# IFG Guardian v3 — architektura i plan migracji

**Data:** 2026-06-26  
**Wersja:** `3.0.0-alpha.1` (etap 1 — refaktoryzacja + CLI)  
**Status:** Etap 1 zaimplementowany; pełne v3 w kolejnych commitach.

---

## 1. Cel

Guardian ma być **jednym narzędziem administracyjnym IFG** zamiast rozproszonych flag (`--deploy-check`, `--repo-sync`) i osobnego `guardian2.py`.

Zasady:
- **Read-only domyślnie** — mutacje tylko przy jawnych komendach (`deploy run`, `prod recover --yes`).
- **Zakaz automatycznego** `git restore/clean/reset/commit/push/rm` w trybach audytu.
- **Kompatybilność wsteczna** — stare flagi działają jako aliasy (deprecated).
- **Raporty** w `docs/guardian/`.

---

## 2. Stan przed migracją (v2)

| Plik | Rola | Tryby |
|------|------|-------|
| `scripts/guardian.py` | ~1116 linii monolitu | API mobile, `--deploy-check`, `--ksef-async-check`, `--repo-sync` |
| `scripts/guardian2.py` | Deploy/recovery | `deploy-ksef`, `recover-prod` (mutujące) |

Problemy:
- Jedna flaga = jedna funkcja, brak spójnego CLI.
- Brak `repo audit` z klasyfikacją i ryzykiem.
- Brak centralnego katalogu raportów.
- `guardian2` ładuje `guardian.py` przez `importlib`.

---

## 3. Architektura v3 (etap 1)

```
scripts/
  guardian.py                 # entry point + re-export compat
  guardian2.py                # mutacje deploy/recover (delegat etap 1)
  ifg_guardian/
    __init__.py               # __version__
    __main__.py               # python3 -m ifg_guardian
    cli.py                    # centralny parser subcommands + legacy aliases
    config.py                 # ROOT, stałe, IGNORE_PATTERNS
    compat.py                 # re-export dla guardian2 / starych importów
    reporting.py              # zapis do docs/guardian/
    core/
      git.py                  # git, porcelain, resolve_ds723_host
      ssh.py                  # ssh, remote_git
      compose.py              # docker compose ps parsing
      risk.py                 # RiskLevel, FileCategory
    modules/
      repo.py                 # status, audit, clean --dry-run
      deploy.py               # deploy check
      production.py           # prod health, recover delegate
      ksef.py                 # ksef check (+ sync placeholder)
      frontend.py             # frontend check, dist freshness
      warehouse.py            # warehouse check
      api_mobile.py           # mobile-expo ↔ backend (domyślny stary tryb)
      doctor.py               # agregat read-only
```

### Mapowanie CLI v3

| Komenda v3 | Moduł | Mutująca? | Status etap 1 |
|------------|-------|-----------|---------------|
| `guardian repo status` | `repo.run_repo_sync` | Nie | ✅ |
| `guardian repo audit` | `repo.run_repo_audit` | Nie | ✅ |
| `guardian repo clean --dry-run` | `repo.run_repo_clean_dry_run` | Nie | ✅ |
| `guardian deploy check` | `deploy.run_deploy_check` | Nie | ✅ |
| `guardian deploy run` | → `guardian2 deploy-ksef` | **Tak** | ✅ delegate |
| `guardian ksef check` | `ksef.run_ksef_check` | Nie | ✅ |
| `guardian ksef sync` | placeholder | — | 🔜 etap 2 |
| `guardian prod health` | `production.run_prod_health` | Nie | ✅ |
| `guardian prod recover` | → `guardian2 recover-prod` | **Tak** | ✅ delegate |
| `guardian frontend check` | `frontend.run_frontend_check` | Nie | ✅ |
| `guardian warehouse check` | `warehouse.run_warehouse_check` | Nie | ✅ |
| `guardian doctor` | `doctor.run_doctor` | Nie | ✅ |
| `guardian version` | cli | Nie | ✅ |

### Legacy aliases (deprecated)

| Stara flaga | Nowa komenda |
|-------------|--------------|
| _(brak flag)_ | `guardian` / API mobile check |
| `--deploy-check` | `guardian deploy check` |
| `--ksef-async-check` | `guardian ksef check` |
| `--repo-sync [--fetch] [--remote ds723]` | `guardian repo status ...` |

---

## 4. Repo audit (nowe w etap 1)

### Klasyfikacja plików (`FileCategory`)

| Kategoria | Znaczenie |
|-----------|-----------|
| `commit` | Bezpieczne / zamierzone do commita (docs, testy) |
| `ignore` | Powinno być w `.gitignore` (dist, env) |
| `delete_review` | Nieśledzone — decyzja człowieka |
| `crlf_noise` | Tylko końce linii (`git diff -w` pusty) |
| `substantive` | Zmiana merytoryczna (app/, frontend src) |
| `deploy_blocker` | Sekrety / krytyczne |

### Poziom ryzyka (`RiskLevel`)

| Poziom | Kryteria przykładowe |
|--------|---------------------|
| **LOW** | Czyste repo, tylko docs |
| **MEDIUM** | CRLF-only, untracked docs, behind/ahead |
| **HIGH** | Zmiany app/frontend bez build, zła gałąź |
| **CRITICAL** | `.env` w diff, sekrety |

### Sekcja RECOMMENDED ACTION

Generowana heurystycznie — **tylko tekst**, bez wykonywania poleceń.

Raport: `docs/guardian/REPO_AUDIT_YYYY_MM_DD.md`

---

## 5. Plan migracji v2 → v3

### Etap 1 ✅ (ten commit)

- [x] Pakiet `ifg_guardian/` z modułami domenowymi
- [x] CLI subcommands + legacy aliases
- [x] `repo audit` z klasyfikacją, ryzykiem, RECOMMENDED ACTION
- [x] `repo clean --dry-run` (preview only)
- [x] Raporty w `docs/guardian/`
- [x] `guardian2` importuje `ifg_guardian.compat`
- [x] Logika istniejących checków **bez zmian merytorycznych** (przeniesienie 1:1)

### Etap 2 (następny)

- [ ] Przenieść `deploy-ksef` / `recover-prod` do `ifg_guardian/modules/deploy_run.py` i `production.py`
- [ ] Usunąć `guardian2.py` jako osobny entry — zastąpić `guardian deploy run` / `guardian prod recover`
- [ ] Zaimplementować `guardian ksef sync` (read-only trigger vs API)
- [ ] `guardian doctor --report` → jeden raport zbiorczy MD
- [ ] Alias shell: `scripts/guardian` (bez `.py`) lub `pip install -e .` entry point `guardian`

### Etap 3

- [ ] CI: `guardian repo audit` + `guardian deploy check` w pipeline
- [ ] Deprecation warning → usunięcie legacy flag (min. 1 release cycle)
- [ ] Integracja z `.cursor/rules/rules_10_guardian.mdc` (nowe komendy)
- [ ] Testy jednostkowe: porcelain parser, klasyfikacja, risk scoring

### Etap 4

- [ ] `guardian warehouse check` — walidacja API/stan DB (read-only SQL)
- [ ] `guardian prod health` — rozszerzenie: alembic head, worker queue
- [ ] Opcjonalny TUI / JSON output (`--format json`)

---

## 6. Ocena ryzyka migracji

| Ryzyko | Poziom | Mitygacja |
|--------|--------|-----------|
| Regresja `--deploy-check` / `--repo-sync` | **Średnie** | Kod przeniesiony 1:1; legacy aliases; ręczna weryfikacja |
| Zepsuty import `guardian2` | **Niskie** | `compat.py` re-exportuje te same symbole |
| Fałszywe alarmy `repo audit` | **Średnie** | Heurystyki; RECOMMENDED ACTION = sugestie, nie auto-exec |
| Porcelain parsing | **Naprawione** | `line[2:].lstrip()` zamiast `line[3:]` |
| Doctor zbyt wolny (SSH) | **Niskie** | `deploy check` w doctor wymaga DS723+ — dokumentacja |
| Mutacja przez pomyłkę | **Niskie** | `deploy run` / `prod recover` wymagają `--yes` |

---

## 7. Komendy po etapie 1

```bash
cd /Users/lukasz/projekty/ifg_standalone

# Nowe (v3)
python3 scripts/guardian.py repo audit --fetch
python3 scripts/guardian.py repo clean --dry-run
python3 scripts/guardian.py deploy check
python3 scripts/guardian.py ksef check
python3 scripts/guardian.py frontend check
python3 scripts/guardian.py warehouse check
python3 scripts/guardian.py doctor
python3 scripts/guardian.py version

# Mutujące (jawnie)
python3 scripts/guardian.py deploy run --yes
python3 scripts/guardian.py prod recover --yes

# Legacy (deprecated, nadal działa)
python3 scripts/guardian.py --deploy-check
python3 scripts/guardian.py --repo-sync --fetch --remote ds723
python3 scripts/guardian.py --ksef-async-check
python3 scripts/guardian2.py deploy-ksef --yes
```

Opcjonalny alias na Mac mini (`~/.zshrc`):
```bash
alias guardian='python3 /Users/lukasz/projekty/ifg_standalone/scripts/guardian.py'
```

---

## 8. Pliki zmienione (etap 1)

| Plik | Zmiana |
|------|--------|
| `scripts/guardian.py` | Cienki entry + compat re-export |
| `scripts/guardian2.py` | Import z `ifg_guardian.compat` |
| `scripts/ifg_guardian/**` | Nowy pakiet |
| `docs/GUARDIAN_V3_ARCHITECTURE.md` | Ten dokument |
| `docs/guardian/REPO_AUDIT_*.md` | Raporty generowane |

---

## 9. Werdykt etapu 1

**Gotowe do użytku lokalnego.** Produkcja DS723+ — bez zmian w deploy flow (`guardian2` nadal używany przez `deploy run`). Kolejny commit: przeniesienie logiki mutującej do pakietu i testy regresji.
