# KSeF — synchronizacja faktur zakupowych v1

## Diagnoza

IFG łączy się z produkcyjnym KSeF, sesja jest aktywna, endpoint sync purchases zwraca HTTP 200, ale faktury zakupowe nie pojawiają się w aplikacji. Przyczyny zidentyfikowane w v1:

1. **Zbyt krótki zakres dat** — poprzednia logika używała domyślnie ~30 dni wstecz (lub krótkie okno bez jawnej konfiguracji w API).
2. **Hardcoded `subjectType=subject2`** — dla części podmiotów KSeF zwraca pustą listę mimo istniejących faktur zakupowych (naprawione wcześniej fallbackiem subject2 → subject1 → subject3).
3. **Brak raportu parzystości** — odpowiedź API nie zawierała pełnego podsumowania sync (okres, subjectType, liczniki, błędy).

## Decyzje projektowe

| Decyzja | Uzasadnienie |
|---------|--------------|
| Lokalna baza IFG jako źródło prawdy po sync | IFG/IFGM czytają dane z DB; KSeF jest tylko źródłem importu |
| Endpoint `POST /api/v1/ksef/sync/purchases` z opcjonalnymi parametrami dat | Umożliwia ręczny pełny import i inkrementalny sync bez zmian UI |
| Domyślnie 90 dni (`days_back`) | Bezpieczne minimum historyczne bez migracji DB |
| `force_full=true` → 365 dni | Pierwszy / pełny import historyczny |
| Inkrementalność przez `ksef_sync_states.state_json` | Tabela już istnieje — bez nowej migracji |
| Bufor 2 dni nakładania okna | Chroni przed opóźnieniami KSeF przy sync inkrementalnym |
| Dedup po `ksef_reference_number` | Istniejący unikalny identyfikator w modelu faktury |
| Fallback subjectType bez duplikacji importu | Import tylko z pierwszego niepustego subjectType |

## Jak działa zakres dat

Parametry requestu (`POST /api/v1/ksef/sync/purchases`):

| Parametr | Domyślnie | Opis |
|----------|-----------|------|
| `date_from` | — | Opcjonalna data początkowa (ISO) |
| `date_to` | dziś | Opcjonalna data końcowa |
| `days_back` | 90 | Używane gdy brak `date_from` |
| `force_full` | false | Pełny import: ostatnie 365 dni |

Algorytm (`KSeFSessionService.resolve_purchase_sync_window`):

1. Jeśli podano `date_from` → użyj `[date_from, date_to]`.
2. Jeśli `force_full=true` → `[dziś − 365 dni, dziś]`.
3. Jeśli istnieje poprzedni udany sync w `ksef_sync_states.state_json.last_date_to`:
   - `date_from = max(dziś − days_back, last_date_to − 2 dni bufora)`.
4. W przeciwnym razie → `[dziś − days_back, dziś]`.

Konfiguracja env (opcjonalna):

- `KSEF_PURCHASE_SYNC_DAYS_BACK` (domyślnie 90)
- `KSEF_PURCHASE_SYNC_FULL_DAYS` (domyślnie 365)
- `KSEF_PURCHASE_SYNC_OVERLAP_DAYS` (domyślnie 2)

## Jak działa inkrementalność

Stan sync zapisywany w istniejącej tabeli `ksef_sync_states` (scope=`purchase_invoices`):

```json
{
  "last_date_from": "2026-03-01",
  "last_date_to": "2026-05-22",
  "last_subject_type": "subject1",
  "last_counts": { ... }
}
```

Kolejny sync bez `date_from` zaczyna od `last_date_to − 2 dni` (z nakładaniem), nie od zera.

Status sync można odczytać: `GET /api/v1/ksef/sync/status`.

## Jak działa dedup

Przed zapisem każdej faktury wywoływane jest `invoice_repository.exists_by_ksef_number(ksef_reference_number)`. Istniejące faktury są pomijane (`skipped_existing`), nowe zapisywane jako `direction=purchase`.

## Jak testować

### curl — login + sync

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)

# Inkrementalny sync (domyślnie 90 dni / od ostatniego sync)
curl -s -X POST http://localhost:8000/api/v1/ksef/sync/purchases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq

# Pełny import historyczny
curl -s -X POST http://localhost:8000/api/v1/ksef/sync/purchases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force_full": true}' | jq

# Jawny zakres dat
curl -s -X POST http://localhost:8000/api/v1/ksef/sync/purchases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date_from":"2025-01-01","date_to":"2026-05-22"}' | jq
```

Oczekiwana odpowiedź:

```json
{
  "status": "ok",
  "date_from": "2025-01-01",
  "date_to": "2026-05-22",
  "subject_type": "subject1",
  "ksef_returned": 12,
  "created": 10,
  "skipped_existing": 2,
  "errors": 0,
  "error_samples": []
}
```

### IFG UI

1. Otwórz sesję KSeF (aktywna sesja wymagana).
2. Uruchom synchronizację zakupów (przycisk sync w panelu KSeF).
3. Sprawdź listę faktur zakupowych — dane powinny być widoczne bez ponownego sync.
4. Powtórz sync — `skipped_existing` rośnie, brak duplikatów.

### Logi backendu

Szukaj wpisów:

```
KSeF purchases sync subjectType=subject2 result_count=0 date_from=... date_to=...
KSeF purchases sync done: date_from=... date_to=... subjectType=subject1 ksef_returned=... created=...
```

## Ograniczenia

- Brak UI do wyboru zakresu dat — tylko API (parametry opcjonalne).
- Endpoint asynchroniczny `/ksef-sessions/sync-purchase` nadal wymaga jawnych `date_from`/`date_to` w body (bez zmian w v1).
- Fallback subjectType może wykonać do 3 zapytań KSeF przy pustych wynikach.
- `error_samples` ograniczone do 5 wpisów, bez tokenów i danych wrażliwych.
- Parzystość KSeF ↔ IFG opiera się na licznikach sync, nie na pełnej reconciliacji per-faktura.

## TODO — docelowa parzystość

- [ ] UI: wybór zakresu dat i trybu `force_full` w panelu KSeF.
- [ ] Env `KSEF_PURCHASES_SUBJECT_TYPE` — pominąć fallback gdy znany właściwy typ.
- [ ] Raport parzystości per okres: porównanie liczby FV w KSeF vs lokalna baza (checksum / lista brakujących ref).
- [ ] Ujednolicić endpoint async `/sync-purchase` z nowymi parametrami dat.
- [ ] Scheduler automatycznego sync inkrementalnego (cron / background job).
- [ ] Retencja historii sync (audit trail poza `state_json`).
