# IFG Mobile (Expo)

Aplikacja iPhone rozwijana równolegle z IFG web.

## Zasady

- Branch: `feature/mobile-expo` (osobny od `main` / `production`).
- Korzysta z istniejącego API IFG (`/api/v1/*`).
- **Nie** modyfikuje backendu IFG.
- **Nie** zastępuje `frontend-react` — to osobny klient mobilny.

## Start

```bash
cd mobile-expo
npm install
npx expo start
```

## Adres API

Ustaw przez `EXPO_PUBLIC_API_BASE_URL` (nadpisuje `app.json`):

| Środowisko | URL |
|------------|-----|
| Mac mini LAN / dev | `http://192.168.1.50:8000` |
| DS723+ Tailscale (bez CF Access) | `http://100.87.84.118:8000` |
| `https://ifg.ikonastudio.pl` | **nie dla mobile API** — Cloudflare Access blokuje `/api/v1/*` (HTTP 302) |
| Simulator iOS (backend lokalny) | `http://127.0.0.1:8000` |

```bash
# Mac mini LAN
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.50:8000 npx expo start

# Produkcja
EXPO_PUBLIC_API_BASE_URL=https://ifg.ikonastudio.pl npx expo start
```

## Logowanie i dashboard (MVP)

1. Aplikacja startuje na ekranie **logowania** (`/login`).
2. Po poprawnym `POST /api/v1/auth/login` token JWT trafia do pamięci (`AuthContext` + `apiClient`).
3. Redirect na **dashboard** → `GET /api/v1/mobile/dashboard?period=YYYY-MM`.
4. Bez tokena — brak dostępu do chronionych ekranów (redirect na login).
5. Błąd API na dashboardzie — komunikat + „Spróbuj ponownie”; KPI i linki FV nie renderują się.

Opcjonalnie w dev (pomija ekran logowania):

```bash
EXPO_PUBLIC_API_TOKEN=<jwt> npx expo start
```

## Test w Expo Go

```bash
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.50:8000 npx expo start
```

1. Zeskanuj QR w Expo Go (telefon w tej samej sieci co backend).
2. Zaloguj się loginem IFG (np. `admin`).
3. Dashboard powinien pokazać dane z API (spinner → KPI).

### Jak sprawdzić, że dashboard NIE używa mocków

- Mock `dashboardMock` ma stałe wartości (np. sprzedaż `125 430 zł`) — **dashboard.tsx ich nie importuje**.
- Po logowaniu wartości KPI powinny odpowiadać danym z backendu dla wybranego okresu.
- Zmiana miesiąca w selektorze odświeża zapytanie do API.
- Przy wyłączonym backendzie: komunikat błędu zamiast danych mock.
- W logach Metro / proxy sieci widać request `GET .../api/v1/mobile/dashboard?period=...`.

## Struktura auth

```
mobile-expo/
├── app/login.tsx          ekran logowania
├── app/dashboard.tsx      dane z API
├── app/_layout.tsx        AuthProvider + guard
├── src/auth/AuthContext.tsx
└── src/api/
    ├── auth.ts            POST /auth/login
    ├── mobile.ts          GET /mobile/dashboard
    └── config.ts          base URL
```

Pozostałe ekrany (faktury, rozrachunki itd.) nadal korzystają z `src/data/mock.ts` — poza zakresem tego etapu.
