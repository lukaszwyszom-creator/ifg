# GWO-IFG-CURSOR-NPM-TASK-PROVIDER-ISOLATION-0004

Data: 2026-09-22  
Zakres: izolacja `npm.autoDetect` (User Settings only). Bez zmian w repo / package.json / commit / push / deploy.

## Co zrobiono

1. **User Settings only**  
   Plik: `/Users/lukasz/Library/Application Support/Cursor/User/settings.json`  
   Ustawiono: `"npm.autoDetect": "off"`  
   Potwierdzono: **brak** `npm.autoDetect` w `.vscode/settings.json` repozytorium.

2. **Reload**  
   Pełne `Developer: Reload Window` przez osascript **zablokowane** przez macOS Accessibility (`osascript nie ma zezwolenia…`).  
   Wykonano równoważny restart Extension Host okna IFG (`window3`) **po** ustawieniu `npm.autoDetect=off`:
   - kill EH pid `85992` @ `21:20:21`
   - nowy EH pid `88389`
   - `vscode.npm` activate success @ `21:20:22.355`

3. **Weryfikacja po restarcie** (do ~21:21:48, w tym ponowne otwarcie `frontend-react/package.json` przez CLI):
   - **0** nowych / zaktualizowanych `tasks*.log` od `21:18:00`
   - brak nowego `output_*` z błędem npm
   - stare logi błędu (≤ `21:10:14`) **nie** zostały przepisane

## Wyniki pakietu

| Check | Result |
|---|---|
| `JSON.parse(frontend-react/package.json)` | PASS (`name=faktura-frontend`) |
| `npm pkg get name` | PASS (`"faktura-frontend"`, rc=0) |
| `package.json` niezmieniony w tej izolacji | TAK (tylko User settings) |

## Porównanie z DIAG-0003

Przed `autoDetect=off`, każdy cykl reload/EH pisał w ciągu ~5 s:

`Error: Npm task detection: failed to parse the file .../frontend-react/package.json`

Po `autoDetect=off` + re-aktywacji `vscode.npm`: **brak** tego wpisu.

## STATUS

`ISOLATION_PASS`

## NPM_AUTODETECT

`OFF` (User Settings; pozostawione)

## ERROR_AFTER_RELOAD

`NO`  
(brak nowego toast-dowodu w logach; UI toast nie jest logowany — proxy = brak nowego Tasks error po re-aktywacji providera)

## TASK_LOG_ERROR_AFTER_RELOAD

`NO`

## PACKAGE_JSON_VALID

`YES`

## VERDICT

`NPM_TASK_PROVIDER_CONFIRMED`

Komunikat / Tasks error pochodzi wyłącznie z automatycznego npm task detection Cursora (`vscode.npm` gdy `npm.autoDetect=on`).  
Nie wpływa na poprawność `frontend-react/package.json` ani na projekt IFG.  
Dalsza diagnostyka **wstrzymana**. `npm.autoDetect=off` **zostaje**.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Diag/izolacja IDE only — brak zmian aplikacji IFG.)
