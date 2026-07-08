# GWO-IFG-0042 — Transmissions HTTP500 Traceback & Fix

**Data:** 2026-07-08  
**Zakres:** backend `GET /api/v1/transmissions/`  
**Wykonanie:** reprodukcja 500, traceback, fix minimalny, testy, weryfikacja endpointu

---

## 1) Reprodukcja requestu

Request odtworzony dla endpointu:

`GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=false`

### Wynik reprodukcji

- z tokenem poprawnym (`sub=<UUID użytkownika>`) -> **HTTP 200**
- z tokenem legacy (`sub="admin"`, poprawnie podpisany JWT, ale `sub` nie jest UUID) -> **HTTP 500**

---

## 2) Pełny traceback (z runtime odpowiedzi API)

```
Traceback (most recent call last):
  ...
  File "/app/app/api/deps.py", line 200, in get_current_user
    return auth_service.get_authenticated_user(credentials.credentials)
  File "/app/app/services/auth_service.py", line 48, in get_authenticated_user
    user = self.user_repository.get_by_id(UUID(user_id))
  File "/usr/local/lib/python3.13/uuid.py", line 181, in __init__
    raise ValueError('badly formed hexadecimal UUID string')
ValueError: badly formed hexadecimal UUID string
```

---

## 3) Miejsce wyjątku (plik / funkcja / linia)

- **Plik:** `app/services/auth_service.py`
- **Funkcja:** `get_authenticated_user`
- **Linia (traceback):** `48` (`UUID(user_id)`)

Ścieżka wejścia:

- `app/api/deps.py` -> `get_current_user` -> `auth_service.get_authenticated_user(...)`

---

## 4) Root cause

Kod zakłada, że claim JWT `sub` zawsze jest UUID użytkownika.

Dla tokenu legacy (lub uszkodzonego), gdzie `sub` ma wartość tekstową nie-UUID (np. `admin`):

1. JWT przechodzi decode (podpis OK),
2. `UUID(user_id)` rzuca `ValueError`,
3. wyjątek nie jest mapowany na `UnauthorizedError`,
4. kończy się **HTTP 500** zamiast kontrolowanego **401**.

---

## 5) Minimalna poprawka

Zmieniono `get_authenticated_user` w `app/services/auth_service.py`:

- dodano bezpieczną walidację `UUID(str(user_id))` w `try/except`,
- `ValueError/TypeError/AttributeError` mapowane na:
  - `UnauthorizedError("Nieprawidlowy token dostepu.")`

Efekt:

- brak nieobsłużonego wyjątku `ValueError`,
- dla tokenu z nieprawidłowym `sub` endpoint zwraca **401**, nie 500.

Dodatkowo dodano test regresyjny:

- `tests/unit/test_auth_service.py`
  - `test_invalid_subject_uuid_raises`

---

## 6) Testy

Uruchomione:

```bash
.venv/bin/python -m pytest tests/unit/test_transmission_api.py tests/unit/test_transmission_service.py tests/unit/test_auth_service.py
```

Wynik:

- **54 passed**
- `test_transmission_api.py` -> PASS
- `test_transmission_service.py` -> PASS
- `test_auth_service.py` -> PASS (w tym nowy test regresyjny)

---

## 7) Weryfikacja endpointu `GET /api/v1/transmissions/`

Weryfikacja runtime requestu:

- `GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=false`
- z poprawnym tokenem -> **HTTP 200** + poprawny JSON (`items`, `total`, `page`, `size`)

Weryfikacja scenariusza awarii:

- token z `sub` nie-UUID:
  - przed fixem -> **500**
  - po fixie (pokryte testem jednostkowym) -> **401 Unauthorized**

---

## 8) Weryfikacja Monitora KSeF

Ponieważ Monitor KSeF konsumuje dokładnie endpoint:

`GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=false`

i endpoint zwraca 200 dla poprawnej sesji, backend nie blokuje już widoku przez ten typ 500.

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Zidentyfikowano i odtworzono backendowy HTTP500.
- Uzyskano pełny traceback z plikiem/funkcją/linią.
- Wprowadzono minimalny fix mapujący legacy `sub` -> 401 zamiast 500.
- Testy transmisji + auth: **54/54 PASS**.
- Request transmisji z poprawnym tokenem zwraca **HTTP 200**.

### ⚠️ Znane problemy

- Running container może wymagać standardowego cyklu deploy/restart, aby odebrać fix z repo.

### ❌ Co nie działa

- Brak.

---

## A. ROOT CAUSE

Nieobsłużony `ValueError` przy konwersji `JWT.sub` do UUID w `AuthService.get_authenticated_user`.

## B. Zmienione pliki

- `app/services/auth_service.py`
- `tests/unit/test_auth_service.py`

## C. Deploy

Nie wykonywano deployu produkcyjnego w tym zadaniu.

## D. Testy

`pytest` dla transmisji + auth: 54 passed.

## E. Następny krok

Wykonać standardowy deploy backendu z tym patchem i potwierdzić w runtime, że token legacy zwraca 401 (bez 500) oraz Monitor KSeF ładuje dane przy poprawnej sesji.

---

## Pre-deploy JWT source verification

### 1) Czy był to stary token zapisany w LocalStorage przeglądarki?

**Najbardziej prawdopodobnie: tak.**

Dowody:

- frontend przechowuje token trwale w store `zustand/persist` pod kluczem `faktura-auth` (`frontend-react/src/store/useAuthStore.js`);
- bez jawnego `logout` token jest używany w kolejnych requestach (`frontend-react/src/api/client.js` dodaje `Authorization: Bearer <token>` z tego store).

To dokładnie pasuje do scenariusza „stara sesja po zmianie kontraktu tokenu”.

### 2) Czy backend nadal generuje tokeny legacy?

**Nie (w aktualnym backendzie).**

W jedynym miejscu emisji JWT (`app/services/auth_service.py`) token jest generowany:

- `subject=str(user.id)` -> `sub` jest UUID użytkownika,
- dodatkowe claims: `username`, `role`.

Brak innej ścieżki tworzenia tokenu auth z `sub=username`.

### 3) Czy po ponownym logowaniu nowy JWT zawiera UUID w `sub`?

**Tak.**

Z konstrukcji `login()` wynika jednoznacznie, że świeżo wystawiony JWT ma:

- `sub = str(user.id)` (UUID),
- nie `sub = username`.

### 4) Czy użytkownik musi tylko wykonać wylogowanie/logowanie?

**Tak — to właściwa akcja operacyjna dla sesji legacy.**

Ponowne logowanie odświeża token w `faktura-auth` i zastępuje stary JWT nowym (z UUID w `sub`).

### 5) Czy fix GWO-IFG-0042 wystarcza jako zabezpieczenie przed HTTP500 dla legacy/uszkodzonych tokenów?

**Tak.**

Fix mapuje nieprawidłowy `sub` (nie-UUID) na kontrolowane `UnauthorizedError`:

- wynik: **401** zamiast **500**,
- backend nie wywraca się na tokenach legacy/uszkodzonych.

Uwaga operacyjna:

- fix nie „naprawia” starego tokenu, ale skutecznie eliminuje HTTP500 i zamienia go na poprawny semantycznie 401.

