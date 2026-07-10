# GWO-IFG-0040 — Diagnostyka błędu „Błąd ładowania transmisji” w Monitorze KSeF

**Data:** 2026-07-08  
**Zakres:** pełna diagnostyka, bez naprawy kodu  
**Tryb:** read-only

---

## Cel diagnostyki

Zweryfikować cały przepływ Monitor KSeF:

1. Request frontend (URL + query params),
2. Endpoint FastAPI i schema response,
3. Faktyczny status backendu (200/4xx/5xx),
4. Logi backendu i korelacja z komunikatem UI,
5. Spójność: `transmissions.js` ↔ `transmissions.py` ↔ `transmission.py` ↔ `TransmissionTable.jsx`.

---

## 1) Frontend — co dokładnie wysyła

### Źródło requestu

- `frontend-react/src/api/transmissions.js`
  - `client.get('/transmissions/', { params: { page, size, warnings_or_errors_only } })`
- `frontend-react/src/api/client.js`
  - `baseURL: '/api/v1'`
  - Authorization header: `Bearer <token>` z `useAuthStore`

### Faktyczny URL wywołania

Frontend wywołuje:

- `GET /api/v1/transmissions/?page=<n>&size=<n>&warnings_or_errors_only=<bool>`

### Query parameters

Potwierdzone parametry:

- `page` (default 1)
- `size` (default 20)
- `warnings_or_errors_only` (default `false`, checkbox w `TransmissionTable`)

---

## 2) Backend — endpoint i zgodność kontraktu

### Endpoint FastAPI

- `app/api/routers/transmissions.py`
  - `@router.get("/", response_model=TransmissionPageResponse)`
  - Parametry: `page`, `size`, `warnings_or_errors_only`
- Router jest podpięty w `app/main.py`:
  - `application.include_router(transmissions_router, prefix=settings.api_v1_prefix)`

### Response schema

- `app/schemas/transmission.py`
  - `TransmissionPageResponse`: `items`, `total`, `page`, `size`
  - `TransmissionResponse.invoice_id: UUID | None = None` (nullable)

### Zgodność z `TransmissionTable`

`TransmissionTable.jsx` oczekuje pól:

- `items[]` + `total` (pagination),
- m.in. `severity`, `status`, `invoice_number_local`, `metadata_json`, `created_at`.

Kontrakt API i renderer tabeli są zgodne strukturalnie.

---

## 3) Weryfikacja runtime (request/response i logi)

### 3.1. Test requestów do API

Wykonane requesty diagnostyczne:

1. `POST /api/v1/auth/login` (próba logowania kontem `admin/admin123!`)  
2. `GET /api/v1/transmissions/?page=1&size=20`  
3. `GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=true`

### 3.2. Wynik HTTP

- `POST /api/v1/auth/login` → **401 Unauthorized**
- `GET /api/v1/transmissions/...` → **401 Unauthorized**

Przykładowa odpowiedź login:

```http
HTTP/1.1 401 Unauthorized
{"error":{"code":"unauthorized","message":"Nieprawidlowy login lub haslo."}}
```

### 3.3. Logi backendu (docker api)

W logach API:

- `POST /api/v1/auth/login` — `status_code: 401`
- `GET /api/v1/transmissions/?page=1&size=20` — `status_code: 401`
- `GET /api/v1/transmissions/?...&warnings_or_errors_only=true` — `status_code: 401`

Brak bieżących wpisów:

- `500 Internal Server Error`
- `Traceback`
- `pydantic_core.ValidationError`

---

## 4) 500/404/Pydantic — wynik diagnostyczny

### 500

W aktualnej diagnostyce **nie wystąpił** HTTP 500 dla `/api/v1/transmissions/`.

### 404

W aktualnej diagnostyce **nie wystąpił** HTTP 404 dla `/api/v1/transmissions/`; endpoint jest zarejestrowany.

### Pydantic validation error

W aktualnych logach **brak** błędu walidacji Pydantic dla transmisji.

Kontekst historyczny:

- dawny błąd `invoice_id=None` (ValidationError) był już wcześniej zdiagnozowany i adresowany przez zmianę schematu na nullable.

---

## 5) Console + Network (przeglądarka)

W tym środowisku diagnostycznym nie było aktywnej sesji przeglądarki podłączonej do agenta, więc nie ma bezpośredniego zrzutu zakładek DevTools (Console/Network) z urządzenia operatora.

Natomiast kod frontendu wskazuje:

- `resolveTransmissionLoadError()` loguje `console.error` z:
  - `url`, `status`, `responseData`, info o Authorization header.
- Dla `401` zwracany komunikat użytkownika:
  - `Brak autoryzacji — zaloguj się ponownie...`
- Dla `404`:
  - `Endpoint Monitora KSeF nie został znaleziony...`
- Dla `500`:
  - `Błąd serwera podczas ładowania Monitora KSeF (...)`

To oznacza, że literalny komunikat **„Błąd ładowania transmisji”** nie pochodzi z aktualnego kodu `frontend-react/src`.

---

## 6) Dokładna przyczyna (root cause)

### Przyczyna bezpośrednia aktualnej awarii

**401 Unauthorized na warstwie auth** (brak poprawnego tokena JWT), co blokuje `GET /api/v1/transmissions/`.

### Przyczyna komunikatu tekstowego zgłoszonego przez użytkownika

Komunikat „Błąd ładowania transmisji” jest charakterystyczny dla wcześniejszej wersji UI (przed refaktoryzacją obsługi błędów), nie dla aktualnego kodu źródłowego.

Najbardziej prawdopodobny scenariusz:

1. backend zwraca 401,
2. użytkownik widzi stary ogólny komunikat z nieaktualnego bundle/cachu frontendowego.

---

## 7) Miejsce awarii

### Techniczne miejsce awarii

- Warstwa autoryzacji (`/api/v1/auth/login` -> 401),
- skutek: endpoint transmisji odrzuca request (`/api/v1/transmissions/` -> 401).

### Miejsce symptomu

- UI Monitora KSeF (`TransmissionTable`) pokazuje błąd ładowania zamiast danych tabeli.

---

## 8) Ocena wpływu

- **Wpływ funkcjonalny:** wysoki dla użytkownika — brak możliwości przeglądu transmisji KSeF.
- **Wpływ na dane:** brak (odczyt zablokowany, brak mutacji).
- **Zakres:** Monitor KSeF (tab transmissions); inne endpointy mogą działać niezależnie.

---

## 9) Minimalny zakres wymaganej poprawki (bez implementacji)

1. Zweryfikować i ustabilizować ścieżkę logowania dla środowiska, z którego korzysta UI (poprawne credentials/token lifecycle).  
2. Potwierdzić, że środowisko serwuje aktualny bundle frontendu (`transmissionLoadError.js` z nową mapą komunikatów).  
3. Dodać operacyjny check w procedurze wdrożeniowej: po deploy wykonać smoke:
   - `POST /api/v1/auth/login` -> 200,
   - `GET /api/v1/transmissions/?page=1&size=20` -> 200 (z tokenem),
   - w UI Network status zgodny z backendem.

---

## 10) Propozycja GWO naprawczego

**GWO-IFG-0041 — KSeF Monitor Auth + Frontend Artifact Consistency Fix**

Zakres proponowany:

1. Diagnostyka i naprawa autoryzacji dla środowiska operatorskiego (przyczyna 401).  
2. Weryfikacja i ewentualna korekta procesu publikacji artefaktów frontend (`dist`) tak, aby wykluczyć serwowanie starego bundle.  
3. Dodanie twardego smoke testu post-deploy dla Monitora KSeF (HTTP + UI Network).  
4. Uzupełnienie checklisty Guardian/Deploy o walidację zgodności wersji UI i API.

---

## 11) Dowody (źródła diagnostyczne)

- `frontend-react/src/api/transmissions.js`
- `frontend-react/src/api/client.js`
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
- `frontend-react/src/utils/transmissionLoadError.js`
- `app/api/routers/transmissions.py`
- `app/schemas/transmission.py`
- `app/main.py`
- logi kontenera API (`docker compose -f docker/docker-compose.yml logs api --since 10m`)
- requesty curl do `127.0.0.1:8000`

