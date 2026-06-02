# IFG Mobile (Expo)

Aplikacja iPhone rozwijana równolegle z IFG web.

## Zasady

- Branch: `feature/mobile-expo` (osobny od `main` / `production`).
- Korzysta z istniejącego API IFG (`/api/v1/*`).
- **Nie** modyfikuje `app/`, `frontend-react/`, `docker/docker-compose.prod.yml`.
- **Nie** zastępuje `frontend-react` — to osobny klient mobilny.

## Start (Mac mini)

```bash
cd mobile-expo
npm install
npm run ios
```

## API

Domyślnie: `http://127.0.0.1:8000` (lokalny backend dev).

Produkcja / DS723+ (Tailscale):

```bash
EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000 npm run ios
```

## Struktura

```
mobile-expo/
├── app/           Expo Router
├── src/api/       klient HTTP IFG
├── app.json
└── package.json
```
