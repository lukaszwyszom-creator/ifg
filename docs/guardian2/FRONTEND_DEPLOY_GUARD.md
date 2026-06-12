# Frontend deploy guard — ochrona przed starym dist

**Data:** 2026-05-22  
**Kontekst:** incydent po `9abc884` — poprawny `src/`, stary `dist/` na DS723+

---

## Cel

Zablokować wdrożenie, w którym `frontend-react/src` zawiera nowszy kod niż zbudowany `frontend-react/dist`.

---

## Zmiany

| Plik | Zmiana |
|------|--------|
| `docs/DS723_DEPLOYMENT_CHECKLIST.md` | Obowiązkowy krok `npm ci && npm run build` przed `docker compose up --force-recreate api worker` |
| `docs/GUARDIAN2_DEPLOY.md` | Ostrzeżenie: rebuild API/worker **nie** wdraża zmian UI; wymagany build dist |
| `scripts/guardian.py` | Automatyczna walidacja świeżości dist vs ostatni commit w `frontend-react/src` |

---

## Automatyczna walidacja (`guardian.py`)

Funkcje: `check_frontend_dist_freshness()`, `check_remote_frontend_dist_freshness()`.

**Reguła:** porównaj timestamp ostatniego commita dotykającego `frontend-react/src/` z mtime najnowszego `dist/assets/*.js`.

**Błąd:**
```
Frontend dist wymaga przebudowy (npm run build).
```

**Wywołania:**
- `python3 scripts/guardian.py --ksef-async-check` — lokalnie
- `python3 scripts/guardian.py --deploy-check` — lokalnie + DS723+ (SSH)

Werdykt `--deploy-check` wymaga świeżego dist (Mac mini i zdalnie, jeśli SSH działa).

---

## Procedura deploy (DS723+)

```bash
cd frontend-react && npm ci && npm run build && cd ..
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --build --force-recreate api worker
python3 scripts/guardian.py --ksef-async-check
python3 scripts/guardian.py --deploy-check
```

Restart API po samym rebuild dist **nie jest wymagany** (volume mount).

---

## Powiązane dokumenty

- `docs/guardian2/FRONTEND_DIST_DEPLOY_VALIDATION.md`
- `docs/guardian2/PURCHASE_UI_NUMBERING_PRODUCTION_ANALYSIS.md`
