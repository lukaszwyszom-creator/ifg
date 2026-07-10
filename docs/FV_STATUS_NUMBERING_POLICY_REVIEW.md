# Przegląd statusów FV sprzedaży vs polityka numeracji draft/locked

Data: 2026-05-22  
Zakres: analiza tylko — **bez zmian w kodzie**.

---

## 1. Znalezione statusy faktury sprzedaży

### Enum domenowy (`InvoiceStatus`)

| Wartość DB/API | Etykieta UI (PDF) | Istnieje? |
|----------------|-------------------|-----------|
| `ready_for_submission` | Gotowa do wysyłki | **Tak** — jedyny stan roboczy |
| `sending` | Wysyłanie / W toku | **Tak** |
| `accepted` | Zatwierdzona / OK (UPO) | **Tak** |
| `rejected` | Odrzucona | **Tak** |

**Inne statusy faktury sprzedaży w IFG nie występują.**

### Legacy / aliasy

| Wartość | Status |
|---------|--------|
| `draft` | **Usunięty z domeny** — migracja `0011_k1l2m3n4o5p6` mapuje `draft` → `ready_for_submission`. Mapper przy odczycie nadal akceptuje alias `draft` → `ready_for_submission`. |
| `ready`, `gotowa` | Tylko frontend (`invoiceOpenMode.js`) — traktowane jak niewysłane; backend ich nie zapisuje. |

### Powiązane pola (nie status, ale wpływają na KSeF)

| Pole | Model |
|------|--------|
| `ksef_reference_number` | `InvoiceORM` / `Invoice` — ustawiane przy sukcesie transmisji |
| `validation_status` | kolumna DB, nieużywana w logice numeracji |
| `payment_status` | osobny wymiar (`unpaid` / `partially_paid` / `paid`) — nie blokuje numeru |

### Statusy transmisji KSeF (`TransmissionStatus`) — kontekst lock

`queued` → `processing` → `submitted` → `waiting_status` → `success`  
oraz: `failed_temporary`, `failed_retryable`, `failed_permanent`

Przy błędach przejściowych (brak sesji, KSeF niedostępny) worker **cofa fakturę** z `sending` → `ready_for_submission`, zostawiając rekord transmisji w statusie retryable.

---

## 2. Maszyna stanów i workflow KSeF

```
ready_for_submission ──(submit)──► sending ──► accepted
                                      │
                                      └──► rejected ──(resubmit)──► sending
```

- **Create:** faktura sale od razu w `ready_for_submission` (brak osobnego `draft`).
- **Submit:** `TransmissionService` → status `sending`, tworzy transmisję `queued`.
- **Sukces:** transmisja `success` → faktura `accepted` + opcjonalnie `ksef_reference_number`.
- **Odrzucenie trwałe:** transmisja `failed_permanent` → faktura `rejected`.
- **Błąd przejściowy:** faktura wraca do `ready_for_submission`, transmisja `failed_retryable` / `failed_temporary`.
- **Resubmit z rejected:** bezpośrednie ustawienie `sending` (pomija formalną maszynę stanów dla `rejected` → `sending`).

Źródła: `app/domain/models/invoice.py`, `app/services/transmission_service.py`, `app/worker/job_handlers/submit_invoice.py`.

---

## 3. Edytowalność wg aktualnego IFG

| Status | Backend `is_invoice_editable` | Frontend `isInvoiceEditable` | Uwagi |
|--------|------------------------------|------------------------------|-------|
| `ready_for_submission` | Tak | Tak | Formularz + wysyłka KSeF |
| `rejected` | Tak | Tak | Poprawka + „Wyślij ponownie” |
| `sending` | Nie | Nie | Tylko podgląd |
| `accepted` | Nie | Nie | Tylko podgląd |

---

## 4. Ocena: czym jest `ready_for_submission`?

**Rekomendacja: wariant A — zwykły draft roboczy podlegający renumeracji.**

Uzasadnienie:

1. Migracja usunęła osobny status `draft`; komentarze w `invoice_service` i `mark_as_ready` traktują `ready_for_submission` jako stan przed wysyłką.
2. Faktura jest tworzona w tym statusie i jest **edytowalna**.
3. Numer może (i powinien) być nadany przy create, ale **nie jest jeszcze „zużyty” w KSeF** dopóki nie nastąpi skuteczna wysyłka.
4. `mark_as_ready` jest idempotentne — uzupełnia brakujący numer, nie zmienia istniejącego.

`ready_for_submission` **nie powinien** blokować numeru (wariant B) — to by uniemożliwiło renumerację roboczych FV i kolidowało z modelem „usuń środkową → przenumeruj”.

---

## 5. Rekomendowany model numeracji

| Status | Edycja | Usunięcie | Renumeracja draftów | Locked numer |
|--------|--------|-----------|---------------------|--------------|
| `ready_for_submission` | Tak | Tak* | Tak | **Nie*** |
| `sending` | Nie | Nie | Nie | **Tak** |
| `accepted` | Nie | Nie | Nie | **Tak** |
| `rejected` | Tak | Nie | Nie | **Tak** |

\* Usunięcie tylko gdy faktura nie była faktycznie wysłana do KSeF (patrz niżej).  
\*\* Wyjątek: `ready_for_submission` po **udanej próbie wysłania XML** (transmisja ≥ `submitted`) — numer locked mimo edytowalności statusu; usunięcie zabronione.

### Warunki blokady numeru (Locked = TAK, gdy którykolwiek):

1. **Status** ∈ `{sending, accepted, rejected}`
2. **`ksef_reference_number`** jest ustawione (faktura zaakceptowana w KSeF)
3. **Transmisja „po wysłaniu”** — istnieje transmisja w statusie:  
   `submitted`, `waiting_status`, `success`, `failed_permanent`  
   (numer P_2 trafił do KSeF lub próba zakończyła się odrzuceniem)

### Warunki, które **nie powinny** same blokować numeru:

- Transmisja wyłącznie w `queued` / `processing` / `failed_retryable` / `failed_temporary`, gdy faktura wróciła do `ready_for_submission` **przed** wysłaniem XML (np. brak sesji KSeF) — numer nadal roboczy, możliwe usunięcie i renumeracja.

### Uzasadnienie dla `rejected`:

- Faktura **edytowalna**, ale numer **locked** — XML z tym numerem był już wysłany; resubmit wymaga `number_local` (`require_number_local=True`), numer nie może się zmienić ani być zwolniony przez renumerację innych draftów.

---

## 6. Zgodność z planowanym modelem draft/locked

Planowany model (create → numer, delete draft → renumeracja, MAX+1 po locked) jest **zgodny z workflow IFG**, pod warunkiem doprecyzowania lock transmisji (sekcja 5), a nie „jakikolwiek rekord w `transmissions`”.

**Potencjalna luka w obecnej implementacji polityki:** lock na `has_transmission = true` (dowolny rekord) może zablokować numer faktury w `ready_for_submission` po błędzie przejściowym (brak sesji), mimo że IFG pozwala ją edytować i ponowić wysyłkę. Przed wdrożeniem warto zweryfikować, czy lock ma opierać się na **statusie transmisji**, nie na samym istnieniu wiersza.

---

## 7. Czy wdrożenie jest bezpieczne bez migracji danych?

**Tak — migracja schematu DB nie jest wymagana.**

| Aspekt | Ocena |
|--------|--------|
| Nowe kolumny | Nie potrzebne — wystarczą `status`, `number_local`, `ksef_reference_number`, `transmissions` |
| Legacy `draft` | Już znormalizowane do `ready_for_submission` (migracja 0011) |
| Faktury bez `number_local` | Mogą istnieć w starych danych — wymagają jednorazowego `mark-as-ready` / nadania numeru, nie migracji |
| Faktury `accepted` / `rejected` / `sending` | Numery muszą pozostać — lock po statusie je chroni |
| Brak UNIQUE na `number_local` | Ryzyko historyczne (duplikaty) — poza zakresem migracji; wymaga opcjonalnego audytu SQL przed wdrożeniem |

**Ryzyko operacyjne (bez migracji):** ręczne rekordy ze „złym” statusem (np. `ready_for_submission` + `ksef_reference_number`) — lock powinien uwzględniać oba sygnały.

---

## 8. Pliki źródłowe (odczyt)

- `app/domain/enums.py` — `InvoiceStatus`, `TransmissionStatus`
- `app/domain/models/invoice.py` — przejścia stanów
- `app/persistence/mappers/invoice_mapper.py` — alias `draft`, dozwolone statusy zapisu
- `app/persistence/models/invoice.py` — kolumny ORM
- `app/services/invoice_service.py` — edytowalność, create w `ready_for_submission`
- `app/services/transmission_service.py` — submit, sync statusów z KSeF
- `app/worker/job_handlers/submit_invoice.py` — cofanie do `ready_for_submission`
- `frontend-react/src/components/invoice/invoiceOpenMode.js` — edytowalność UI
- `alembic/versions/0011_k1l2m3n4o5p6_remove_draft_status.py` — usunięcie `draft`

---

## 9. Podsumowanie decyzyjne

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy `draft` istnieje? | Nie jako osobny status — zastąpiony przez `ready_for_submission` |
| Czy pozostałe 4 statusy istnieją? | Tak |
| `ready_for_submission` = draft czy pre-lock? | **Draft (A)** — renumeracja i usuwanie dozwolone |
| Kiedy lock numeru? | `sending`, `accepted`, `rejected`, `ksef_reference_number`, transmisja po wysłaniu XML |
| Migracja DB? | **Nie wymagana** |
| Wdrożenie numeracji draft/locked | **Bezpieczne** przy doprecyzowaniu reguły transmisji i ewentualnym backfillu brakujących `number_local` |
