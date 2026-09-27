# GWO-IFG-POST-RELEASE-CLEANUP-0011

Data: 2026-09-23  
Cel: posprzątanie środowiska po potwierdzonym E2E release IFG — **bez** zmiany funkcjonalności, **bez** Undo All, **bez** kasowania nieznanego WIP.

## VERDICT

`CLEANUP_PARTIAL_SCM_162_NOT_CURRENT_DIRTY`

Produkcja i legacy `:32768` posprzątane; lokalny WIP (Guardian/stock/raporty) **zachowany**. Liczba „162 Files” w Cursor **nie** odpowiada obecnemu dirty set (~30).

---

## 1. CURSOR — „162 Files”

### Źródło liczby

| Hipoteza | Evidence | Werdykt |
|---|---|---|
| Aktualny `git status` ifg_standalone | **29–30** linii porcelain | NIE = 162 |
| Suma sibling repos + worktree | ~64–69 | NIE |
| Agent transcripts | 66 | NIE |
| Tracked WT z bajtami CRLF | **~167** (najbliższe) | prawdopodobny historyczny „dirty/EOL” snapshot UI |
| Cursor multi-root | workspace = **single** `ifg_standalone` | nie multi-folder |

**Wniosek:** `CURSOR_FILES_BEFORE: 162` to **historyczny/stale** wskaźnik UI (najpewniej długie EOL debt / stary SCM snapshot), nie aktualna lista do usunięcia.

### Repo / worktree (stan)

| Ścieżka | Branch | HEAD | M | ?? | Staged |
|---|---|---|--:|---:|---:|
| `/Users/lukasz/projekty/ifg_standalone` | `production` | `d3571ec` (+ docs tip later) | 7 | ~22 | 0 |
| `/Users/lukasz/projekty/ifg_standalone_gwo_0002c` | `gwo/ifg-stock-0002c-invoice-warehouse-link` | `cde9c76` | 21 EOL-only | 0 | 0 |

### Klasyfikacja dirty (primary, ~30 ścieżek)

| Kat. | Opis | Akcja |
|---|---|---|
| **A** | Tracked WIP (Guardian doctor/release/tests, GUARDIAN2_RECOVERY) | **ZACHOWANE** |
| **B** | Untracked WIP (stock GWO docs, numbering test, guardian deploy test) | **ZACHOWANE** |
| **C** | Generated w status | **brak** (node_modules/dist/__pycache__ są ignored) |
| **D** | EOL-only (`migracja_mac_mini.md`, `package.json`) | **ZACHOWANE** (nie renorm w tym GWO) |
| **E** | Untracked raporty zakończonych GWO (09-12…09-22) | **ZACHOWANE** jako dokumentacja |
| **F** | Nieznane | **brak** |

---

## 2. WORKTREES

- `ifg_standalone_gwo_0002c`: **KEEP** — 2 unikalne commity stock **nie** na `production`.
- Usunięto worktree: **0**
- `git worktree prune`: nie wymagane / nie usuwano aktywnych

---

## 3. STASH (nie usuwano)

| Stash | Treść | Status |
|---|---|---|
| `stash@{0}` `gwo-0064-temp-gate-check` | ~50 plików (transmissions/invoice/frontend/guardian) | **PRESERVE** — wygląda na duży WIP |
| `stash@{1}` `wip guardian async docs before ksef numbering deploy` | 3 pliki docs/guardian | **PRESERVE** |

---

## 4. BACKGROUND TERMINALS

| | Wartość |
|---|---|
| BEFORE | **10–14** stale agent sessions (meta `running`, PID dead) |
| AFTER | **1** (pozostawiony niesklasyfikowany jako IFG leftover) |

Usunięto **tylko** martwe pliki sesji Cursor `terminals/*.txt` po zakończonych shellach IFG/KSeF.  
**Nie** ruszano Guardian / PSAG / Ollama / LaunchAgent / produkcji.

---

## 5. LEGACY `:32768`

| Check | Wynik |
|---|---|
| Kontener | `ifg-frontend-1` (nginx, obraz 2026-05-06, compose project `docker`, `restart: always`) |
| Konsumenci | **brak** (cloudflared → `:8000`; brak reverse-proxy/cron na 32768) |
| Kanoniczne UI | API **`/ui`** na `:8000` |
| Akcja | `docker update --restart=no` → `stop` → `rm` (obrazy zachowane) |
| Po | `:32768` **DOWN**; `/ui` 200; `/health` ok; api/worker/db healthy |

Zmiana **tylko na NAS** — bez commit/compose (frontend już usunięty z `docker-compose.prod.yml`).

---

## 6. FINALNY STAN

```
CURSOR_BACKGROUND_TERMINALS_BEFORE: 14
CURSOR_BACKGROUND_TERMINALS_AFTER: 1

CURSOR_FILES_BEFORE: 162
CURSOR_FILES_CLASSIFIED: A=5 B=4 C=0 D=2 E=19 F=0 (+ worktree D=21 KEEP; 162≠current dirty)
CURSOR_FILES_AFTER: 31 (ifg_standalone porcelain; WIP preserved)

LEGITIMATE_WIP_PRESERVED: YES
TEMP_FILES_REMOVED: NO (brak bezpiecznych C w dirty status; terminals metadata YES)
WORKTREES_REMOVED: 0
STASHES_PRESERVED: YES (2)

LEGACY_32768_STATUS: REMOVED
CANONICAL_UI_STATUS: PASS (/ui :8000)

IFG_PRODUCTION_HEALTH: PASS (api/worker/db healthy, /health ok)

VERDICT: CLEANUP_PARTIAL_SCM_162_NOT_CURRENT_DIRTY
```

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [x] DEPLOYED_TO_DS723
- [x] PRODUCTION_VERIFIED

*(cleanup ops; produkcja IFG bez regresji)*

## Decyzje dla ChatGPT

1. Czy commitować zaległe raporty E (untracked `docs/reports/…`) osobnym docs GWO?
2. Czy kontynuować stock worktree `gwo_0002c`, czy zamknąć osobnym GWO?
3. Czy dropnąć któryś ze stashy po ręcznym przeglądzie?
