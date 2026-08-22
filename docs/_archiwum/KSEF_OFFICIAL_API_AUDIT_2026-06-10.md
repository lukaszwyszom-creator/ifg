# KSeF API 2.0 — audyt sync zakupów IFG vs dokumentacja MF

Data: 2026-06-10  
Źródła:
- OpenAPI prod: `https://api.ksef.mf.gov.pl/docs/v2/openapi.json` (pobrane 2026-06-10)
- Dokumentacja CIRFMF: `https://github.com/CIRFMF/ksef-docs` (`pobieranie-faktur/pobieranie-faktur.md`, `przyrostowe-pobieranie-faktur.md`)

Pliki IFG:
- `app/integrations/ksef/client.py`
- `app/services/ksef_session_service.py`
- `app/services/ksef_sync_service.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `scripts/ksef_metadata_probe.py`
- `tests/unit/test_ksef_client_retry.py`

---

## 1. Endpointy wg oficjalnej dokumentacji MF

### Wyszukiwanie metadanych

| Oficjalny endpoint | Metoda | Opis |
|--------------------|--------|------|
| `/invoices/query/metadata` | **POST** | Lista metadanych faktur (`InvoiceQueryFilters`: `subjectType`, `dateRange`) |
| Query params | | `pageOffset`, `pageSize` (10–250), `sortOrder` |
| Response 200 | | `hasMore`, `isTruncated`, `permanentStorageHwmDate`, `invoices[]` (`InvoiceMetadata`) |

**Enumy:** `subjectType`: `Subject1|Subject2|Subject3|SubjectAuthorized`; `dateType`: `Issue|Invoicing|PermanentStorage`.

### Pobranie pojedynczej faktury

| Oficjalny endpoint | Metoda | Response |
|--------------------|--------|----------|
| `/invoices/ksef/{ksefNumber}` | **GET** | **`application/xml`** — surowe XML FA |

**Brak w OpenAPI:** `GET /invoices/{ksefNumber}`.

### Eksport paczek (rekomendowany sync przyrostowy)

| Oficjalny endpoint | Metoda | Opis |
|--------------------|--------|------|
| `/invoices/exports` | **POST** | Asynchroniczny eksport (`encryption`, `filters`, opcj. `onlyMetadata`) |
| `/invoices/exports/{referenceNumber}` | **GET** | Status + URL paczki (ZIP/TarGz, `_metadata.json` + XML) |

CIRFMF: **POST `/invoices/exports` jest rekomendowanym mechanizmem** synchronizacji przyrostowej (HWM, `restrictToPermanentStorageHwmDate`).

### Sesja online (wysyłka, nie zakupy)

| Oficjalny endpoint | Metoda | Opis |
|--------------------|--------|------|
| `/sessions/online` | POST | Otwarcie sesji interaktywnej |
| `/sessions/{referenceNumber}/invoices` | **GET** | **Faktury przesłane w sesji** + statusy (nie lista zakupów!) |
| `/sessions/{referenceNumber}/invoices/{invoiceReferenceNumber}` | GET | Status pojedynczej faktury w sesji |

**Brak w OpenAPI:**
- `/sessions/{ref}/invoices/received`
- `/sessions/{ref}/invoices/query`
- `POST /sessions/{ref}/invoices/query`
- `POST /invoices/query`

### Rate limiting (oficjalne limity z OpenAPI 429)

| Grupa | req/s | req/min | req/h |
|-------|-------|---------|-------|
| `invoiceMetadata` | 8 | 16 | **20** |
| `invoiceDownload` | 8 | 16 | 64 |
| `invoiceExport` | (osobna grupa) | | |
| `invoiceExportStatus` | (osobna grupa) | | |

Endpoint diagnostyczny: `GET /rate-limits` → `EffectiveApiRateLimits`.

Obsługa 429: retry z `Retry-After` (CIRFMF: „sterowanie tempem wywołań”).

---

## 2. Co używa IFG obecnie

### `query_received_invoices` (`client.py`) — ścieżka subject2 (nowa)

| Krok | IFG | Zgodność |
|------|-----|----------|
| 1 | `POST /invoices/query/metadata` + `Subject2` + `PermanentStorage`/`Invoicing` | ✅ **Zgodne** (potwierdzone prod: 28 FV) |
| 2 | Paginacja przez `totalCount` | ⚠️ **Niezgodne** — OpenAPI ma `hasMore`, nie `totalCount` |
| 3 | `GET /invoices/{ksefNumber}` + parse JSON | ❌ **Niepotwierdzone / błędne** — powinno być `/invoices/ksef/{ksefNumber}` + XML |

### Fallback sesyjny (gdy metadata 404/405 lub subject1/3)

| IFG endpoint | W OpenAPI? | Ocena |
|--------------|------------|-------|
| `GET /sessions/{ref}/invoices/received` | ❌ brak | Podejrzany |
| `GET /sessions/{ref}/invoices/query` | ❌ brak | Podejrzany |
| `GET /sessions/{ref}/invoices` + params `invoiceType=received` | ⚠️ path istnieje, **inna semantyka** | Zwraca faktury **wysłane w sesji**, nie zakupy — prod: 200 + `[]` |
| `POST /sessions/{ref}/invoices/query` | ❌ brak | Prod: 405 |
| `POST /invoices/query` | ❌ brak | Prod: 404 |
| `GET /invoices/{ref}` + decrypt sesyjny | ❌ brak path | Błędny path; decrypt z kluczem sesji online nie dotyczy pobrania po KSeF number |

### Warstwa sync (bez zmian API)

- `ksef_session_service.sync_received_invoices` → `query_received_invoices` → `parse_fa3_xml` → `invoice_repository.add`
- `ksef_sync_service` / worker — delegacja, bez własnych endpointów
- `ksef_metadata_probe.py` — `POST /invoices/query/metadata` ✅ (referencja parametrów OK)

---

## 3. Diagnoza problemu prod

1. **Stara ścieżka** opierała się na sesyjnych GET + nieistniejących POST query → pusta lista mimo faktur w portalu.
2. **Poprawka metadata** trafia we właściwy endpoint listy (28 FV na DS723+).
3. **Pobranie XML** nadal używa **nieoficjalnego** `GET /invoices/{ref}` i oczekuje JSON — sync może zwrócić `ksef_returned=28`, `saved=0`, `skipped_parse>0`.

---

## 4. `GET /invoices/{ksefNumber}` vs `/invoices/ksef/{ksefNumber}`

| | IFG | Oficjalne API |
|---|-----|---------------|
| Path | `/invoices/{ref}` | **`/invoices/ksef/{ksefNumber}`** |
| Accept | domyślny / JSON | **`application/xml`** |
| Body | JSON (`encryptedInvoiceContent`, `invoice`) | **surowe XML** |
| Szyfrowanie sesji | próba decrypt AES kluczem sesji online | **nie dotyczy** |

**Wniosek:** `GET /invoices/{ksefNumber}` **nie jest poprawne**. Należy użyć **`GET /invoices/ksef/{ksefNumber}`** i czytać `response.content`.

---

## 5. Metadata + pojedyncze pobrania vs exports

| Kryterium | metadata + GET ksef | POST exports |
|-----------|---------------------|--------------|
| Oficjalność | ✅ oba endpointy | ✅ rekomendowany przez CIRFMF |
| ~28 FV (obecny case) | ✅ wystarczy (~29 requestów) | overkill |
| 100+ FV / sync przyrostowy | ⚠️ limit **20 req/h** na metadata; 64/h download | ✅ lepsze (paczka, HWM) |
| Dedup / HWM | ręcznie w IFG | wbudowane (`permanentStorageHwmDate`, `_metadata.json`) |
| Złożoność | niska | średnia (encryption, polling, rozpakowanie ZIP) |

**Rekomendacja:**
- **Teraz (28 FV):** metadata + `/invoices/ksef/{ksefNumber}` — minimalny patch.
- **Później (prod sync przyrostowy, duże wolumeny):** migracja na `POST /invoices/exports` wg `przyrostowe-pobieranie-faktur.md`.

---

## 6. Czy obecna poprawka (metadata) jest bezpieczna?

| Element | Bezpieczna? | Uwagi |
|---------|-------------|-------|
| `POST /invoices/query/metadata` + Subject2 | **Tak** | Zgodne z OpenAPI; potwierdzone prod |
| Paginacja `totalCount` | **Częściowo** | Działa dla ≤50 wyników; przy >50 może uciąć listę — użyć `hasMore` |
| Throttling 1.2 s | **Tak** | Poniżej 8 req/s; OK dla download, uwaga na 20 req/h metadata przy dużych oknach |
| `GET /invoices/{ref}` | **Nie** | Nieoficjalny path; prawdopodobnie blokuje zapis do bazy |
| Fallback sesyjny | **Nie** | Endpointy niepotwierdzone / zła semantyka — nie polegać na prod |

**Podsumowanie:** poprawka metadata jest **kierunkowo poprawna**, ale **niekompletna** — bez fix pobierania XML sync nie zapisze faktur mimo `ksef_returned>0`.

---

## 7. Proponowany minimalny patch (po audycie)

**Zakres:** tylko `app/integrations/ksef/client.py` + test w `test_ksef_client_retry.py`. Bez UI, sprzedaży, exports.

### P0 — wymagane

1. **`_download_received_invoices`:** zamienić path na `GET /invoices/ksef/{ksefNumber}`.
2. **Response:** `Accept: application/xml`, `xml_bytes = inv_resp.content` (bez `.json()` / decrypt sesyjnego dla tej ścieżki).
3. **Paginacja metadata:** iterować po `hasMore is True`, nie po `totalCount`.

### P1 — zalecane

4. Usunąć/wyłączyć fallback na nieistniejące path (`/invoices/received`, `/invoices/query`, `POST /invoices/query`) — zostawić tylko metadata dla subject2.
5. Respektować `Retry-After` z nagłówka przy HTTP 429 (obok obecnego sleep 1.2 s).
6. Test: mock `GET .../invoices/ksef/KSEF-1` → raw XML bytes.

### P2 — osobny task (nie w minimalnym patchu)

7. Implementacja `POST /invoices/exports` dla sync przyrostowego (HWM, duże wolumeny).
8. `GET /rate-limits` — opcjonalna diagnostyka przed sync.

---

## 8. Wpływ na zapis do bazy

Flow `sync_received_invoices` jest poprawny **po stronie IFG** (parse → Invoice → DB), ale wymaga **poprawnego `xml_bytes`** z oficjalnego GET. Obecna implementacja pobierania prawdopodobnie kończy się wyjątkiem w `_parse_invoice_content` → `skipped_parse++`, `saved=0`.

---

## Powiązane dokumenty

- `docs/KSEF_PURCHASE_SYNC_METADATA_FIX.md`
- `docs/KSEF_PURCHASE_API_INVESTIGATION.md`
- `docs/KSEF_METADATA_PROBE.md`
