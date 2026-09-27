# GWO-IFG-EOL-RENORMALIZATION-0001

Data: 2026-09-22  
Cel: osobny commit techniczny CRLF→LF wyłącznie dla dwóch plików contractor — **bez** feature KSeF w commicie.

## ETAP 1 — PREFLIGHT

Ścieżki:
- `app/services/contractor_service.py`
- `frontend-react/src/api/contractors.js`

| Check | Wynik |
|---|---|
| Index staged empty | YES |
| HEAD CRLF | YES (288 / 12 CRLF) |
| `.gitattributes` `eol=lf` | YES (`*.py`, `*.js`) |
| PREVIOUS_HEAD | `42b77faf5b5ba37d250bb76fba1d5ae193dd8235` |

## ETAP 2–3 — INDEX (plumbing)

Źródło: wyłącznie `git show HEAD:<path>` → CRLF→LF → `hash-object -w` → `update-index --cacheinfo`.  
Working tree **nie** nadpisany.

Przed commit:
- staged = dokładnie 2 pliki
- `git diff --cached --ignore-cr-at-eol` = **EMPTY**

## ETAP 4 — COMMIT

```
e686bacd6012e3c7baa53186ea19206d77a5891c
chore(ifg): normalize contractor address files to LF
2 files changed, 300 insertions(+), 300 deletions(-)
```

Bez push.

## ETAP 5 — POST-COMMIT

Feature WT zachowany. Diff vs nowy HEAD (ignore-cr = raw):

| Plik | Diff |
|---|---|
| `contractor_service.py` | `+2 / -1` (`is not None`) |
| `contractors.js` | `+3 / -0` (`updateOverride`) |

POST_COMMIT_EOL_NOISE: **NO**

## STATUS

```
STATUS: SUCCESS
PREVIOUS_HEAD: 42b77faf5b5ba37d250bb76fba1d5ae193dd8235
EOL_COMMIT_SHA: e686bacd6012e3c7baa53186ea19206d77a5891c
FILES_IN_COMMIT: app/services/contractor_service.py ; frontend-react/src/api/contractors.js
CACHED_IGNORE_CR_DIFF: EMPTY
WORKING_TREE_PRESERVED: YES
CONTRACTOR_SERVICE_FEATURE_DIFF_LINES: +2/-1
CONTRACTORS_JS_FEATURE_DIFF_LINES: +3/-0
POST_COMMIT_EOL_NOISE: NO
READY_TO_REPEAT_KSEF_PRECOMMIT_GATE: YES
VERDICT: EOL_RENORM_OK_FEATURE_DIFF_CLEAN
```

## RELEASE STATE

- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED
- [ ] LOCAL_REVIEW_REQUIRED

(docs/standard chore — bez DS723; odblokowuje powtórzenie KSeF precommit gate)

## Dodatkowe zasady techniczne (weryfikacja post-factum)

| Zasada | Status względem `e686bac` |
|---|---|
| Nie używać `git add --renormalize` | OK w praktyce (plumbing + tylko 2 pliki); użycie renormalize w historii: UNKNOWN |
| `git hash-object --no-filters` | Blob w commitcie **==** `hash-object --stdin --no-filters` po CRLF→LF z parent (obu plików) |
| Mode z HEAD przy `update-index --cacheinfo` | **YES** `100644`→`100644` (oba) |
| Przed commit: `git diff --cached --name-only` = dokładnie 2 pliki | Spełnione w ETAP 3/4 |

`ACTION_NEEDED: NONE` — rewrite nie jest wymagany.

## Decyzje dla ChatGPT

Brak.
