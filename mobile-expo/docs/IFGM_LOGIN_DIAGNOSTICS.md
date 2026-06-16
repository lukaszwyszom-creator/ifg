# IFGM — diagnostyka logowania (iPhone / Expo Go)

**Data:** 2026-05-22  
**Rola:** G2 — architekt wdrożenia / audytor operacyjny  
**Objaw:** Safari i curl działają; IFGM pokazuje *„Nie udało się zalogować. Sprawdź połączenie z serwerem.”*  
**Zakres:** analiza bez zmian w kodzie

---

## 1. Mapowanie komunikatu błędu

Komunikat pochodzi wyłącznie z `mobile-expo/src/api/auth.ts` (`LOGIN_FAILED_MSG`), gdy:

- request **nie** zwrócił `AuthError` (401 → wtedy byłoby *„Nieprawidłowy login lub hasło”*),
- błąd **nie** zawiera słów: `cloudflare`, `html zamiast json`, `login`, `hasło`, `401`.

Typowe scenariusze prowadzące do tego komunikatu:

| Przyczyna | HTTP / sieć | Komunikat użytkownika |
|-----------|-------------|------------------------|
| Zły URL (np. podwójne `/api/v1`) | 404 Not Found | **Połączenie z serwerem** |
| Backend 5xx | 500 | **Połączenie z serwerem** |
| Sieć / timeout / odmowa | fetch reject | **Połączenie z serwerem** |
| Fallback `127.0.0.1` na iPhone | connection refused | **Połączenie z serwerem** |
| Błędne hasło | 401 | *Nieprawidłowy login lub hasło* |
| Cloudflare Access | 302 / HTML | komunikat o Cloudflare |
| Brak `access_token` w JSON 200 | — | *Nieprawidłowy login lub hasło* |

**Wniosek:** skoro użytkownik widzi *„Sprawdź połączenie z serwerem”*, a nie *„Nieprawidłowy login”*, problem leży **po stronie URL / odpowiedzi HTTP / sieci fetch**, a nie w samych danych logowania (te same dane działają w curl).

---

## 2. Analiza możliwych przyczyn (z priorytetem)

### P0 — najbardziej prawdopodobne

#### P0-1: Podwójne `/api/v1` w URL logowania

**Dowód w repo:**

`mobile-expo/app.json`:
```json
"apiBaseUrl": "http://100.87.84.118:8000/api/v1"
```

`mobile-expo/src/api/config.ts` — `getApiBaseUrl()` zwraca bazę **bez** `/api/v1`.  
`mobile-expo/src/api/client.ts` — dokleja `API_V1_PREFIX` (`/api/v1`):

```
{getApiBaseUrl()} + /api/v1 + /auth/login
```

Gdy **nie** ustawiono `EXPO_PUBLIC_API_BASE_URL` przy starcie Metro, aplikacja woła:

```
http://100.87.84.118:8000/api/v1/api/v1/auth/login   ← BŁĘDNY URL
```

curl użytkownika trafia w poprawny adres:

```
http://100.87.84.118:8000/api/v1/auth/login        ← POPRAWNY
```

Safari `/health` nie używa prefiksu API — dlatego działa mimo błędnej konfiguracji mobile.

**Weryfikacja (Mac mini):**
```bash
# Powinno FAIL (404 lub HTML)
curl -i -X POST http://100.87.84.118:8000/api/v1/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}'

# Powinno OK (200 + access_token)
curl -s -X POST http://100.87.84.118:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}' | jq .
```

#### P0-2: `EXPO_PUBLIC_API_BASE_URL` nie ustawione przy `expo start`

Priorytet w `config.ts`:
1. `EXPO_PUBLIC_API_BASE_URL` (env przy starcie Metro)
2. `app.json` → `extra.apiBaseUrl` ← obecnie z **błędnym** `/api/v1`
3. fallback `http://127.0.0.1:8000`

Jeśli Expo uruchomiono jako `npx expo start` **bez** prefiksu env, aplikacja używa P0-1.

Jeśli env ustawiono **z** sufiksem `/api/v1`:
```bash
EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000/api/v1 npx expo start
```
— efekt identyczny (podwójny prefix).

**Poprawny format env (bez `/api/v1`):**
```bash
EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000 npx expo start
```

---

### P1 — średnio prawdopodobne

#### P1-1: Stary bundle Metro / cache Expo

Metro wbudowuje `process.env.EXPO_PUBLIC_*` w **momencie startu**. Zmiana env bez restartu lub stary cache → aplikacja nadal używa poprzedniej bazy (np. `127.0.0.1`).

**Objaw:** Safari/Tailscale OK, app woła localhost telefonu.

**Weryfikacja:** restart z czyszczeniem cache:
```bash
cd mobile-expo
EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000 npx expo start -c
```

#### P1-2: `app.json` nadpisuje oczekiwania operatora

Operator zakłada, że IP w `app.json` wystarczy — ale wartość zawiera `/api/v1`, co jest **niezgodne** z kontraktem `config.ts` (baza bez prefiksu).

**Pliki:** `app.json`, `src/api/config.ts`, `README.md` (poprawny przykład: URL **bez** `/api/v1`).

#### P1-3: Błąd HTTP inny niż 401 (502, 503, timeout)

Rzadziej przy działającym curl, ale możliwy przy różnicy ścieżek (podwójny prefix → 404).

---

### P2 — mało prawdopodobne (przy działającym Safari na tym samym hoście)

#### P2-1: ATS / iOS blokuje cleartext HTTP w fetch

Safari na iPhone otwiera `http://100.87.84.118:8000/health` — **ATS nie blokuje** tego hosta w przeglądarce. Expo Go w dev zwykle też akceptuje HTTP. Mało prawdopodobne jako główna przyczyna.

#### P2-2: Problem specyficzny Expo Go

Możliwy, ale wtedy `/health` w Safari nadal nie wyjaśnia różnicy — bardziej wskazuje na zły URL niż na Expo Go.

#### P2-3: Parser odpowiedzi loginu

Gdyby JSON był poprawny bez `access_token` → *„Nieprawidłowy login”*, nie *„połączenie”*. **Wykluczone** przy obecnym komunikacie.

#### P2-4: Cloudflare Access

curl i Safari używają Tailscale IP — CF nie wchodzi w grę. Gdyby CF — inny komunikat w aplikacji.

---

## 3. Checklist diagnostyczna

### Faza A — potwierdź URL (5 min)

- [ ] **A1** Odczytaj `mobile-expo/app.json` → `expo.extra.apiBaseUrl` — czy zawiera `/api/v1`?
- [ ] **A2** Sprawdź, **jaką komendą** uruchomiono Expo (historia terminala / notatka operatora).
- [ ] **A3** curl podwójnego URL (`/api/v1/api/v1/auth/login`) — status i body.
- [ ] **A4** curl poprawnego URL (`/api/v1/auth/login`) — 200 + token.

### Faza B — konfiguracja runtime (5 min)

- [ ] **B1** W terminalu Metro przy starcie: czy widoczne `EXPO_PUBLIC_API_BASE_URL`?
- [ ] **B2** Restart: `EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000 npx expo start -c`
- [ ] **B3** Ponowne skanowanie QR w Expo Go (świeży bundle).
- [ ] **B4** Logowanie tymi samymi danymi co w curl.

### Faza C — sieć i odpowiedź (10 min)

- [ ] **C1** iPhone: Safari → `http://100.87.84.118:8000/health` (już OK).
- [ ] **C2** Mac: Tailscale ping do `100.87.84.118`.
- [ ] **C3** Mac: curl login z tymi samymi credentials co w IFGM.
- [ ] **C4** Porównaj username — curl vs IFGM (literówka → wtedy *„Nieprawidłowy login”*, nie ten objaw).

### Faza D — logi (jeśli A–C nie wystarczy)

- [ ] **D1** Metro bundler — błędy sieci / fetch w konsoli po kliknięciu „Zaloguj”.
- [ ] **D2** Flipper / React Native Debugger — Network tab (jeśli dostępny).
- [ ] **D3** Logi API na DS723+ w momencie próby logowania z IFGM:
  ```bash
  docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs -f api --tail=50
  ```
  Brak wpisu POST `/auth/login` → request nie dociera (zły host/URL).  
  Wpis `POST /api/v1/api/v1/auth/login` → **potwierdza P0-1**.

---

## 4. Pliki do sprawdzenia

| Plik | Co sprawdzić |
|------|----------------|
| `mobile-expo/app.json` | `extra.apiBaseUrl` — **nie** powinno kończyć się na `/api/v1` |
| `mobile-expo/src/api/config.ts` | Priorytet env vs app.json vs fallback |
| `mobile-expo/src/api/client.ts` | Składanie URL: `base + /api/v1 + path` |
| `mobile-expo/src/api/auth.ts` | Mapowanie błędów → który komunikat widzi użytkownik |
| `mobile-expo/README.md` | Poprawny przykład env (bez `/api/v1`) |
| Terminal Metro | Komenda startu, wartość `EXPO_PUBLIC_API_BASE_URL` |

---

## 5. Komendy i dane do zebrania

### Obowiązkowe (przekaż do analizy)

1. **Dokładna komenda** uruchomienia Expo (copy-paste z terminala).
2. **Wynik A3** — curl podwójnego URL (status HTTP + pierwsze 200 znaków body).
3. **Zawartość** `app.json` → `extra.apiBaseUrl` (aktualna).
4. **Czy po restarcie z `-c` i poprawnym env** problem ustępuje (tak/nie).

### Opcjonalne (gdy problem trwa)

5. Fragment logów Metro po nieudanym logowaniu.
6. Fragment logów `api` z DS723+ (czy widać POST i jaka ścieżka).
7. Screenshot ekranu błędu IFGM (pełny komunikat).

### Szybki test potwierdzający P0-1 (Mac mini)

```bash
# Błędny URL (symuluje app.json bez env)
curl -i -X POST "http://100.87.84.118:8000/api/v1/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}'

# Poprawny URL
curl -i -X POST "http://100.87.84.118:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}'
```

---

## 6. Plan działań (bez zmian w kodzie)

### Krok 1 — Potwierdź hipotezę podwójnego `/api/v1`

Uruchom curl z sekcji 5 (błędny vs poprawny URL).  
Jeśli błędny zwraca 404/405/HTML, a poprawny 200 — **przyczyna zidentyfikowana**.

### Krok 2 — Uruchom Expo z poprawnym env

```bash
cd mobile-expo
EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000 npx expo start -c
```

**Bez** `/api/v1` na końcu. Zeskanuj QR ponownie.

### Krok 3 — Test logowania na iPhone

Te same credentials co w curl.  
Oczekiwany wynik: dashboard.

### Krok 4 — Jeśli nadal błąd

Zbierz logi Metro (Krok D) i logi API DS723+.  
Sprawdź, czy request w ogóle dociera i jaka jest ścieżka.

### Krok 5 — Dopiero po identyfikacji — ewentualna poprawka kodu (poza tym raportem)

Kandydaci **na później** (nie teraz):
- poprawić `app.json` (`apiBaseUrl` bez `/api/v1`),
- opcjonalnie: guard w `config.ts` stripujący końcówkę `/api/v1` z bazy.

---

## 7. Najbardziej prawdopodobna przyczyna (hipoteza G2)

**Podwójne `/api/v1`** — `app.json` ma `http://100.87.84.118:8000/api/v1`, a klient HTTP dokleja kolejne `/api/v1`. Przy starcie Expo **bez** `EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000` login trafia w nieistniejący endpoint → komunikat *„Sprawdź połączenie z serwerem”*, podczas gdy curl i Safari testują poprawne ścieżki.

---

## 8. Wymagane dane diagnostyczne (skrót)

| # | Dane |
|---|------|
| 1 | Komenda uruchomienia `npx expo start` (z env lub bez) |
| 2 | Wynik curl na `/api/v1/api/v1/auth/login` vs `/api/v1/auth/login` |
| 3 | Aktualna wartość `app.json` → `extra.apiBaseUrl` |
| 4 | Wynik testu po `EXPO_PUBLIC_API_BASE_URL=...:8000 npx expo start -c` |
| 5 | (Opcjonalnie) log API DS723+ — ścieżka POST przy próbie z IFGM |

---

*IFGM Login Diagnostics — G2, bez modyfikacji kodu aplikacji.*
