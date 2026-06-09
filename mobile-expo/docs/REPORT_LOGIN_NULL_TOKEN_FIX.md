# Raport: naprawa crasha `access_token` przy logowaniu

**Data:** 2026-05-22  
**Zakres:** `src/api/auth.ts`, `app/login.tsx`

## Problem

Po błędnym logowaniu aplikacja wyświetlała:
`Cannot read property 'access_token' of null`

Przyczyna: `loginWithCredentials` odwoływało się do `res.access_token` bez sprawdzenia, czy odpowiedź API istnieje i zawiera token.

## Zmiany

### `src/api/auth.ts`

- Walidacja pustego loginu/hasła przed requestem.
- `try/catch` wokół `apiClient.post` — błędy HTTP i sieci bez crasha.
- Mapowanie błędów auth na: **„Nieprawidłowy login lub hasło”**.
- Błędy sieci/serwera na bezpieczny komunikat bez szczegółów technicznych.
- Token zapisywany **tylko** gdy `access_token` jest niepustym stringiem.

### `app/login.tsx`

- Komunikat przy pustym loginie/hasłu przed wysłaniem formularza.
- Wyświetlanie `authError` z kontekstu lub `localError` z formularza.

## Oczekiwane zachowanie

| Scenariusz | Wynik |
|------------|-------|
| admin + błędne hasło | Komunikat „Nieprawidłowy login lub hasło”, brak crasha |
| admin + puste hasło | Ten sam komunikat, brak requestu |
| Brak tokena | Brak dostępu do dashboardu / zakładek (guard w `_layout`) |
| Poprawne dane | Token w pamięci, redirect na dashboard |

## Test manualny

1. `EXPO_PUBLIC_API_BASE_URL=<backend> npx expo start`
2. Wpisz `admin` + złe hasło → komunikat, bez przejścia dalej.
3. Wpisz poprawne dane → logowanie OK, dashboard z API.
