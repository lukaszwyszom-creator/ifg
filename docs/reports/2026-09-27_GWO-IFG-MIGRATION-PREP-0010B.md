# GWO-IFG-MIGRATION-PREP-0010B — Zabezpieczenie WIP przed migracją WorkspaceSSD

**Data:** 2026-09-27  
**Tryb:** prep only — **bez** przeniesienia repo, bez LaunchAgents, bez Profiles/IFG.md, bez deployu DS723+  
**Następny GWO:** `GWO-IFG-REPO-MIGRATION-WORKSPACESSD-0010C`

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

`READY_FOR_DEPLOY` = prep zakończony; brak zmian aplikacji do weryfikacji UX; DS723+ nietknięty.

---

## STATUS

```
STATUS: COMPLETE
VERDICT: READY_FOR_REPO_MIGRATION
```

---

## ETAP 1 — INVENTORY FREEZE (przed mutacjami)

| Pole | Wartość |
|------|---------|
| Canonical | `/Users/lukasz/projekty/ifg_standalone` |
| Branch | `production` |
| HEAD | `d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa` |
| origin/production | `d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa` |
| ahead/behind | `0 / 0` |
| staged | puste (`git diff --cached --stat` empty) |
| Worktrees | canonical + `/Users/lukasz/projekty/ifg_standalone_gwo_0002c` @ `cde9c76` |

### Modified tracked (7)

- `docs/GUARDIAN2_RECOVERY_DS723.md`
- `docs/_archiwum/migracja_mac_mini.md`
- `frontend-react/package.json`
- `scripts/ifg_guardian/plugins/ifg/doctor/aggregation.py`
- `scripts/ifg_guardian/plugins/ifg/release_plan/stages.py`
- `tests/unit/test_guardian_ifg_handoff.py`
- `tests/unit/test_guardian_preflight.py`

### Untracked (25)

- `docs/gwo/` (2 plany STOCK)
- `docs/reports/2026-07-20_*` … `2026-09-23_*` (21 raportów)
- `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js`
- `tests/unit/test_guardian_deploy_decision_engine.py`

`git diff --stat` (pre): 7 files, +1197 / −985

---

## ETAP 2 — STOCK-0002C

| Check | Result |
|-------|--------|
| Local HEAD | `cde9c7673425452df66453c3ab3b035ff490d4cb` |
| Unique commits vs production | `3edcf9f`, `cde9c76` (2) |
| origin before | brak |
| `git diff -w` | pusty (EOL-only dirty) |
| Push | `origin/gwo/ifg-stock-0002c-invoice-warehouse-link` |
| Remote SHA | `cde9c7673425452df66453c3ab3b035ff490d4cb` |
| Verified | **YES** (local == ls-remote == fetch) |
| Merged to production | **NO** (zgodnie z zakazem) |

---

## ETAP 3 — WIP SNAPSHOT

| Pole | Wartość |
|------|---------|
| Branch | `gwo/ifg-pre-migration-wip-snapshot-0010b` |
| Base | `d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa` |
| Commit | `5bde904e4e4cbb3e0f0ccf0f281e8ff4653f2cab` |
| Message | `chore(recovery): preserve pre-migration IFG working tree` |
| Files | 32 (7 M + 25 A) |
| Remote | `origin/gwo/ifg-pre-migration-wip-snapshot-0010b` @ `5bde904…` |
| Remote verified | **YES** |

### SECURITY_SCAN: PASS

- Brak staged `.env` / credentials / private keys / binariów / plików >500KB
- Heurystyki hard-secret: clean
- Jedyny content hit: placeholder `postgres:twoje_haslo@localhost` w `docs/_archiwum/migracja_mac_mini.md` (przykład w bloku ```env``` z `<wygeneruj…>` / `<silne hasło>`) — **nie sekret produkcyjny**

Snapshot = punkt odzyskania, **nie** kandydat do auto-merge do `production`.

---

## ETAP 4 — CANONICAL PRODUCTION

Po weryfikacji remote snapshot:

1. `git checkout production`
2. `git reset --hard d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa`
3. `git clean -fd`

### Uwaga EOL / skip-worktree

Po hard reset `docs/_archiwum/migracja_mac_mini.md` wracał jako dirty wyłącznie z powodu historycznego blob CRLF vs `.gitattributes` `eol=lf` (treść identyczna po strip CR). Wersja LF jest już na snapshot `5bde904`.

Aby uzyskać `git status` CLEAN **bez** zmiany `origin/production`:

```text
git update-index --skip-worktree -- docs/_archiwum/migracja_mac_mini.md
```

Lokalny flag index (`S` w `git ls-files -v`). Przed edycją tego pliku: `git update-index --no-skip-worktree -- …`.

`origin/production` **niezmieniony**: `d3571ec…`

---

## ETAP 5 — STARY WORKTREE

| Check | Result |
|-------|--------|
| HEAD == origin STOCK | YES (`cde9c76`) |
| Content diff (`-w`) | empty |
| Remove | `git worktree remove --force` (EOL noise blokował clean remove) |
| prune | wykonane |
| Path | usunięty |
| Remote branch | **zachowany** |

`git worktree list --porcelain` — wyłącznie canonical `production`.

---

## ETAP 6 — FINAL GATE

| # | Kryterium | Wynik |
|---|-----------|-------|
| 1 | production HEAD `d3571ec…` | PASS |
| 2 | origin/production ten sam | PASS |
| 3 | working tree CLEAN (porcelain 0) | PASS |
| 4 | snapshot local+remote `5bde904…` | PASS |
| 5 | STOCK origin `cde9c76…` | PASS |
| 6 | old worktree | **REMOVED** |
| 7 | DS723+ | **NO** |
| 8 | LaunchAgents | **NO** (ścieżki nadal `~/projekty/ifg_standalone`) |
| 9 | WorkspaceSSD target | **nieutworzony** |

---

## OUTPUT CONTRACT

```
STATUS: COMPLETE
VERDICT: READY_FOR_REPO_MIGRATION
PRODUCTION_HEAD: d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa
ORIGIN_PRODUCTION_HEAD: d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa
PRODUCTION_WORKTREE_CLEAN: YES
WIP_SNAPSHOT_BRANCH: gwo/ifg-pre-migration-wip-snapshot-0010b
WIP_SNAPSHOT_SHA: 5bde904e4e4cbb3e0f0ccf0f281e8ff4653f2cab
WIP_SNAPSHOT_REMOTE_VERIFIED: YES
STOCK_BRANCH: gwo/ifg-stock-0002c-invoice-warehouse-link
STOCK_LOCAL_SHA: cde9c7673425452df66453c3ab3b035ff490d4cb
STOCK_REMOTE_SHA: cde9c7673425452df66453c3ab3b035ff490d4cb
STOCK_REMOTE_VERIFIED: YES
OLD_WORKTREE: REMOVED
SECURITY_SCAN: PASS
DS723_TOUCHED: NO
LAUNCHAGENTS_TOUCHED: NO
WORKSPACESSD_MIGRATION_STARTED: NO
NEXT_GWO: GWO-IFG-REPO-MIGRATION-WORKSPACESSD-0010C
```

### FILES_PRESERVED (snapshot `5bde904`)

Modified: `docs/GUARDIAN2_RECOVERY_DS723.md`, `docs/_archiwum/migracja_mac_mini.md`, `frontend-react/package.json`, `scripts/ifg_guardian/plugins/ifg/doctor/aggregation.py`, `scripts/ifg_guardian/plugins/ifg/release_plan/stages.py`, `tests/unit/test_guardian_ifg_handoff.py`, `tests/unit/test_guardian_preflight.py`

Added: `docs/gwo/*` (2), `docs/reports/2026-07-20…`–`2026-09-23…` (21), `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js`, `tests/unit/test_guardian_deploy_decision_engine.py`

### MUTATIONS_PERFORMED

1. Push `gwo/ifg-stock-0002c-invoice-warehouse-link` → origin  
2. Branch + commit + push `gwo/ifg-pre-migration-wip-snapshot-0010b` @ `5bde904`  
3. Checkout `production` @ `d3571ec` + hard reset + clean  
4. `skip-worktree` na `docs/_archiwum/migracja_mac_mini.md` (lokalnie)  
5. `git worktree remove --force` + `prune` dla `ifg_standalone_gwo_0002c`

### NIE wykonano

- przeniesienia repo / utworzenia `/Volumes/WorkspaceSSD/projects/ifg_standalone`
- zmian LaunchAgents / Profiles/IFG.md
- deployu / mutacji DS723+
- merge snapshot ani STOCK do `production`
- usunięcia remote STOCK branch

---

## Dowody

```bash
git -C ~/projekty/ifg_standalone rev-parse HEAD origin/production
# d3571ec… / d3571ec…

git -C ~/projekty/ifg_standalone status -sb
# ## production...origin/production

git -C ~/projekty/ifg_standalone worktree list
# /Users/lukasz/projekty/ifg_standalone  d3571ec [production]

git ls-remote --heads origin \
  gwo/ifg-pre-migration-wip-snapshot-0010b \
  gwo/ifg-stock-0002c-invoice-warehouse-link
# 5bde904…  gwo/ifg-pre-migration-wip-snapshot-0010b
# cde9c76…  gwo/ifg-stock-0002c-invoice-warehouse-link
```

---

## Decyzje dla ChatGPT

1. Czy w 0010C przed rsync wolno zostawić lokalny `skip-worktree` na `migracja_mac_mini.md`, czy najpierw osobny mikro-commit renormalizacji EOL na `production`?  
2. Czy snapshot `5bde904` ma pozostać recovery-only, czy po migracji osobne GWO ma selektywnie portować implementację Guardian (aggregation/stages/tests)?

## GENERATED REPORTS

Ten plik: `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-27_GWO-IFG-MIGRATION-PREP-0010B.md`
