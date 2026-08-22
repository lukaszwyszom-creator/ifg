# KSeF — obsługa pustej synchronizacji zakupów

## Problem

Ręczna synchronizacja faktur zakupowych KSeF kończyła się błędem **502**, mimo że sesja była aktywna i API odpowiadało poprawnie.

Typowy przebieg w produkcji:

1. `GET /sessions/{session}/invoices` → HTTP **200**, pusta lista faktur
2. `POST /sessions/{session}/invoices/query` → **405**
3. `POST /invoices/query` → **404**
4. IFG rzucało wyjątek: `Brak dostępnego endpointu query dla KSeF`

Użytkownik widział błąd serwera zamiast raportu sync z zerowymi licznikami.

## Przyczyna

Produkcyjne API KSeF v2 akceptuje GET na endpointach sesyjnych, ale **nie udostępnia** POST query fallback używanego w kodzie IFG. Po poprawce wcześniejszego buga (pusty GET nie blokował już POST) kod dochodził do końca ścieżki fallbacków i traktował brak endpointu POST jako błąd krytyczny.

To nie jest błąd sesji ani autoryzacji — to **pusty wynik zapytania** w połączeniu z niedostępnymi endpointami POST.

## Wprowadzone zmiany

Plik: `app/integrations/ksef/client.py`

- Flaga `empty_get_succeeded` — ustawiana, gdy GET zwróci HTTP 200 bez faktur i bez `referenceNumber`
- Flagi `post_fallback_attempted` / `post_fallback_only_skipable` — śledzą POST fallback (404/405/21405)
- Gdy GET pusty, POST niedostępny → **zwracana pusta lista `[]`** z logiem:
  `KSeF received invoices query returned empty result; no POST query endpoint available`
- Dodano `.gitattributes` z `eol=lf` dla `*.py`, `*.js`, `*.jsx`, `*.md` — zapobiega przypadkowym `^M` w diffach

## Dlaczego `[]` zamiast 502

| Aspekt | 502 (wyjątek) | `[]` (sukces) |
|--------|---------------|---------------|
| Semantyka | Błąd infrastruktury IFG | Brak nowych faktur w zadanym okresie |
| UI / API | Sync failed | Sync OK: `ksef_returned=0`, `created=0` |
| Dedup / stan | Sync state może oznaczyć error | Sync state aktualizowany poprawnie |
| Diagnostyka | Ukrywa prawdziwy problem (pusty KSeF) | Logi nadal pokazują pusty GET i niedostępny POST |

502 jest poprawne tylko przy realnym błędzie (timeout, 401, 500 KSeF). Pusty wynik z działającym GET to **oczekiwany scenariusz**, dopóki nie znajdziemy właściwego sposobu pobierania historycznych FV zakupowych.

## Walidacja

```bash
python3 -m py_compile app/integrations/ksef/client.py
# exit code 0 — OK
```

## Otwarte — brak faktur w KSeF

Ta poprawka **nie rozwiązuje** problemu, że KSeF zwraca 0 faktur mimo ich obecności w portalu MF. Wymaga dalszej analizy:

- właściwego endpointu / parametrów query dla FV zakupowych w prod API v2
- `subjectType`, typ daty (`invoicingDate` vs `issueDate`)
- uprawnień tokena / roli podmiotu w sesji

Patrz też: `docs/KSEF_PURCHASE_DIAGNOSTICS.md`
