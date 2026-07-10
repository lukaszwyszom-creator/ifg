# Model numeracji FV sprzedaży — draft vs locked

Data: 2026-05-22

## Problem

Faktury sprzedaży pokazywały ten sam numer roboczy (`01/06/2026`) lub zmieniały numer po utworzeniu kolejnej faktury. Przyczyną było dynamiczne nadawanie numerów w UI oraz brak kontrolowanej renumeracji po usunięciu draftu.

## Model biznesowy

### Draft (robocza, niewysłana)

| Cecha | Wartość |
|-------|---------|
| Status | `ready_for_submission` |
| Transmisja KSeF | brak |
| `ksef_reference_number` | brak |
| Numer | nadawany przy `create_invoice`, format DB `FV/{seq}/{MM}/{YYYY}` |
| Usuwanie | dozwolone (`DELETE /api/v1/invoices/{id}`) |
| Renumeracja | może zostać przenumerowana po usunięciu innego draftu w tym samym miesiącu |

### Locked (zablokowana)

Numer **nigdy** nie zmienia się, faktury **nie można usunąć**, gdy spełniony jest **którykolwiek** warunek:

| Warunek | Przykład |
|---------|----------|
| Status `sending` | w trakcie wysyłki do KSeF |
| Status `accepted` | zaakceptowana przez KSeF |
| Status `rejected` | odrzucona przez KSeF (numer z próby wysyłki) |
| `ksef_reference_number` ustawione | potwierdzenie KSeF |
| Istnieje rekord w `transmissions` | jakakolwiek próba wysyłki |

Implementacja: `InvoiceNumberPolicy.is_sale_number_locked()`.

### Nadawanie numeru przy tworzeniu

- `create_invoice` (sale) → `_allocate_number_local()` → **MAX(seq) + 1** w miesiącu `issue_date`.
- Nie wypełnia luk po fakturach locked (np. locked 01 + locked 02 → nowy draft = 03).

### Renumeracja po usunięciu draftu

1. Usuń draft (`delete_sale_invoice`).
2. Pobierz wszystkie sale z miesiąca, posortowane po `created_at`.
3. Zbierz sekwencje locked (pomiń przy aktualizacji).
4. Drafty przypisz kolejno do wolnych numerów, omijając zajęte przez locked.
5. Przykład: drafty 01, 02, 03 → usuń 02 → 03 staje się 02; A=01 bez zmian.

### mark_as_ready / wysyłka

- Jeśli `number_local` już istnieje — **nie zmieniaj** (idempotentne).
- Po przejściu w `sending` / `accepted` / `rejected` numer staje się locked przez status.

## Źródło prawdy

- **Backend** — nadawanie, renumeracja, usuwanie.
- **Frontend** (`InvoiceCardList`) — wyświetla wyłącznie `number_local` z API (`backend:number_local`). Brak `ui:temporary_sequence`.

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/services/invoice_number_policy.py` | Parsowanie, locked/draft, renumeracja, MAX+1 |
| `app/services/invoice_service.py` | `delete_sale_invoice`, `_renumber_draft_invoices_in_month` |
| `app/persistence/repositories/invoice_repository.py` | `list_sale_in_month`, `delete_by_id`, `update_number_local`, MAX seq |
| `app/persistence/repositories/transmission_repository.py` | `get_invoice_ids_with_transmissions` |
| `app/api/routers/invoices.py` | `DELETE /{invoice_id}` |
| `frontend-react/src/api/invoices.js` | `delete()` |
| `frontend-react/src/components/invoice/InvoiceCardList.jsx` | numer z backendu, przycisk Usuń |
| `frontend-react/src/components/invoice/InvoiceCardList.module.css` | styl przycisku Usuń |
| `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | test E (brak UI sequence) |
| `tests/unit/test_invoice_numbering_regression.py` | testy A–D + locked delete |

## Testy

```bash
pytest tests/unit/test_invoice_numbering_regression.py -q
node --test frontend-react/src/components/invoice/invoiceCardListNumbering.test.js
```

| Test | Scenariusz |
|------|------------|
| A | Dwa create → 01, 02; odczyt bez zmian |
| B | A=01, B=02, C=03; usuń B → C=02 |
| C | A locked=01; B=02, C=03; usuń B → A=01, C=02 |
| D | Locked 01+02 → nowy draft = 03 |
| E | Brak `ui:temporary_sequence` w InvoiceCardList.jsx |

## Migracja DB

**Nie wymagana.** Wykorzystywane istniejące pola:
- `invoices.number_local`
- `invoices.status`
- `invoices.ksef_reference_number`
- `invoices.direction`
- `invoices.issue_date`
- tabela `transmissions`

## Ryzyka

| Ryzyko | Opis |
|--------|------|
| Stare FV bez numeru | Faktury sprzed zmiany bez `number_local` wymagają `mark-as-ready` |
| Brak UNIQUE na `number_local` | Race przy równoległym create — `exists_by_number` + IntegrityError retry w mark_as_ready; create bez retry |
| Usunięcie draftu | Kaskada usuwa pozycje, transmisje, alokacje płatności — nieodwracalne |
| REJECTED = locked | Odrzucona faktura nie podlega renumeracji ani usunięciu przez API (zgodnie z modelem wysyłki) |
| Frontend confirm | Usuwanie wymaga potwierdzenia `window.confirm` |

## Weryfikacja manualna

1. Utwórz 3 faktury w czerwcu → 01, 02, 03.
2. Usuń środkową → trzecia staje się 02.
3. Wyślij pierwszą do KSeF → usuń próba na niej powinna zwrócić błąd 409.
4. Odśwież listę — numery zgodne z DB.
