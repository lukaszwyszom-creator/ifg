# IFG Guardian — raport: kontrola synchronizacji repo

**Data:** 2026-06-08  
**Plik:** `scripts/guardian.py`

## Co zmieniono

Dodano tryb `--repo-sync` do IFG Guardian MVP oraz:

- `--fetch` — opcjonalny `git fetch origin production` przed odczytem
- `--remote ds723` — porównanie Mac mini / GitHub / DS723+ przez SSH
- `--remote-host`, `--remote-path` — parametry zdalnego repo

| Odczyt lokalny | Komenda git |
|----------------|-------------|
| Gałąź | `git branch --show-current` |
| Lokalny HEAD | `git rev-parse HEAD` |
| Origin production | `git rev-parse origin/production` |
| Status roboczy | `git status --porcelain` |
| Ahead / behind | `git rev-list --left-right --count HEAD...origin/production` |

| Odczyt DS723+ (SSH) | Komenda |
|---------------------|---------|
| Gałąź | `ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && git branch --show-current'` |
| HEAD | `git rev-parse HEAD` |
| Status | `git status --porcelain` |

Guardian **nie wykonuje** pull, push, commit ani deploy — tylko odczyt i raport.

## Jak uruchamiać

```bash
# dotychczasowy check API (mobile-expo ↔ backend)
python3 scripts/guardian.py

# kontrola synchronizacji repo (bez fetch — origin/production może być nieaktualne)
python3 scripts/guardian.py --repo-sync

# kontrola z odświeżeniem origin/production przed odczytem ahead/behind
python3 scripts/guardian.py --repo-sync --fetch

# porównanie Mac mini ↔ GitHub ↔ DS723+
python3 scripts/guardian.py --repo-sync --remote ds723

# z fetch + własnym hostem/ścieżką
python3 scripts/guardian.py --repo-sync --fetch --remote ds723 \
  --remote-host ds723 \
  --remote-path /volume1/docker/ifg_v2/ifg_standalone
```

### Flaga `--fetch`

| Tryb | Zachowanie |
|------|------------|
| `--repo-sync` | Tylko odczyt lokalnego stanu git; ostrzeżenie o możliwym stale `origin/production` |
| `--repo-sync --fetch` | Najpierw `git fetch origin production --quiet`, potem odczyt HEAD/ahead/behind |

Przy błędzie fetch: `Status: ERROR`, exit code `1`.

### Flaga `--remote ds723`

Porównuje lokalne `origin/production` z HEAD na DS723+ (SSH).  
`?? backups/` na DS723+ jest **neutralne** (nie liczy się jako dirty).

## Przykładowy output (lokalny)

```
IFG Guardian Repo Sync
========================================

Local branch: production
Local HEAD: 1ba0ee3a1b2c3d4e5f6789012345678901234567
Origin production: 1ba0ee3a1b2c3d4e5f6789012345678901234567
Local ahead: 0
Local behind: 0
Local working tree: clean

✅ local on production branch
✅ local working tree clean
✅ local clean + synced with origin/production

========================================
Status: OK
```

## Przykładowy output (z `--remote ds723`)

```
IFG Guardian Repo Sync
========================================

Local branch: production
Local HEAD: 902cd60...
Origin production: 902cd60...
Local ahead: 0
Local behind: 0
Local working tree: clean

Remote DS723 (ds723:/volume1/docker/ifg_v2/ifg_standalone)
----------------------------------------
Remote DS723 branch: production
Remote DS723 HEAD: 207dd51...
Remote DS723 working tree: clean

Sync summary:
  Mac mini : 902cd60
  GitHub   : 902cd60
  DS723+   : 207dd51
  ⚠️  DS723+ out of sync with GitHub (origin/production)

⚠️  DS723+ behind origin/production (3 commit(s))

========================================
Status: WARNING
```

Przykład ostrzeżenia (bez `--fetch`):

```
⚠️  origin/production may be stale. Run: git fetch origin production
⚠️  local working tree dirty

Status: WARNING
```

Przykład ostrzeżenia (sync):

```
⚠️  local ahead of origin/production (2 commit(s))

Status: WARNING
```

Przykład błędu:

```
❌ local not on production branch

Status: ERROR
```

## Interpretacja statusów

| Symbol | Znaczenie |
|--------|-----------|
| ✅ local clean + synced | Gałąź `production`, brak ahead/behind, czyste drzewo |
| ⚠️ local working tree dirty | Są niezacommitowane zmiany lokalnie |
| ⚠️ local ahead / behind | Lokalne repo vs `origin/production` |
| ⚠️ DS723+ behind / ahead | Zdalny HEAD vs lokalne `origin/production` |
| ⚠️ remote dirty | Zmiany na DS723+ poza `?? backups/` |
| ❌ wrong branch | Lokalna lub zdalna gałąź ≠ `production` |
| ❌ SSH failed | Brak połączenia lub błąd git na DS723+ |

Exit code: `0` = OK, `1` = WARNING lub ERROR.

## Ograniczenia

- Guardian **nie wdraża** i **nie synchronizuje** automatycznie Mac mini ↔ GitHub ↔ DS723+ — tylko **ostrzega**.
- Remote check wymaga skonfigurowanego SSH aliasu `ds723` (lub `--remote-host`).
- Wymaga dostępnego `origin/production` lokalnie (zalecane: `--fetch`).
- Nie sprawdza stanu kontenerów Docker — tylko repozytorium git.
- Ahead/behind DS723+ liczone względem lokalnego `origin/production` z Mac mini.
