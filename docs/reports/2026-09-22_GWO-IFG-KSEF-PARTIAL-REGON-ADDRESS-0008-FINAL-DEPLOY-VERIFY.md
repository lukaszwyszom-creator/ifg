# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0008 — FINAL DEPLOY VERIFY

**Data:** 2026-09-22  
**Cel:** Deploy `e0a53b0` (KSeF partial REGON / AdresL1) na DS723 + weryfikacja health / smoke (bez wysyłki KSeF).

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [x] DEPLOYED_TO_DS723
- [x] PRODUCTION_VERIFIED

## STATUS KOŃCOWY (syntetyczny)

| Pole | Wartość |
|------|---------|
| DEPLOY_RESULT | SUCCESS |
| EXPECTED_SHA | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| PREVIOUS_SHA | `40e6445b59dced074c76aa2b62d450aa36bb38da` |
| DEPLOYED_SHA | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| COSMETICS | EOL-only (`git diff --ignore-cr-at-eol` pusty) — kontynuacja dozwolona |
| ORIGIN_PRODUCTION | = EXPECTED (Mac) |
| FRONTEND_BUILD | PASS (`npm run build` + tar sync dist) |
| GIT_PULL_DS723 | PASS `40e6445..e0a53b0` (bez force) |
| DOCKER_API_REBUILD | PASS |
| ALEMBIC | no-op / head (brak nowych migracji) |
| HEALTH | PASS (`status: ok`, api+worker+db healthy) |
| WORKER | UP / healthy |
| FRONTEND_DIST | `frontend-react/dist/index.html` OK |
| KSEF_CONFIG | `ENABLE_KSEF=true` w kontenerze; `KSEF_AUTH` lines=2 (bez dump sekretów) |
| FEATURE_SMOKE | PASS (`SMOKE_OK`, `MAPPER_DRY_OK`) |
| PURCHASE_SYNC_ANCESTOR | `40e6445` is-ancestor HEAD → ANCESTOR_OK |
| ROLLBACK | NIE wymagany |

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Deploy non-interactive: `yes \| SKIP_TESTS=1 bash scripts/deploy-ds723.sh` (po wcześniejszym lokalnym smoke KSeF).
- DS723 HEAD = EXPECTED `e0a53b0`.
- Kontenery `api`, `worker`, `db` — healthy; `GET /health` → `status: ok`.
- Feature AdresL1: wieś bez ulicy (`Prusicko 10, 98-420 Prusicko`); mapper `_format_adres_l1` zgodny; przypadki niedostateczne blokowane.
- Regresja purchase sync: `40e6445` jest przodkiem HEAD.

⚠️ Znane problemy
- Mac working tree brudny (docs/guardian/tests) — deploy kontynuowany świadomie (skrypt pytał; `yes`).
- Na DS723 kosmetyczny dirty EOL w `docs/_archiwum/migracja_mac_mini.md` + untracked bak/backups/logs (operacyjne).
- Przy healthcheck zaraz po `up` kontenery były jeszcze `health: starting`; po ~1 min — healthy (OK).

❌ Co nie działa
- Brak.

### A. Root cause
N/A — planowy deploy feature na production DS723.

### B. Zmienione pliki
- Na Mac: brak commitów w tym GWO-0008 (tylko build dist + deploy).
- Na DS723: `git pull` `40e6445` → `e0a53b0`; rebuild image `ifg-api:latest`; sync `frontend-react/dist/`.
- Raport: ten plik.

### C. Deploy
- Skrypt: `scripts/deploy-ds723.sh` (`SKIP_TESTS=1`, stdin `yes`).
- Lokalny smoke przed deploy: `pytest tests/unit/test_ksef_partial_regon_address.py -q` → **16 passed**.
- Frontend: Vite build na Mac + tar|ssh do NAS.
- Backend: `docker compose … build api` + `up -d --remove-orphans api worker`.
- DB: `alembic upgrade head` (bez nowych migracji).

### D. Testy / dowody

**Lokalnie (przed deploy):**
```
16 passed in 0.24s  # test_ksef_partial_regon_address.py
```

**DS723 HEAD / ancestor:**
```
e0a53b0bf673f2243fca90d522edf999622224ae
ANCESTOR_OK  # merge-base --is-ancestor 40e6445 HEAD
```

**Health:**
```json
{"status":"ok","environment":"production","regon":{"configured":true}}
```
Containers: api/worker/db healthy; dist index present.

**Feature smoke (api container, bez KSeF send):**
```
ADRESL1 Prusicko 10, 98-420 Prusicko
SMOKE_OK
MAPPER_DRY_OK
```

**KSeF config (bez sekretów):** `ENABLE_KSEF=true`; `KSEF_AUTH` occurrences=2.

### E. Następny krok
- Opcjonalnie: produkcyjny smoke UI faktury z częściowym adresem REGON (bez wysyłki KSeF).
- Cleanup operacyjny na DS723: bak/logs poza ścieżką krytyczną (nie blokuje).

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0008-FINAL-DEPLOY-VERIFY.md`
