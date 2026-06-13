# Guardian — kontrola buildu frontend-react po zmianach src

**Data:** 2026-05-22  
**Kontekst:** `KSEF_CONNECT_BUTTON_FIX.md` — fix connect miał być w src, ale nie trafił na `production` / do `dist`.

---

## Stan fixu connect (audyt)

| Marker | `frontend-react/src` (working tree) | `production` HEAD | `frontend-react/dist` |
|--------|-------------------------------------|-------------------|------------------------|
| `openSessionOnce` w `ksef.js` | ✅ | ❌ | ❌ |
| `actionInFlightRef` w `KSeFConnectionTile.jsx` | ✅ | ❌ | ❌ |
| obsługa `409` w tile | ✅ | ❌ | ❌ |

**Wniosek:** fix jest **tylko lokalnie (niezcommitowany)**. Gałąź `production` @ `0133c7c` **nie zawiera** connect fix. Bundle produkcyjny (`dist/assets/*.js`) **nie zawiera** markerów fix.

Ostatni commit dotykający tych plików: `ef23258` (sync trigger), **przed** connect fix.

---

## Co Guardian robił wcześniej

| Check | Plik | Zachowanie |
|-------|------|------------|
| commit src vs dist mtime | `guardian.py` → `check_frontend_dist_freshness()` | Porównuje timestamp ostatniego commita w `frontend-react/src` z `mtime` plików `dist/assets/*.js` |
| deploy-check | `run_deploy_check()` | Blokuje deploy gdy dist lokalnie/DS723+ starszy niż commit src |
| ksef-async-check | `run_ksef_async_check()` | `runPurchaseSync` w dist, brak `syncPurchasesNow` |
| Guardian2 deploy | `guardian2.py` | `npm ci && npm run build` lokalnie i na DS723+ |

**Luka:** check commit-vs-dist **nie widzi niezcommitowanych zmian** w `frontend-react/src`. Dist mógł być „świeży” względem ostatniego commita, ale **bez** aktualnego kodu z working tree — stąd fałszywe OK.

**Luka 2:** brak weryfikacji markerów `KSEF_CONNECT_BUTTON_FIX` w bundle.

**Luka 3:** `KSeFConnectionTile.jsx` nie był w allowliście `guardian2.py` DEPLOY_ALLOWLIST.

---

## Wdrożone uzupełnienia (minimalne)

### `scripts/guardian.py`

1. **`check_frontend_worktree_requires_build()`** — jeśli `git status` pokazuje zmiany w `frontend-react/src`, `dist` musi być nowszy niż najnowszy `mtime` zmienionego pliku. Blokuje `--ksef-async-check` i `--deploy-check`.

2. **`check_ksef_connect_button_fix()`** — weryfikuje markery w src i dist:
   - `ksef.js`: `openSessionOnce`
   - `KSeFConnectionTile.jsx`: `actionInFlightRef`, `409`
   - `dist/assets/*.js`: obecność `openSessionOnce` / `actionInFlightRef` w bundle

### `scripts/guardian2.py`

- Allowlist deploy: `KSeFConnectionTile.jsx`, `docs/KSEF_CONNECT_BUTTON_FIX.md`, `docs/GUARDIAN_FRONTEND_BUILD_CHECK.md`
- Flow bez zmian: lokalnie `npm run build` → remote `npm run build` → `guardian --ksef-async-check`

---

## Komendy weryfikacji

```bash
# pełny check KSeF (powinien FAIL dopóki brak commit + build)
python3 scripts/guardian.py --ksef-async-check

# deploy readiness
python3 scripts/guardian.py --deploy-check

# po commit + build powinno przejść:
cd frontend-react && npm run build
python3 scripts/guardian.py --ksef-async-check
```

---

## Co zrobić, żeby fix był na DS723+

```bash
git add frontend-react/src/api/ksef.js \
        frontend-react/src/components/layout/KSeFConnectionTile.jsx \
        frontend-react/src/api/ksef.purchase-sync.test.mjs \
        docs/KSEF_CONNECT_BUTTON_FIX.md \
        scripts/guardian.py scripts/guardian2.py \
        docs/GUARDIAN_FRONTEND_BUILD_CHECK.md
cd frontend-react && npm run build && cd ..
git add frontend-react/dist
git commit -m "fix(ksef): connect button race guard and single retry"
python3 scripts/guardian.py --ksef-async-check   # oczekiwane: OK
python3 scripts/guardian2.py deploy-ksef --yes     # lub ręczny deploy
```

---

## Ryzyko

| Ryzyko | Ocena |
|--------|-------|
| Fałszywy FAIL gdy dist zbudowany przed zapisem pliku src | Niskie — porównanie mtime |
| Minifikacja usuwa nazwy `openSessionOnce` z dist | Średnie — sprawdzamy też `actionInFlightRef`; po build Vite nazwy często zostają w chunkach; jeśli FAIL fałszywy → dodać hash commita |
| Guardian2 allowlist wymaga ręcznego dopisywania plików | Zamierzone — kontrolowany deploy |
