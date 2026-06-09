# Cloudflare Access vs logowanie IFGM

## Obserwacja (curl)

```bash
curl -i -X POST https://ifg.ikonastudio.pl/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Odpowiedź: **HTTP 302** → redirect do `cloudflareaccess.com`, nagłówek `www-authenticate: Cloudflare-Access`.

## Przyczyna

Publiczny URL `https://ifg.ikonastudio.pl` jest chroniony **Cloudflare Access** (Zero Trust).
Żądanie do `/api/v1/auth/login` nie trafia do FastAPI — CF wymaga wcześniejszej autoryzacji przez Access.

IFGM wysyła `POST` z JSON `{username, password}` do JWT IFG, ale dostaje stronę logowania Cloudflare.

## Rozwiązanie dla mobile

Użyj adresu API **bez Cloudflare Access**:

```bash
# Mac mini LAN
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.50:8000 npx expo start

# DS723+ Tailscale
EXPO_PUBLIC_API_BASE_URL=http://100.87.84.118:8000 npx expo start
```

## Weryfikacja

Poprawny backend zwraca JSON:

```bash
curl -s -X POST http://192.168.1.50:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"..."}' | jq .access_token
```

## Zmiana w aplikacji

`src/api/client.ts` wykrywa 302 / Cloudflare-Access / HTML i pokazuje czytelny komunikat zamiast crasha lub „Nieprawidłowy login”.
