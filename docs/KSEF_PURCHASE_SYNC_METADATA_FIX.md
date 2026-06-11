# KSeF — naprawa sync zakupów przez metadata query

Data: 2026-06-10

---

## Przyczyna

IFG synchronizował faktury zakupowe przez **sesyjne GET** (`/sessions/{sessionReference}/invoices*`), które na prod KSeF v2 zwracały **HTTP 200 z pustą listą** (`invoices=[]`).

Jednocześnie **`POST /v2/invoices/query/metadata`** z `subjectType=Subject2` zwracał **28 faktur** w tym samym okresie (potwierdzone przez `scripts/ksef_metadata_probe.py` na DS723+).

Sync używał niewłaściwego surface API — poprawna ścieżka dla zakupów to metadata query, nie lista sesyjna.

---

## Zmiana

### `app/integrations/ksef/client.py`

Dla `subject_type=subject2` (FV zakupowe):

1. **`POST /invoices/query/metadata`**
   - `subjectType=Subject2`
   - `dateType`: preferowane `PermanentStorage`, fallback `Invoicing`
   - paginacja (`pageOffset` / `pageSize=50`)
   - zakres dat z okna sync (ISO datetime UTC)

2. **`GET /invoices/{ksefNumber}`** dla każdego numeru z metadanych
   - obsługa `encryptedInvoiceContent` (decrypt sesyjny) oraz plain `invoice` / `invoiceXml`

3. **Throttling / 429**
   - min. **1.2 s** między requestami KSeF (`_pace_request`)
   - dodatkowy sleep po HTTP 429 przed retry

Fallback do starej ścieżki sesyjnej tylko gdy metadata endpoint zwróci **404/405** (środowiska testowe).

### Bez zmian

- `app/services/ksef_sync_service.py` — deleguje do `sync_received_invoices`
- `app/services/ksef_session_service.py` — zapis do bazy bez zmian (parsowanie FA(3) XML)
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `app/api/routers/ksef_session.py`
- sprzedaż, FA(3), UI, mobilka

---

## Zapis do bazy

Po pobraniu XML flow bez zmian: `parse_fa3_xml` → `Invoice` z `direction=purchase` → `invoice_repository.add(source_system="ksef_import")`.

---

## Następny krok (jeśli GET /invoices/{ref} zawiedzie)

Metadata zwraca tylko numery KSeF. Jeśli prod zwróci nieznany format XML lub wymaga innej ścieżki:

- sprawdzić **`GET /invoices/ksef/{ksefNumber}`** (alternatywny endpoint MF)
- ewentualnie export batch — poza zakresem tej poprawki

---

## Testy

- `tests/unit/test_ksef_client_retry.py::TestQueryReceivedInvoicesMetadata`
- istniejące testy sesyjne — metadata POST → 404 → fallback (kompatybilność test env)

---

## Deploy DS723+

**Tak — wymagany deploy backendu** (zmiana `app/integrations/ksef/client.py`). Po deployu uruchomić sync zakupów z UI lub:

```bash
POST /api/v1/ksef-sessions/sync/purchases
```

Oczekiwany wynik: `ksef_returned > 0`, `created > 0` dla okresu z fakturami w KSeF.
