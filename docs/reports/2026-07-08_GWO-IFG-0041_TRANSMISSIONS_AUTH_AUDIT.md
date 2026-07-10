# GWO-IFG-0041 — Audyt autoryzacji endpointu `GET /api/v1/transmissions/`

**Data:** 2026-07-08  
**Zakres:** wyłącznie autoryzacja endpointu `GET /api/v1/transmissions/`  
**Tryb:** read-only (bez zmian kodu)

---

## 1. Dependency FastAPI podpięte do endpointu transmissions

Endpoint:

- `app/api/routers/transmissions.py`
- funkcja: `list_transmissions(...)`
- podpis dependencies:
  - `transmission_service: Depends(get_transmission_service)`
  - `_ : Depends(get_current_user)`

Czyli autoryzacja jest realizowana przez `get_current_user`.

---

## 2. Porównanie z działającym endpointem listy faktur

Endpoint referencyjny:

- `app/api/routers/invoices.py`
- funkcja: `list_invoices(...)`
- podpis dependencies:
  - `invoice_service: Depends(get_invoice_service)`
  - `_ : Depends(get_current_user)`

**Wniosek:** mechanizm autoryzacji dla `GET /api/v1/transmissions/` i `GET /api/v1/invoices/` jest **identyczny** (`Depends(get_current_user)`).

Brak różnicy w konfiguracji dependency, która sama w sobie tłumaczyłaby odmienny status auth.

---

## 3. Pełna ścieżka autoryzacji (Authorization -> JWT -> DI -> 401)

### Krok A: Authorization header

`get_current_user` korzysta z:

- `http_bearer = HTTPBearer(auto_error=False)`
- `credentials: Depends(http_bearer)`

Efekt:

- jeśli nagłówek `Authorization: Bearer ...` nie istnieje lub nie jest poprawnym Bearer credentials, `credentials` będzie `None` (zamiast automatycznego wyjątku FastAPI).

### Krok B: get_current_user

Plik: `app/api/deps.py`

1. `if credentials is None:`
2. `raise UnauthorizedError("Brak tokenu dostepu.")`
3. w przeciwnym razie: `auth_service.get_authenticated_user(credentials.credentials)`

### Krok C: JWT decode

Plik: `app/services/auth_service.py`, `get_authenticated_user(token)`

1. `payload = decode_access_token(token)`
2. `user_id = payload["sub"]`
3. wyjątek dekodowania/parsowania -> `UnauthorizedError("Nieprawidlowy token dostepu.")`

`decode_access_token`:

- plik `app/core/security.py`
- `jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])`

To obejmuje m.in. błędny podpis, zły algorytm, wygasły token (`exp`) i nieprawidłowy format.

### Krok D: weryfikacja użytkownika

Po poprawnym decode:

1. `user = user_repository.get_by_id(UUID(user_id))`
2. `if user is None or not user.is_active:`
3. `raise UnauthorizedError("Uzytkownik nie istnieje lub jest nieaktywny.")`

### Krok E: mapowanie wyjątku na HTTP 401

Plik: `app/core/exceptions.py`

- `UnauthorizedError.status_code = 401`
- globalny handler `AppError` zwraca:
  - `status_code=401`
  - body: `{"error":{"code":"unauthorized","message":"..."}}`

---

## 4. Dokładne miejsca kodu generujące 401 dla tego endpointu

### Bezpośrednie źródła 401

1. `app/api/deps.py` — `get_current_user(...)`
   - `raise UnauthorizedError("Brak tokenu dostepu.")`
2. `app/services/auth_service.py` — `get_authenticated_user(...)`
   - `raise UnauthorizedError("Nieprawidlowy token dostepu.")`
   - `raise UnauthorizedError("Uzytkownik nie istnieje lub jest nieaktywny.")`

### Linia odpowiedzi HTTP

3. `app/core/exceptions.py` — handler `AppError`
   - `JSONResponse(status_code=exc.status_code, ...)`
   - dla `UnauthorizedError` jest to 401.

---

## 5. Permission check

Dla `GET /api/v1/transmissions/` nie ma dodatkowego RBAC (np. rola admin/user) po `get_current_user`.

Czyli jedyny warunek dostępu to poprawna autentykacja użytkownika.

---

## 6. Ustalenie przyczyny (kategorie zlecone)

Na podstawie ścieżki kodu 401 dla tego endpointu może powstać wyłącznie z:

1. **Brak nagłówka** `Authorization` -> `Brak tokenu dostepu.`
2. **Błędny token** (format/podpis/exp/claims) -> `Nieprawidlowy token dostepu.`
3. **Token poprawny kryptograficznie, ale user nie istnieje lub nieaktywny** -> `Uzytkownik nie istnieje lub jest nieaktywny.`

Nie stwierdzono:

- błędnej konfiguracji endpointu transmissions względem invoices,
- różnicy w dependency dla auth między transmissions a invoices.

---

## 7. Root cause (audyt autoryzacji)

**Root cause po stronie kodu autoryzacji:** brak dedykowanego problemu w konfiguracji `GET /api/v1/transmissions/`; endpoint używa tego samego `get_current_user` co działające listowanie faktur.

**Przyczyna 401 musi pochodzić z danych runtime auth** (header/token/user-state), a nie z różnicy endpoint configuration.

---

## 8. Minimalna poprawka

Minimalna poprawka operacyjno-diagnostyczna (bez zmiany logiki auth):

1. Logować w `get_current_user` rozróżnienie przyczyny 401 (missing header vs invalid token vs inactive user) z `request_id` i bez ujawniania tokenu.
2. Dodać endpoint-level audit metric dla `unauthorized_reason`.

Minimalna poprawka produktowa (opcjonalna):

3. Zwracać różne `error.code` dla:
   - `missing_token`
   - `invalid_token`
   - `inactive_user`

To pozwoli jednoznacznie diagnozować 401 aktywnej sesji bez zgadywania.

