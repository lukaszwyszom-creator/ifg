# IFGM BACKEND GAP ANALYSIS V1

Analiza zgodności obecnego backendu IFG z wymaganiami IFGM (`docs/IFGM_USER_FLOW_V1.md`, `docs/IFGM_API_REQUIREMENTS_V1.md`).

Data audytu: na podstawie stanu repozytorium w momencie sporządzenia dokumentu.

Prefiks API produkcyjnego IFG: **`/api/v1`** (domyślnie `settings.api_v1_prefix`).

---

## Podsumowanie

| Obszar | Gotowe | Wymaga rozszerzenia | Brak |
|--------|--------|---------------------|------|
| Uwierzytelnianie | ✅ | 🟡 | — |
| Dashboard | — | 🟡 | ❌ (brak agregatu) |
| Powiadomienia | — | — | ❌ |
| Dłużnicy | — | 🟡 | ❌ (notatki, kontakt, agregacja) |
| Wierzyciele | — | 🟡 | ❌ (notatki, kontakt, agregacja) |
| Płatności do przypisania | 🟡 | 🟡 | — |
| Faktury sprzedaży | ✅ | 🟡 | — |
| Faktury zakupu | ✅ | 🟡 | — |
| KSeF | ✅ | 🟡 | — |
| Rozrachunki (wsparcie) | 🟡 | 🟡 | — |

Legenda oceny sekcji: ✅ Gotowe · 🟡 Wymaga rozszerzenia · ❌ Brak

---

## 1. Dashboard

### Wymaganie IFGM

Jeden agregat ekranu startowego (`GET /api/mobile/dashboard?period=YYYY-MM`):

* sprzedaż netto, zakup netto, VAT do zapłaty / odliczenia
* liczba dłużników, suma należności, kwota po terminie
* liczba wierzycieli, suma zobowiązań, kwota po terminie
* liczba i suma płatności do przypisania
* liczba nowych dokumentów KSeF, data ostatniej synchronizacji
* liczba aktywnych powiadomień
* skrót ostatnich zakupów z KSeF

### Istniejące endpointy (fragmenty)

| Endpoint | Plik routera | Opis |
|----------|--------------|------|
| `GET /api/v1/invoices/?direction=sale&month=YYYY-MM` | `app/api/routers/invoices.py` | lista faktur sprzedaży za miesiąc — dane do sum netto po stronie klienta |
| `GET /api/v1/invoices/?direction=purchase&month=YYYY-MM` | `app/api/routers/invoices.py` | lista faktur zakupowych za miesiąc |
| `GET /api/v1/invoices/?view=open` | `app/api/routers/invoices.py` | otwarte faktury + `summary` (`OpenInvoicesSummary`: receivables, payables, overdue buckets) |
| `GET /api/v1/payments/settlements?side=all&month=YYYY-MM` | `app/api/routers/payments.py` | rozrachunki per faktura (debtors/creditors) |
| `GET /api/v1/payments/transactions?match_status=unmatched` | `app/api/routers/payments.py` | transakcje niedopasowane |
| `GET /api/v1/ksef/status` | `app/api/routers/ksef_session.py` | status połączenia KSeF (`ui_status`, `details`) |
| `GET /api/v1/ksef/sync/status` | `app/api/routers/ksef_session.py` | ostatnia synchronizacja zakupów, błędy |

### Ocena

🟡 **Wymaga rozszerzenia**

Brak jednego endpointu agregującego. Desktop liczy KPI w frontendzie (`DashboardSummary`, `VATSummary`, store `invoicePool`). IFGM wymaga jednego requestu na ekran Start.

### Brakujące pola / zachowania

* `sales_net`, `purchase_net`, `vat_balance`, `vat_label` — brak w jednej odpowiedzi API
* `debtors_count`, `creditors_count` — rozrachunki zwracają **listę faktur**, nie liczbę kontrahentów
* `debtors_overdue_due`, `creditors_overdue_due` — częściowo w `OpenInvoicesSummary.overdue_*`, ale bez podziału sale/purchase i bez liczby kontrahentów
* `notifications_active_count` — brak źródła danych
* `ksef_new_invoices_count` — brak dedykowanego pola (możliwy derivat ze `state_json` sync status)
* `recent_purchase_invoices` — wymaga osobnego zapytania listy zakupów

### Szacowany zakres zmian

**Średni** — nowy handler agregujący istniejące serwisy (`InvoiceService`, `PaymentService`, `KSeFSyncService`) bez duplikacji logiki biznesowej.

---

## 2. Powiadomienia

### Wymaganie IFGM

Centrum spraw wymagających działania (`GET /api/mobile/notifications`):

* typy: `payment_unassigned`, `ksef_new_invoice`, `debtor_overdue`, `creditor_overdue`, `ksef_sync_error`
* pola: `id`, `type`, `title`, `subtitle`, `count`, `created_at`, `target_type`, `target_id`
* zdarzenia zbiorcze (`count > 1`) → nawigacja najpierw do listy

### Istniejące endpointy

Brak dedykowanego modułu powiadomień, kolejki ani tabeli notification.

Powiązane dane źródłowe (read-only, rozproszone):

| Źródło | Endpoint | Plik |
|--------|----------|------|
| Transakcje niedopasowane | `GET /api/v1/payments/transactions?match_status=unmatched` | `payments.py` |
| Sync KSeF błąd | `GET /api/v1/ksef/sync/status` (`last_error`, `status`) | `ksef_session.py` |
| Otwarte / przeterminowane | `GET /api/v1/invoices?view=open` | `invoices.py` |

### Ocena

❌ **Brak**

### Brakujące pola

* cały model `NotificationItem` i logika agregacji zdarzeń
* `target_type` / `target_id` dla nawigacji IFGM
* licznik `active_count` na Dashboardzie

### Szacowany zakres zmian

**Średni** — read-model liczony on-demand z istniejących tabel (bez push), ewentualnie cache krótkotrwały.

---

## 3. Dłużnicy

### Wymaganie IFGM

* lista kontrahentów z agregacją zadłużenia
* szczegóły: telefon, notatki, historia kontaktów, lista faktur
* `POST .../notes`

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `GET /api/v1/payments/settlements?side=sales` | `app/api/routers/payments.py` | faktury sprzedaży z `remaining_amount > 0` (`SettlementItemResponse`) |
| `GET /api/v1/invoices/?view=open&direction=sale` | `app/api/routers/invoices.py` | otwarte FS z `overdue_days`, `remaining_amount` |
| `GET /api/v1/contractors/by-nip/{nip}` | `app/api/routers/contractors.py` | dane kontrahenta z REGON (bez telefonu w schemacie) |

Serwis: `PaymentService.get_settlement_summary()` — `app/services/payment_service.py` (poziom **faktury**, nie kontrahent).

### Ocena

🟡 **Wymaga rozszerzenia** (+ ❌ dla notatek/kontaktu)

### Brakujące pola / funkcje

* agregacja **per kontrahent**: `total_due`, `overdue_due`, `invoices_count`, `overdue_invoices_count`
* `last_note`, `last_contact_at` — brak modelu windykacyjnego w backendzie (grep: brak `contact`, `windyk`, `collection_note`)
* `phone` — brak w `ContractorResponse` (`app/schemas/contractor.py`)
* `GET /debtors/{id}` — brak endpointu szczegółów kontrahenta z fakturami
* `POST /debtors/{id}/notes` — brak persystencji notatek

### Szacowany zakres zmian

**Wysoki** dla pełnego USER FLOW (notatki + historia kontaktu wymagają nowych tabel). **Średni** jeśli MVP ograniczy się do agregacji z rozrachunków bez notatek.

---

## 4. Wierzyciele

### Wymaganie IFGM

Analogicznie do Dłużników, perspektywa zobowiązań wobec dostawców.

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `GET /api/v1/payments/settlements?side=purchase` | `payments.py` | faktury zakupowe z saldem |
| `GET /api/v1/invoices/?view=open&direction=purchase` | `invoices.py` | otwarte FZ |

### Ocena

🟡 **Wymaga rozszerzenia** (+ ❌ notatki/kontakt — jak Dłużnicy)

### Brakujące pola

Jak w §3, z `direction=purchase` / `side=purchase`.

### Szacowany zakres zmian

**Wysoki** (z notatkami) / **Średni** (agregacja bez notatek).

---

## 5. Płatności do przypisania

### Wymaganie IFGM

* lista transakcji do przypisania
* szczegóły z `confidence`, `proposed_matches`
* `POST .../assign` z wieloma fakturami (`invoice_ids`, `allocations`)

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `GET /api/v1/payments/transactions?match_status=unmatched` | `payments.py` | lista; pola: `amount`, `counterparty_name`, `title`, `match_status`, `remaining_amount`, `transaction_date` |
| `POST /api/v1/payments/transactions/{id}/match` | `payments.py` | ponowny auto-match (wynik tekstowy, bez listy kandydatów) |
| `POST /api/v1/payments/transactions/{id}/allocate` | `payments.py` | ręczna alokacja **jednej** faktury (`ManualAllocateRequest`: `invoice_id`, `amount`) |
| `DELETE /api/v1/payments/allocations/{id}` | `payments.py` | cofnięcie alokacji |

Serwis matcher: `app/services/payment_matcher.py` — `find_candidates()` istnieje, **nie jest wystawione przez API**.

### Ocena

🟡 **Wymaga rozszerzenia**

Lista i podstawowe przypisanie istnieją; brakuje warstwy „propozycja IFG” dla mobile.

### Brakujące pola / funkcje

* `GET /payments/transactions/{id}` — brak endpointu szczegółów
* `confidence` — brak w `BankTransactionResponse` (jest tylko `match_status`: `unmatched`, `manual_review`, …)
* `proposed_matches` — logika w `PaymentMatcher.find_candidates()` nie zwracana w API
* `POST assign` z wieloma fakturami — `allocate_manual` obsługuje pojedynczą fakturę na wywołanie
* `booked_at` — w API jest `transaction_date` / `imported_at` (mapowanie nazw w mobile)

### Szacowany zakres zmian

**Średni** — rozszerzenie routera płatności + ekspozycja kandydatów matchera; ewentualnie batch allocate.

---

## 6. Faktury sprzedaży

### Wymaganie IFGM

Lista + podgląd read-only: numer, kontrahent, kwota, status płatności, termin.

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `GET /api/v1/invoices/?direction=sale&month=YYYY-MM` | `invoices.py` | lista z paginacją |
| `GET /api/v1/invoices/{id}` | `invoices.py` | szczegóły + `payment_status`, `overdue_days`, `remaining_amount` |
| `GET /api/v1/invoices/{id}/preview` | `invoices.py` | HTML podglądu |
| `GET /api/v1/invoices/{id}/pdf` | `invoices.py` | PDF |

Schema: `InvoiceResponse` — `app/schemas/invoice.py`.

### Ocena

✅ **Gotowe** (z mapowaniem pól w warstwie mobile)

### Brakujące pola

* `contractor_name` — w odpowiedzi jako `buyer_snapshot.name` (wymaga mapowania, nie osobnego pola)
* brak prefiksu `/api/mobile/` — kosmetyka ścieżki

### Szacowany zakres zmian

**Niski** — reuse istniejących endpointów; ewentualnie cienki alias mobile lub adapter odpowiedzi.

---

## 7. Faktury zakupu

### Wymaganie IFGM

Lista + podgląd: numer, dostawca, kwota, status; filtr źródła KSeF.

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `GET /api/v1/invoices/?direction=purchase&month=YYYY-MM` | `invoices.py` | lista FZ |
| `GET /api/v1/invoices/{id}` | `invoices.py` | szczegóły (`seller_snapshot` = dostawca) |
| `GET /api/v1/invoices/{id}/preview` | `invoices.py` | podgląd |
| `GET /api/v1/invoices/{id}/pdf` | `invoices.py` | PDF |

### Ocena

✅ **Gotowe**

### Brakujące pola

* `supplier_name` — mapowanie z `seller_snapshot.name`
* `source=ksef` — brak filtra query; identyfikacja po `ksef_reference_number IS NOT NULL` wymaga rozszerzenia listy lub filtrowania po stronie klienta

### Szacowany zakres zmian

**Niski** — opcjonalny filtr `source` / `has_ksef_reference` w `list_invoices`.

---

## 8. KSeF

### Wymaganie IFGM

Status połączenia, ostatnia synchronizacja, liczba nowych faktur, ręczna synchronizacja.

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `GET /api/v1/ksef/status?nip=` | `ksef_session.py` | `KSeFConnectionStatusResponse` (`ui_status`, `details.last_error`) |
| `GET /api/v1/ksef/sync/status` | `ksef_session.py` | `last_success_at`, `last_attempt_at`, `last_error`, `status`, `state_json` |
| `POST /api/v1/ksef/sync/purchases` | `ksef_session.py` | synchroniczne odświeżenie zakupów (`counts.saved`, …) |
| `POST /api/v1/ksef-sessions/sync-purchase` | `ksef_session.py` | wariant asynchroniczny (job + worker) |

IFGM nie łączy się z KSeF bezpośrednio — zgodne z architekturą.

### Ocena

✅ **Gotowe** (z mapowaniem pól)

### Brakujące pola

* `new_invoices_count` — brak jawnego pola; możliwe z `SyncPurchaseResponse.saved` po sync lub ze `state_json`
* nazwy pól IFGM (`last_sync_at`) vs IFG (`last_success_at`)

### Szacowany zakres zmian

**Niski** — adapter odpowiedzi mobile / dokumentacja mapowania.

---

## 9. Uwierzytelnianie

### Wymaganie IFGM

Logowanie użytkownikiem IFG, JWT, użycie z Expo, obsługa wygaśnięcia tokena.

### Istniejące endpointy

| Endpoint | Plik | Opis |
|----------|------|------|
| `POST /api/v1/auth/login` | `app/api/routers/auth.py` | `LoginRequest` → `TokenResponse` (`access_token`, `expires_in`, `username`, `role`) |

Implementacja: `app/services/auth_service.py`, `app/core/security.py` (JWT HS256, `create_access_token`, `decode_access_token`).

Ochrona tras: `get_current_user` w `app/api/deps.py` — nagłówek `Authorization: Bearer`.

### Ocena

✅ **Gotowe** dla MVP logowania

🟡 **Wymaga rozszerzenia** dla wygody mobile

### Brakujące elementy

* **brak `POST /auth/refresh`** — po wygaśnięciu (`ACCESS_TOKEN_EXPIRE_MINUTES`, domyślnie 30 min) wymagane ponowne logowanie
* brak endpointu `/me` — opcjonalnie dla profilu
* Expo: standardowy fetch + SecureStore — **kompatybilne** z obecnym Bearer JWT

### Szacowany zakres zmian

**Niski** (MVP: re-login) · **Średni** (refresh token lub dłuższa sesja mobile)

---

## 10. Mapa zgodności

| Wymaganie IFGM | Istniejący endpoint IFG | Brakujące pola / luki | Wymaga zmian |
|----------------|-------------------------|------------------------|--------------|
| Dashboard agregat | brak | cały payload dashboard | **TAK** |
| Sprzedaż / zakup netto (okres) | `GET /api/v1/invoices/?direction=&month=` | agregacja po stronie klienta; brak netto w summary | **TAK** (agregat) |
| VAT okresu | brak dedykowanego | sumy VAT | **TAK** (agregat) |
| Powiadomienia | brak | cały moduł | **TAK** |
| Dłużnicy — lista | `GET /api/v1/payments/settlements?side=sales` | poziom faktury, brak agregacji kontrahenta, notatki | **TAK** |
| Dłużnicy — szczegóły | częściowo `GET /api/v1/invoices/{id}` | brak widoku kontrahenta, phone, notes | **TAK** |
| Wierzyciele — lista | `GET /api/v1/payments/settlements?side=purchase` | j.w. | **TAK** |
| Płatności — lista | `GET /api/v1/payments/transactions?match_status=unmatched` | `confidence`, `proposed_matches` | **TAK** |
| Płatności — szczegóły | brak `GET .../transactions/{id}` | cały endpoint | **TAK** |
| Płatności — assign | `POST .../transactions/{id}/allocate` | tylko 1 faktura / wywołanie | **TAK** |
| Faktury sprzedaży | `GET /api/v1/invoices/?direction=sale` | mapowanie nazw pól | **NIE** / minimalnie |
| Faktury sprzedaży — podgląd | `GET /api/v1/invoices/{id}/preview` | — | **NIE** |
| Faktury zakupu | `GET /api/v1/invoices/?direction=purchase` | filtr `source=ksef` | **NIE** / opcjonalnie |
| KSeF status | `GET /api/v1/ksef/status` + `/ksef/sync/status` | `new_invoices_count` | **NIE** / minimalnie |
| KSeF sync | `POST /api/v1/ksef/sync/purchases` | — | **NIE** |
| Logowanie | `POST /api/v1/auth/login` | refresh token | **NIE** (MVP) / opcjonalnie |

---

## 11. Endpointy do dopisania

Poniżej wyłącznie luki, których **nie da się** sensownie zrealizować samym rozszerzeniem parametrów istniejących tras.

### 1. `GET /api/v1/mobile/dashboard` (lub rozszerzenie nowego routera mobile)

* **Cel:** jeden agregat KPI Dashboardu IFGM.
* **Uzasadnienie:** brak odpowiednika; obecnie 4–6 requestów i logika w frontendzie desktop.

### 2. `GET /api/v1/mobile/notifications`

* **Cel:** centrum spraw wymagających działania.
* **Uzasadnienie:** brak jakiegokolwiek endpointu; dane źródłowe istnieją, lecz nie są zunifikowane.

### 3. `GET /api/v1/mobile/debtors` · `GET /api/v1/mobile/debtors/{id}`

* **Cel:** lista i szczegóły dłużników per kontrahent.
* **Uzasadnienie:** `/payments/settlements` zwraca faktury, nie kontrahentów; brak grupowania i overdue per kontrahent.

### 4. `GET /api/v1/mobile/creditors` · `GET /api/v1/mobile/creditors/{id}`

* **Cel:** j.w. dla wierzycieli.
* **Uzasadnienie:** analogicznie do dłużników.

### 5. `POST /api/v1/mobile/debtors/{id}/notes` · `POST .../creditors/{id}/notes`

* **Cel:** notatki windykacyjne z USER FLOW.
* **Uzasadnienie:** brak modelu i endpointu w backendzie (nowa persystencja).

### 6. `GET /api/v1/payments/transactions/{id}` (rozszerzenie istniejącego routera)

* **Cel:** szczegóły transakcji + proponowane dopasowania (`proposed_matches`, `confidence`).
* **Uzasadnienie:** matcher istnieje w serwisie, nie jest eksponowany; mobile wymaga ekranu decyzji.

### Opcjonalne rozszerzenia (bez nowych routerów)

* `POST /api/v1/payments/transactions/{id}/allocate` — obsługa wielu alokacji w jednym body (rozszerzenie schematu).
* `GET /api/v1/invoices/` — query `has_ksef_reference=true` dla filtra zakupów KSeF.
* `POST /api/v1/auth/refresh` — wygoda sesji mobile (poza strict MVP).

---

## 12. Rekomendacja

### **B. IFGM wymaga budowy cienkiej warstwy API mobilnego (`/api/v1/mobile/*`)**

**Uzasadnienie:**

1. **Dashboard i powiadomienia** — IFGM zakłada model produktowy (stan firmy vs sprawy do działania), którego obecne REST API nie odzwierciedla. Desktop rozwiązuje to wieloma wywołaniami i logiką w React — na mobile jest to nieakceptowalne (latencja, offline UX, prostota).

2. **Dłużnicy / wierzyciele** — backend ma rozrachunki na poziomie **faktury** (`SettlementItemResponse`), podczas gdy IFGM USER FLOW wymaga poziomu **kontrahenta** oraz notatek — to nowy read-model (i nowe tabele na notatki), nie tylko alias URL.

3. **Płatności** — rdzeń istnieje (`transactions`, `allocate`), ale mobile wymaga **ekspozycji propozycji matchera**; bez tego nie spełnia założenia „akceptacja propozycji IFG”.

4. **Co jest gotowe** — auth JWT, faktury (lista/podgląd/PDF), KSeF status/sync można **reuse'ować bez duplikacji bazy** — warstwa mobile powinna delegować do istniejących serwisów (`InvoiceService`, `PaymentService`, `KSeFSyncService`), nie tworzyć równoległej logiki.

5. **Nie jest to osobny backend** — jedna baza PostgreSQL, jedno źródło prawdy; chodzi o **BFF (Backend for Frontend)** w monolicie IFG, nie o nowy system.

**Opcja A** (wyłącznie istniejące API) byłaby możliwa tylko przy okrojonym MVP (bez powiadomień, bez notatek, bez agregatu dashboard, wielokrotne requesty) — **niezgodnym z `IFGM_USER_FLOW_V1` i `IFGM_API_REQUIREMENTS_V1`**.

---

## Lista plików backendu przeanalizowanych podczas audytu

* `app/main.py`
* `app/api/deps.py`
* `app/api/routers/auth.py`
* `app/api/routers/invoices.py`
* `app/api/routers/payments.py`
* `app/api/routers/contractors.py`
* `app/api/routers/ksef_session.py`
* `app/schemas/auth.py`
* `app/schemas/invoice.py`
* `app/schemas/payment.py`
* `app/schemas/contractor.py`
* `app/schemas/ksef_session.py`
* `app/services/auth_service.py`
* `app/services/invoice_service.py`
* `app/services/payment_service.py`
* `app/services/payment_matcher.py`
* `app/core/security.py`
* `app/core/config.py`
