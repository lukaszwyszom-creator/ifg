# KSeF — patch P0 sync zakupów (metadata + pobranie XML)

Data: 2026-06-10 (rev. 2 — ograniczenie zakresu)  
Audyt: `docs/KSEF_OFFICIAL_API_AUDIT_2026-06-10.md`

---

## Co było błędne

1. **Pobranie XML:** `GET /invoices/{ksefNumber}` + JSON/decrypt — path nieoficjalny.
2. **Paginacja metadata:** `totalCount` zamiast `hasMore`.
3. **Zbyt szeroki patch:** wspólna `_download_received_invoices` stosowała `/invoices/ksef/` także dla fallbacku sesyjnego.

---

## Co zmieniono (rev. 2)

### Rozdzielone ścieżki pobierania

| Ścieżka | Metoda | Endpoint pobrania XML |
|---------|--------|---------------------|
| **Subject2 + metadata** | `_download_metadata_purchase_invoices` | `GET /invoices/ksef/{ksefNumber}` + `Accept: application/xml` + `response.content` |
| **Fallback sesyjny (legacy)** | `_download_legacy_session_invoices` | `GET /invoices/{ref}` + `_parse_invoice_content` (decrypt sesyjny) — **bez zmian semantyki** |

### Paginacja metadata

- Iteracja po **`hasMore`**, nie `totalCount`.

### Throttling

- **1.2 s pacing tylko** dla metadata query i metadata download (`_pace_purchase_request` / `_mark_purchase_request`).
- **`_request_with_retry`** — bez globalnego pacingu (brak wpływu na sprzedaż / sesję online).
- HTTP **429:** nadal `Retry-After` w `_request_with_retry` (wszystkie endpointy).

---

## Endpointy (Subject2 prod)

1. `POST /v2/invoices/query/metadata`
2. `GET /v2/invoices/ksef/{ksefNumber}`

Fallback sesyjny: niezmienione legacy endpointy (poza zakresem P0).

---

## Testy

```bash
.venv/bin/python -m pytest tests/unit/test_ksef_client_retry.py -q
```

- `test_subject2_uses_metadata_query_and_official_ksef_download_path` — metadata → `/invoices/ksef/`
- `test_subject1_session_fallback_uses_legacy_path_not_ksef` — legacy → `/invoices/{ref}`, bez metadata

---

## Deploy DS723+

**Tak** — wymagany deploy backendu po commicie.

---

## Ryzyka / następny krok

| Ryzyko | Status |
|--------|--------|
| Legacy fallback na prod (pusta lista) | bez zmian, poza główną ścieżką |
| Limit 20 req/h metadata | pacing lokalny 1.2 s |
| Duże wolumeny | P1: `POST /invoices/exports` |

**Następny krok (P1):** exports + wyłączenie legacy fallback na prod.
