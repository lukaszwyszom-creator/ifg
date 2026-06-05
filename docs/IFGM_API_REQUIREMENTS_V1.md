# IFGM API REQUIREMENTS V1

Wymagania API dla aplikacji mobilnej IFGM (Imperium Faktur G Mobile).

Dokument źródłowy UX: `docs/IFGM_USER_FLOW_V1.md`.

## Założenia architektoniczne

* IFGM nie posiada własnego backendu.
* IFGM korzysta wyłącznie z istniejącego API IFG.
* Jedna baza danych PostgreSQL.
* Jedno źródło prawdy.
* Brak synchronizacji między systemami.

```text
iPhone
  ↓
IFGM (Expo)
  ↓
IFG API (DS723+)
  ↓
PostgreSQL
```

Prefiks proponowanych endpointów mobilnych: `/api/mobile/`.

Autoryzacja: nagłówek `Authorization: Bearer <JWT>` (ten sam token co desktop IFG).

---

## 1. Dashboard

Agregat danych dla ekranu startowego — kafel główny, KPI, nagłówek KSeF, licznik powiadomień.

### Wymagane dane

* sprzedaż netto
* zakup netto
* VAT do zapłaty / odliczenia
* liczba dłużników (kontrahentów z należnością)
* suma należności
* kwota należności po terminie
* liczba wierzycieli (dostawców ze zobowiązaniem)
* suma zobowiązań
* kwota zobowiązań po terminie
* liczba płatności do przypisania
* suma płatności do przypisania
* liczba nowych dokumentów KSeF (od ostatniej synchronizacji lub w okresie — do ustalenia przy implementacji)
* data ostatniej synchronizacji KSeF
* liczba aktywnych powiadomień
* ostatnie zakupy z KSeF (skrót listy na dole Dashboardu)

### Endpoint

```http
GET /api/mobile/dashboard?period=2026-05
```

| Parametr | Opis |
|----------|------|
| `period` | opcjonalny, format `YYYY-MM`; domyślnie bieżący miesiąc kalendarzowy |

### Przykładowa odpowiedź

```json
{
  "period": "2026-05",
  "sales_net": 125430.00,
  "purchase_net": 48200.00,
  "vat_balance": 8940.00,
  "vat_label": "due",
  "debtors_count": 7,
  "debtors_total_due": 23100.00,
  "debtors_overdue_due": 4850.00,
  "creditors_count": 5,
  "creditors_total_due": 8700.00,
  "creditors_overdue_due": 1200.00,
  "unassigned_payments_count": 3,
  "unassigned_payments_total": 12500.00,
  "ksef_new_invoices_count": 3,
  "ksef_last_sync_at": "2026-05-22T08:02:00+02:00",
  "ksef_connection_status": "connected",
  "notifications_active_count": 3,
  "recent_purchase_invoices": [
    {
      "id": "uuid",
      "supplier_name": "ORLEN S.A.",
      "number": "FZ/2026/05/1847",
      "amount_gross": 1842.50,
      "issue_date": "2026-05-28"
    }
  ]
}
```

| Pole | Opis |
|------|------|
| `vat_balance` | dodatni = do zapłaty, ujemny = do odliczenia |
| `vat_label` | `"due"` \| `"refund"` — etykieta dla UI |
| `ksef_connection_status` | `"connected"` \| `"disconnected"` \| `"error"` |

---

## 2. Powiadomienia

Lista aktywnych spraw wymagających działania (centrum spraw — nie push).

Zdarzenia zbiorcze zwracane jako jeden wpis z `count > 1`; nawigacja przez `target_type` + opcjonalnie `target_id`.

### Typy

| `type` | Opis |
|--------|------|
| `payment_unassigned` | płatności do przypisania |
| `ksef_new_invoice` | nowe faktury zakupowe z KSeF |
| `debtor_overdue` | przeterminowane należności |
| `creditor_overdue` | przeterminowane zobowiązania |
| `ksef_sync_error` | błąd synchronizacji KSeF |

### Endpoint

```http
GET /api/mobile/notifications
```

### Pola elementu listy

| Pole | Typ | Opis |
|------|-----|------|
| `id` | string (uuid) | identyfikator wpisu |
| `type` | string | typ zdarzenia (patrz tabela) |
| `title` | string | np. „Płatności do przypisania” |
| `subtitle` | string | np. „3 transakcje · 12 500 zł” |
| `count` | integer | liczba elementów (1 = pojedyncze, >1 = zbiorcze) |
| `created_at` | datetime ISO | czas powstania / ostatniej aktualizacji |
| `target_type` | string | typ ekranu docelowego (patrz poniżej) |
| `target_id` | string \| null | id rekordu gdy `count = 1`; null gdy zbiorcze |

### `target_type` — nawigacja w IFGM

| Wartość | Ekran docelowy |
|---------|----------------|
| `unassigned_payments` | lista Płatności do przypisania |
| `unassigned_payment` | decyzja przypisania (konkretna płatność) |
| `purchase_invoices` | lista Faktur zakupu (filtr: nowe z KSeF) |
| `purchase_invoice` | podgląd faktury zakupu |
| `debtor` | Szczegóły dłużnika |
| `debtors` | lista Dłużników |
| `creditor` | Szczegóły wierzyciela |
| `creditors` | lista Wierzycieli |
| `ksef` | ekran KSeF |

### Przykładowa odpowiedź

```json
{
  "items": [
    {
      "id": "uuid-1",
      "type": "payment_unassigned",
      "title": "Płatności do przypisania",
      "subtitle": "3 transakcje · 12 500 zł",
      "count": 3,
      "created_at": "2026-05-22T07:45:00+02:00",
      "target_type": "unassigned_payments",
      "target_id": null
    },
    {
      "id": "uuid-2",
      "type": "ksef_new_invoice",
      "title": "Nowe faktury KSeF",
      "subtitle": "2 dokumenty",
      "count": 2,
      "created_at": "2026-05-22T08:02:00+02:00",
      "target_type": "purchase_invoices",
      "target_id": null
    }
  ],
  "active_count": 3
}
```

---

## 3. Dłużnicy

### Lista

```http
GET /api/mobile/debtors
```

| Pole | Opis |
|------|------|
| `id` | identyfikator kontrahenta |
| `name` | nazwa kontrahenta |
| `total_due` | suma zadłużenia |
| `overdue_due` | kwota po terminie |
| `invoices_count` | liczba faktur |
| `overdue_invoices_count` | liczba faktur po terminie |
| `last_note` | skrót ostatniej notatki (max 2 linie w UI) |
| `last_contact_at` | data ostatniego kontaktu |

### Szczegóły

```http
GET /api/mobile/debtors/{id}
```

| Pole | Opis |
|------|------|
| `id`, `name` | dane kontrahenta |
| `phone` | numer telefonu (dla akcji Zadzwoń) |
| `total_due` | suma zadłużenia |
| `last_note` | pełna treść ostatniej notatki |
| `notes_history` | lista starszych notatek |
| `contact_history` | historia kontaktów |
| `invoices` | lista faktur: `id`, `number`, `amount_gross`, `due_date`, `days_overdue` |

### Dodanie notatki

```http
POST /api/mobile/debtors/{id}/notes
```

Payload:

```json
{
  "text": "Treść notatki windykacyjnej"
}
```

Odpowiedź: utworzona notatka (`id`, `text`, `created_at`).

---

## 4. Wierzyciele

Analogicznie do Dłużników.

### Lista

```http
GET /api/mobile/creditors
```

Pola jak w `GET /api/mobile/debtors` (`name` = dostawca).

### Szczegóły

```http
GET /api/mobile/creditors/{id}
```

Pola jak w szczegółach dłużnika; `invoices` — faktury zakupowe.

### Dodanie notatki

```http
POST /api/mobile/creditors/{id}/notes
```

Payload:

```json
{
  "text": "Treść notatki"
}
```

---

## 5. Płatności do przypisania

Mobilka akceptuje propozycje dopasowania z IFG — bez pełnej dekretacji wielowierszowej (desktop).

### Lista

```http
GET /api/mobile/unassigned-payments
```

| Pole | Opis |
|------|------|
| `id` | identyfikator transakcji |
| `amount` | kwota wpłaty |
| `counterparty` | kontrahent / tytuł |
| `booked_at` | data księgowania |
| `confidence` | `"full"` \| `"partial"` \| `"none"` — zgodność propozycji |
| `proposed_matches` | skrót propozycji (faktury + kwoty) |

### Szczegóły

```http
GET /api/mobile/unassigned-payments/{id}
```

Rozszerzone pola decyzji:

* `amount`, `counterparty`, `booked_at`
* `proposed_matches[]`: `{ "invoice_id", "invoice_number", "invoice_type", "amount", "contractor_name" }`
* `confidence`

### Akceptacja propozycji

```http
POST /api/mobile/unassigned-payments/{id}/assign
```

Payload:

```json
{
  "invoice_ids": ["uuid-1", "uuid-2"],
  "allocations": [
    { "invoice_id": "uuid-1", "amount": 1230.00 },
    { "invoice_id": "uuid-2", "amount": 500.00 }
  ]
}
```

Scenariusze UX (patrz USER FLOW): jedna wpłata → jedna faktura; jedna wpłata → wiele faktur; płatność częściowa.

---

## 6. Faktury sprzedaży

### Lista

```http
GET /api/mobile/sales-invoices?period=2026-05
```

| Pole | Opis |
|------|------|
| `id` | identyfikator |
| `number` | numer faktury |
| `contractor_name` | kontrahent |
| `amount_gross` | kwota brutto |
| `payment_status` | `"paid"` \| `"partial"` \| `"unpaid"` \| `"overdue"` |
| `due_date` | termin płatności |

### Szczegóły / podgląd

```http
GET /api/mobile/sales-invoices/{id}
```

Dane listy + pola do podglądu read-only (np. `preview_html_url` lub `preview_html` — do ustalenia przy implementacji).

---

## 7. Faktury zakupu

### Lista

```http
GET /api/mobile/purchase-invoices?period=2026-05
```

| Pole | Opis |
|------|------|
| `id` | identyfikator |
| `number` | numer dokumentu |
| `supplier_name` | dostawca |
| `amount_gross` | kwota |
| `payment_status` | status płatności |
| `issue_date` | data wystawienia |
| `source` | opcjonalnie `"ksef"` \| `"manual"` |

Filtr `?source=ksef` — lista po tapnięciu powiadomienia „Nowe faktury KSeF”.

### Szczegóły / podgląd

```http
GET /api/mobile/purchase-invoices/{id}
```

Dane listy + podgląd read-only.

---

## 8. KSeF

IFGM nie łączy się z KSeF bezpośrednio — wyłącznie przez IFG API.

### Status

```http
GET /api/mobile/ksef/status
```

| Pole | Opis |
|------|------|
| `status` | `"connected"` \| `"disconnected"` \| `"error"` |
| `last_sync_at` | data ostatniej synchronizacji |
| `new_invoices_count` | liczba nowych faktur zakupowych |
| `last_error` | opcjonalny komunikat przy `status = error` |

### Synchronizacja ręczna

```http
POST /api/mobile/ksef/sync
```

Odpowiedź: `{ "status": "started" \| "completed", "last_sync_at", "new_invoices_count" }`.

Automatyczna synchronizacja IFG (08:00, 15:00) — bez endpointu mobilnego; status odświeżany przez `GET .../ksef/status` i Dashboard.

---

## 9. Uwierzytelnianie

### Założenia MVP

* logowanie istniejącym użytkownikiem IFG
* token JWT (ten sam mechanizm co frontend desktop)
* brak osobnego systemu użytkowników mobilnych
* brak rejestracji w IFGM

### Proponowany przepływ

1. `POST /api/auth/login` — istniejący endpoint IFG (login + hasło → JWT).
2. Wszystkie żądania `/api/mobile/*` z nagłówkiem `Authorization: Bearer <token>`.
3. Wygasły token → `401` → ekran logowania w IFGM.

---

## 10. MVP API Checklist

| Funkcja | Endpoint wymagany | Priorytet |
|---------|-------------------|-----------|
| Dashboard | `GET /api/mobile/dashboard` | MVP |
| Powiadomienia | `GET /api/mobile/notifications` | MVP |
| Dłużnicy — lista | `GET /api/mobile/debtors` | MVP |
| Dłużnicy — szczegóły | `GET /api/mobile/debtors/{id}` | MVP |
| Dłużnicy — notatka | `POST /api/mobile/debtors/{id}/notes` | MVP |
| Wierzyciele — lista | `GET /api/mobile/creditors` | MVP |
| Wierzyciele — szczegóły | `GET /api/mobile/creditors/{id}` | MVP |
| Wierzyciele — notatka | `POST /api/mobile/creditors/{id}/notes` | MVP |
| Płatności — lista | `GET /api/mobile/unassigned-payments` | MVP |
| Płatności — szczegóły | `GET /api/mobile/unassigned-payments/{id}` | MVP |
| Płatności — przypisanie | `POST /api/mobile/unassigned-payments/{id}/assign` | MVP |
| Faktury sprzedaży — lista | `GET /api/mobile/sales-invoices` | MVP |
| Faktury sprzedaży — podgląd | `GET /api/mobile/sales-invoices/{id}` | MVP |
| Faktury zakupu — lista | `GET /api/mobile/purchase-invoices` | MVP |
| Faktury zakupu — podgląd | `GET /api/mobile/purchase-invoices/{id}` | MVP |
| KSeF — status | `GET /api/mobile/ksef/status` | MVP |
| KSeF — sync | `POST /api/mobile/ksef/sync` | MVP |
| Logowanie | istniejący `POST /api/auth/login` | MVP |

---

## Endpointy do weryfikacji w istniejącym backendzie IFG

