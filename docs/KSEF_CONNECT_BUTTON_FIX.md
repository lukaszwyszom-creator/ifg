# Fix: przycisk „Połącz KSeF” — natychmiastowy błąd / wielokrotne kliknięcia

**Data:** 2026-05-22  
**Zakres:** `KSeFConnectionTile`, `ksef.js` API, endpoint `POST /api/v1/ksef-sessions/`

---

## Objaw

Kliknięcie „Połącz” w topbarze (`KSeFConnectionTile`) często od razu pokazuje błąd. Po wielokrotnym kliknięciu czasem działa.

---

## Analiza

### Frontend — przycisk połączenia

| Element | Wartość |
|---------|---------|
| Komponent | `frontend-react/src/components/layout/KSeFConnectionTile.jsx` |
| Endpoint connect | `POST /api/v1/ksef-sessions/` (`ksefApi.openSession`) |
| Auth | Axios interceptor w `client.js` — `Authorization: Bearer ${token}` z `useAuthStore` |
| Loading | `ui_status: CONNECTING` + `disabled={status.ui_status === 'CONNECTING'}` |

### Zidentyfikowane problemy (race)

1. **Poll statusu nadpisywał CONNECTING** — `refreshKsefStatus()` (co 30 s, `visibilitychange`, `online`, event `ksef:status-refresh`) wołał `GET /ksef/status` i ustawiał `DISCONNECTED`/`ERROR` **w trakcie** trwającego `openSession`, zanim backend zdążył odpowiedzieć.

2. **Brak synchronicznego guarda przed double-click** — sprawdzenie `status.ui_status === 'CONNECTING'` opierało się na stanie React (async update). Szybkie wielokrotne kliknięcia mogły wysłać **kilka równoległych** `POST /ksef-sessions/`.

3. **HTTP 409 bez obsługi w tile** — pierwszy request tworzył sesję, kolejny dostawał `ConflictError` (409). `KSeFSessionBar` obsługiwał 409 (ładował aktywną sesję), `KSeFConnectionTile` pokazywał błąd mimo że sesja już istniała.

4. **Brak retry na błędy przejściowe** — backend `open_session` woła KSeF auth + `open_online_session`; przy timeout/502/503/504/429 UI od razu pokazywało ERROR bez ponownej próby.

### Backend

| Endpoint | Plik | Uwagi |
|----------|------|-------|
| `POST /ksef-sessions/` | `app/api/routers/ksef_session.py` → `create_session` | alias `open_session` |
| `GET /ksef/status` | `get_ksef_connection_status` | zwraca `DISCONNECTED` gdy brak sesji |
| `GET /ksef-sessions/active` | `get_active_session_v2` | 404 gdy brak sesji |

`KSeFSessionService.open_session`:
- 409 gdy sesja już aktywna
- 502 (`ExternalServiceError`) przy błędzie auth KSeF lub otwarcia sesji online
- wymaga `KSEF_AUTH_TOKEN` w env

Logika backendu **nie zmieniana** — fix tylko po stronie UI/API wrapper.

---

## Wdrożony fix (minimalny)

### `frontend-react/src/api/ksef.js`

- `openSessionOnce(nip)` — deduplikacja równoległych wywołań dla tego samego NIP
- **Jeden retry** po 800 ms przy błędach przejściowych (brak response, 429, 502, 503, 504)
- `ksefApi.openSession` → `openSessionOnce`

### `frontend-react/src/components/layout/KSeFConnectionTile.jsx`

- `actionInFlightRef` — synchroniczny guard (1 klik = 1 akcja)
- `refreshKsefStatus` pomija poll gdy `actionInFlightRef` lub `ui_status === CONNECTING`
- **409** → `getActiveSession` + stan CONNECTED (jak w `KSeFSessionBar`)
- Wydzielone `applyConnectedSession`, `startPurchaseSync` — bez zmiany logiki sync

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `frontend-react/src/api/ksef.js` | dedupe + retry `openSession` |
| `frontend-react/src/components/layout/KSeFConnectionTile.jsx` | guard, skip poll, 409 |
| `frontend-react/src/api/ksef.purchase-sync.test.mjs` | testy regresji źródeł |
| `docs/KSEF_CONNECT_BUTTON_FIX.md` | ten raport |

---

## Ryzyko

| Ryzyko | Ocena |
|--------|-------|
| Retry 429/502 opóźnia connect o ~800 ms | Niskie — tylko przy błędzie przejściowym |
| Dedupe blokuje drugi connect dla tego samego NIP | Zamierzone — zapobiega duplikatom |
| Poll statusu wstrzymany max czas trwania connect | Akceptowalne — krótki okno |
| Backend auth nadal może failować trwale (zły token) | Bez zmian — użytkownik widzi komunikat z API |

---

## Test lokalnie

```bash
cd frontend-react
npm run dev   # lub istniejący bootstrap

# testy statyczne źródeł
node --test src/api/ksef.purchase-sync.test.mjs
```

**Manualnie:**
1. Zaloguj się, otwórz dashboard z topbarem KSeF.
2. Kliknij „Połącz” **raz** — przycisk od razu disabled, label „łączenie...”.
3. Szybko kliknij 5× — tylko jeden request w Network (`POST .../ksef-sessions/`).
4. Po sukcesie: zielona kropka „połączony”.
5. Jeśli sesja już istnieje (409): UI przechodzi na CONNECTED bez błędu.

---

## Test na DS723+

```bash
# rebuild frontend + api (frontend montowany do kontenera)
docker compose -f docker/docker-compose.prod.yml up -d --build api

# logi backendu przy connect
docker compose -f docker/docker-compose.prod.yml logs -f api | grep -i ksef
```

W przeglądarce: DevTools → Network — jeden `POST /api/v1/ksef-sessions/` na kliknięcie, header `Authorization` obecny.

---

## Krótki diff (idea)

```diff
# ksef.js
+ openSessionOnce() — in-flight dedupe + 1× retry transient
- openSession: client.post(...)
+ openSession: (nip) => openSessionOnce(nip)

# KSeFConnectionTile.jsx
+ actionInFlightRef, skip poll during CONNECTING
+ handle 409 → getActiveSession → CONNECTED
+ disabled via CONNECTING (bez zmian)
```
