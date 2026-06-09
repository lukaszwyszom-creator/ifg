# KSeF — diagnostyka synchronizacji faktur zakupowych (0 wyników)

Data: 2026-05-22  
Pliki analizowane: `app/integrations/ksef/client.py`, `app/services/ksef_session_service.py`  
Kontekst: sesja aktywna, zakres 2026-03-11 → 2026-06-09, faktury widoczne w portalu KSeF, sync zwraca 0.

---

## 1. Wykorzystywane endpointy

### `query_received_invoices` (client.py)

**GET (kolejno, pierwszy sukces kończy próby):**

| # | Path |
|---|------|
| 1 | `/sessions/{session_reference}/invoices/received` |
| 2 | `/sessions/{session_reference}/invoices/query` |
| 3 | `/sessions/{session_reference}/invoices` |

**POST (fallback — tylko gdy żaden GET nie zwrócił sukcesu HTTP):**

| # | Path |
|---|------|
| 1 | `/sessions/{session_reference}/invoices/query` |
| 2 | `/invoices/query` |

**Polling (gdy odpowiedź zawiera `referenceNumber`):**

- `GET {poll_path_prefix}/{query_ref}` — do 20 prób co 3 s

**Pobranie treści faktury:**

- `GET /invoices/{ksefReferenceNumber}` → deszyfracja AES-256-CBC kluczem sesji

### `sync_received_invoices` (ksef_session_service.py)

- Wywołuje `query_received_invoices` w pętli `subject2` → `subject1` → `subject3`
- Importuje wynik z pierwszego subjectType z `len(batch) > 0`

---

## 2. Parametry filtrujące wysyłane do KSeF

### GET query params (identyczne dla wszystkich kandydatów GET):

```json
{
  "invoiceType": "received",
  "subjectType": "subject2|subject1|subject3",
  "invoicingDateFrom": "2026-03-11",
  "invoicingDateTo": "2026-06-09"
}
```

Daty pochodzą z `date.isoformat()` — format `YYYY-MM-DD`.

### POST body (`queryCriteria`):

```json
{
  "queryCriteria": {
    "invoiceType": "received",
    "subjectType": "subject2|subject1|subject3",
    "invoicingDateFrom": "2026-03-11",
    "invoicingDateTo": "2026-06-09"
  }
}
```

**Brak innych filtrów:** NIP, `dateType`, paginacja, `ksefNumber`, `invoiceNumber` — nie są wysyłane.

---

## 3. Alternatywne parametry KSeF v2 (potencjalnie wymagane)

Na podstawie samego kodu IFG — **nie weryfikowano względem OpenAPI MF**. Możliwe rozbieżności:

| Obszar | Co robi IFG | Ryzyko |
|--------|-------------|--------|
| Typ daty | `invoicingDateFrom/To` | KSeF może filtrować po dacie wystawienia (`issueDate`) lub innym polu — faktury poza `invoicingDate` nie wrócą |
| Zakres sesyjny vs globalny | Preferuje GET pod `/sessions/{ref}/...` | Endpointy sesyjne mogą zwracać faktury powiązane z bieżącą sesją online, **nie pełną historię zakupów NIP** |
| Query asynchroniczne | POST `/invoices/query` jako fallback | W prod historyczne zapytania mogą wymagać **wyłącznie** POST async query, nie GET sync |
| `invoiceType: "received"` | Hardcoded | W KSeF v2 typ może wymagać innej wartości enum lub dodatkowych pól w `queryCriteria` |

---

## 4. subjectType — czy prawidłowy?

| Wartość | Typowa rola w FA | Zastosowanie dla FV zakupowych |
|---------|------------------|--------------------------------|
| `subject2` | Nabywca (podmiot 2) | **Domyślnie pierwszy** — logicznie poprawny, gdy firma jest nabywcą |
| `subject1` | Sprzedawca / podmiot 1 | Faktury, gdzie firma wystawiła dokument (sprzedaż) |
| `subject3` | Inne role (np. płatnik, podmiot trzeci) | Edge cases |

**Fallback w session_service** próbuje wszystkie trzy kolejno. Jeśli w logach widać `result_count=0` dla **każdego** subjectType — problem leży raczej w endpoincie/flow query niż w samym subjectType.

Jeśli w logach sync kończy się na `subject2` z count=0, a subject1/3 nie są logowane — to inny problem (błąd przed pętlą).

---

## 5. Zapytanie bez subjectType

**W obecnym kodzie: niemożliwe.**

- `subjectType` jest **zawsze** ustawiony w GET params (linia 353) i POST body (linia 428).
- Brak gałęzi ani parametru opcjonalnego do pominięcia pola.
- Nie wiadomo z kodu, czy KSeF v2 akceptuje brak `subjectType` — wymaga testu manualnego curl/Postman.

---

## 6. Krytyczna obserwacja w client.py — prawdopodobna główna przyczyna

```411:414:app/integrations/ksef/client.py
            # Sukces bez listy faktur traktujemy jako pusty wynik.
            logger.info("KSeF received invoices via %s: empty result", candidate)
            invoice_refs = []
            break
```

Po **pierwszym udanym GET** (HTTP 200) z pustą listą faktur:

1. Ustawiane jest `get_candidate_succeeded = True`
2. Pętla GET jest **przerywana** (`break`)
3. POST fallback **nie jest wywoływany**, bo warunek w linii 420 wymaga `not get_candidate_succeeded`:

```420:420:app/integrations/ksef/client.py
        if not invoice_refs and query_ref is None and not get_candidate_succeeded:
```

**Skutek:** jeśli `/sessions/{ref}/invoices/received` odpowiada 200 z `{}` lub pustą listą (typowe dla sesji online bez historycznych FV), IFG **nigdy nie dochodzi** do POST `/invoices/query`, który w KSeF v2 jest standardową ścieżką do historycznego query zakupów.

To tłumaczy scenariusz: sesja OK, zakres dat OK, faktury w portalu KSeF, sync = 0.

---

## 7. Weryfikacja w logach (checklist)

Szukaj wpisów:

```
KSeF query_received_invoices GET attempt: endpoint=/sessions/.../invoices/received params={...}
KSeF received invoices via /sessions/.../invoices/received: empty result
```

Jeśli występuje `empty result` **bez** kolejnych:

```
KSeF query_received_invoices POST attempt: endpoint=/invoices/query
```

→ potwierdza bug early-exit.

Sprawdź też czy dla wszystkich trzech subjectType jest `result_count=0`.

---

## Potencjalne przyczyny (ranking)

1. **Early-exit na pustym GET** — blokuje POST `/invoices/query` (najbardziej prawdopodobne w kodzie).
2. **Sesyjne GET vs globalne query** — `/sessions/{ref}/invoices/received` nie zwraca historycznych FV zakupowych NIP.
3. **Zły typ daty** — `invoicingDate` vs data wystawienia na fakturach w KSeF.
4. **subjectType** — mniej prawdopodobne przy fallbacku 2→1→3, chyba że wszystkie zwracają 0 z tego samego powodu co pkt 1–2.
5. **Brak subjectType** — nie testowane; obecnie zawsze wysyłany.

---

## Rekomendowana poprawka (kolejność)

1. **Naprawić flow w `query_received_invoices`:**
   - Nie robić `break` na pustym GET — kontynuować kolejne GET kandydaty.
   - Jeśli wszystkie GET puste / bez `referenceNumber` → **zawsze** próbować POST `/invoices/query` (usunąć warunek `not get_candidate_succeeded`).
   - Alternatywnie: dla sync zakupów od razu preferować POST `/invoices/query` z pollingiem.

2. **Dodać diagnostyczne logowanie** (przy pustym wyniku): klucze JSON odpowiedzi, `processingCode`, czy zwrócono `referenceNumber` — bez tokenów.

3. **Przetestować w prod/test curl:**
   - POST `/invoices/query` z tym samym `queryCriteria`
   - wariant bez `subjectType`
   - wariant z `issueDateFrom/To` zamiast `invoicingDateFrom/To`

4. **Konfiguracja:** env `KSEF_PURCHASES_SUBJECT_TYPE` + opcjonalnie pominięcie subjectType po weryfikacji z OpenAPI MF.

---

## Ograniczenia tej analizy

- Analiza wyłącznie dwóch plików — bez OpenAPI KSeF MF, bez logów prod, bez testów HTTP.
- Nie wprowadzono zmian w kodzie (zgodnie z poleceniem).
