# KSeF v2 — analiza API pobierania faktur zakupowych (prod)

Data: 2026-06-10  
Pliki: `app/integrations/ksef/client.py`, `docs/KSEF_PURCHASE_DIAGNOSTICS.md`, `docs/KSEF_EMPTY_SYNC_HANDLING.md`  
Base URL prod: `https://api.ksef.mf.gov.pl/v2`

---

## 1. Endpointy używane przez IFG (`query_received_invoices`)

| Krok | Metoda | Path | Uwagi |
|------|--------|------|-------|
| Lista (preferowane) | GET | `/sessions/{session_reference}/invoices/received` | + query params |
| Lista | GET | `/sessions/{session_reference}/invoices/query` | + query params |
| Lista | GET | `/sessions/{session_reference}/invoices` | + query params, **prod: 200 + pusta lista** |
| Query async (fallback) | POST | `/sessions/{session_reference}/invoices/query` | **prod: 405** |
| Query async (fallback) | POST | `/invoices/query` | **prod: 404** |
| Polling | GET | `{poll_path_prefix}/{query_ref}` | gdy GET/POST zwróci `referenceNumber` |
| Pobranie XML | GET | `/invoices/{ksefReferenceNumber}` | deszyfracja AES kluczem sesji online |

Sesja otwierana przez `POST /sessions/online`, a query idzie pod `/sessions/{session_reference}/...` (nie `/sessions/online/{ref}/...`).

**IFG nie używa** (wg oficjalnej dokumentacji KSeF v2 MF):

- `POST /invoices/query/metadata` — metadane faktur (paginacja)
- `POST /invoices/exports` — asynchroniczny eksport paczek (rekomendowany sync)
- `GET /invoices/exports/{referenceNumber}` — status/pobranie paczki

---

## 2. Parametry GET `/sessions/{session}/invoices` (i warianty)

IFG wysyła **4 warianty** query params (brute-force diagnostyczny):

| # | Parametry |
|---|-----------|
| 1 | `invoiceType=received`, `subjectType`, `invoicingDateFrom`, `invoicingDateTo` |
| 2 | `subjectType`, `invoicingDateFrom`, `invoicingDateTo` |
| 3 | `invoiceType=received`, `invoicingDateFrom`, `invoicingDateTo` |
| 4 | `invoicingDateFrom`, `invoicingDateTo` |

Wartości dat: `YYYY-MM-DD` (`date.isoformat()`).

POST fallback (`queryCriteria`) — **tylko wariant 1**:

```json
{
  "invoiceType": "received",
  "subjectType": "subject2|subject1|subject3",
  "invoicingDateFrom": "...",
  "invoicingDateTo": "..."
}
```

**Brak w IFG:** `dateRange`, `dateType`, paginacja, NIP kontrahenta, `subjectAuthorized`, ISO datetime z czasem.

---

## 3. Inne pola dat (KSeF v2 vs IFG)

W oficjalnym API v2 (OpenAPI MF, `POST /invoices/query/metadata`, `POST /invoices/exports`) daty są w obiekcie:

```json
"dateRange": {
  "dateType": "Issue | Invoicing | PermanentStorage | ...",
  "from": "2026-01-01T00:00:00Z",
  "to": "2026-01-31T23:59:59Z"
}
```

| dateType (MF) | Znaczenie | IFG |
|---------------|-----------|-----|
| `Issue` | data wystawienia | ❌ nie używane |
| `Invoicing` | data fakturowania | ⚠️ płaskie `invoicingDateFrom/To` (inny format) |
| `PermanentStorage` | trwałe zapisane w KSeF | ❌ rekomendowane do sync przyrostowego |
| `Acquisition` | (wspominane w materiałach pomocniczych) | ❌ |

**Hipoteza:** faktury widoczne w portalu po dacie wystawienia / permanent storage nie trafiają do wyniku filtrowania po płaskim `invoicingDateFrom` w GET sesyjnym.

---

## 4. subjectType

| Wartość IFG | Rola (FA / MF) | Użycie |
|-------------|----------------|--------|
| `subject2` | nabywca (FV zakupowe) | domyślnie, pierwszy w fallbacku |
| `subject1` | wystawca | drugi w fallbacku |
| `subject3` | podmiot trzeci | trzeci w fallbacku |

**Nie testowane w IFG:** `subjectAuthorized` (podmiot uprawniony).

Fallback w `ksef_session_service`: subject2 → subject1 → subject3. Wariant GET #3 i #4 **pomija** `subjectType`.

Oficjalne API wymaga `subjectType` w body (nie query string) i musi być **zgodny z kontekstem NIP** tokena.

---

## 5. Pobieranie bez filtrów dat

- **IFG:** zawsze wysyła `invoicingDateFrom` + `invoicingDateTo` (w każdym wariancie GET i POST).
- **KSeF v2 (`/invoices/query/metadata`, `/invoices/exports`):** `dateRange` jest wymagany w dokumentacji MF.
- **Wniosek:** pełny brak filtra dat w prod jest mało prawdopodobny; ewentualny test to bardzo szeroki `dateRange` (np. 2 lata) z `dateType=PermanentStorage`.

---

## 6. Stan obecny (po poprawkach IFG)

| Problem | Status |
|---------|--------|
| Early-exit GET → brak POST | ✅ naprawione (kontynuacja wariantów + POST) |
| 502 gdy POST 404/405 | ✅ zwraca `[]` + log |
| **0 faktur mimo portalu KSeF** | ❌ **nadal otwarte** |

Prod: GET `/sessions/.../invoices` → 200 pusta lista; POST query → niedostępne. IFG **nie trafia** w oficjalne API pobierania.

---

## 7. Najbardziej prawdopodobne przyczyny braku faktur

1. **Zły surface API** — IFG używa legacy/sesyjných GET+flat params; prod v2 oczekuje `POST /invoices/query/metadata` lub `POST /invoices/exports`.
2. **Zły kształt filtra dat** — płaskie `invoicingDateFrom/To` zamiast `dateRange.dateType` (Issue vs Invoicing vs PermanentStorage).
3. **Kontekst sesji online vs query globalne** — GET pod `/sessions/{ref}/invoices` zwraca faktury powiązane z sesją, nie pełną historię NIP.
4. **subjectType** — mniej prawdopodobne przy fallbacku 2→1→3, chyba że wszystkie warianty uderzają w ten sam błędny endpoint.
5. **POST `/invoices/query` nie istnieje w prod** — potwierdzone 404; IFG nigdy nie uruchomi async query w prod.

---

## 8. Proponowany następny eksperyment diagnostyczny

**Ręczny curl na prod** (aktywny token sesji, ten sam NIP co portal):

```bash
# 1. Metadane — nabywca, data trwałego zapisu (ISO 8601)
curl -s -X POST "https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subjectType": "Subject2",
    "dateRange": {
      "dateType": "PermanentStorage",
      "from": "2026-03-01T00:00:00Z",
      "to": "2026-06-09T23:59:59Z"
    }
  }' | jq .

# 2. Powtórz z dateType: "Issue" i "Invoicing"
# 3. Powtórz subjectType: "Subject1", "Subject3"
```

Porównaj liczbę rekordów z portalem MF. Jeśli metadata zwraca faktury → właściwa ścieżka to **`/invoices/query/metadata` + `/invoices/{ksefNumber}`**, nie GET sesyjny.

Opcjonalnie test eksportu:

```bash
curl -s -X POST "https://api.ksef.mf.gov.pl/v2/invoices/exports" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "filters": { "subjectType": "Subject2", "dateRange": { ... } }, "encryption": { ... } }'
```

(wymaga klucza szyfrowania jak przy sesji online)

---

## 9. Dodatkowe logi diagnostyczne (bez zmiany logiki)

| Log | Cel |
|-----|-----|
| `KSeF GET response keys=%s has_referenceNumber=%s` przy pustym wyniku | struktura JSON odpowiedzi |
| `KSeF GET empty result variant=%d endpoint=%s params=%s` | który wariant brute-force zwrócił pusty 200 |
| `KSeF POST fallback status=%s exceptionCode=%s body_snippet=%s` | pełniejszy błąd 404/405/400 |
| `session_reference=%s environment=%s` na początku query | korelacja sesji online vs query |
| `subject_type=%s date_from=%s date_to=%s` w raporcie sync (już częściowo) | parzystość z curl |
| Liczba elementów w `invoiceList` / `invoices` / `items` przed `_extract_invoice_refs` | czy parser traci dane |

Bez logowania tokenów, `encryptedInvoiceContent`, certyfikatów.

---

## 10. Rekomendacja docelowa (poza zakresem tej analizy)

1. Zweryfikować OpenAPI prod: https://api.ksef.mf.gov.pl/docs/v2/
2. Przepiąć sync zakupów na `POST /invoices/query/metadata` (MVP) lub `POST /invoices/exports` (prod sync)
3. Użyć `dateRange.dateType=PermanentStorage` dla sync przyrostowego (HWM)
4. Zachować `GET /invoices/{ksefNumber}` + deszyfrację dla pobrania XML

---

## Ograniczenia

Analiza oparta na kodzie IFG i publicznej dokumentacji KSeF MF — bez wykonania curl na prod w tym raporcie.
