# IFGM — plan wykorzystania istniejącego kafelkowego frontendu

**Data:** 2026-05-22  
**Metoda:** Guardian2 — analiza statyczna `mobile-expo/` + Mobile API  
**Założenie:** bez nowego UI, bez zmiany modelu kafelkowego; podłączenie istniejących komponentów do realnego API.

---

## 1. Inwentaryzacja kafli dashboardu

Dashboard (`app/dashboard.tsx`) składa się z **trzech warstw wizualnych**:

| # | Element UI | Typ | Komponent | Trasa docelowa | Trasa istnieje | Źródło danych kafla | Ekran docelowy |
|---|------------|-----|-----------|----------------|----------------|---------------------|----------------|
| A | **Hero** — Sprzedaż netto / Zakup netto / VAT | kafel główny (inline `View`) | `dashboard.tsx` → `styles.hero` | brak (informacyjny) | — | **Real API** (`fetchDashboard`) | — |
| B1 | **Dłużnicy** | `KpiTile` | `@/components/KpiTile` | `/debtors` | tak | **Real API** (KPI z dashboardu) | **Mocki** |
| B2 | **Wierzyciele** | `KpiTile` | `@/components/KpiTile` | `/settlements` | tak | **Real API** (KPI z dashboardu) | **Mocki** |
| B3 | **Płatności do przypisania** | `KpiTile` | `@/components/KpiTile` | `/payments-unassigned` | tak | **Real API** (KPI z dashboardu) | **Mocki** |
| B4 | **KSeF** | `KpiTile` | `@/components/KpiTile` | `/ksef` | tak | **Real API** (KPI z dashboardu) | **Mocki** |
| C | **Ostatnie zakupy KSeF** | lista wierszy (`Pressable`) | `dashboard.tsx` → `styles.purchaseRow` | `/invoice/{id}` | tak | **Real API** (`recent_purchase_invoices`) | **Mocki** |
| D1 | **FV sprzedaż** | quick link (`Pressable`) | `dashboard.tsx` → `styles.quickLink` | `/sales-invoices` | tak | brak (tylko nawigacja) | **Mocki** |
| D2 | **FV zakup** | quick link (`Pressable`) | `dashboard.tsx` → `styles.quickLink` | `/purchase-invoices` | tak | brak (tylko nawigacja) | **Mocki** |

**Nagłówek:** `DashboardHeader` + `PeriodSelector` — bez nawigacji; okres steruje `GET /mobile/dashboard?period=`.

**Brak innych kafli KPI** poza czterema `KpiTile` i hero.

---

## 2. Mapowanie: kafel → ekran → API

### 2.1 Podsumowanie statusów

| Kafel / link | KPI z API | Ekran z API | Uwagi |
|--------------|-----------|-------------|-------|
| Hero (sprzedaż/zakup/VAT) | tak | — | Gotowe |
| Dłużnicy | tak | nie | Backend gotowy |
| Wierzyciele | tak | nie | Backend gotowy; brak `/creditors` |
| Płatności do przypisania | tak | nie | Brak mobile list endpoint |
| KSeF | tak | nie | Sync w IFG: `POST /ksef/sync/purchases` |
| Ostatnie zakupy KSeF | tak | nie (szczegół) | UUID z API → mock `/invoice/[id]` |
| FV sprzedaż / zakup | — | nie | Brak mobile list endpoint |

### 2.2 Szczegóły ekranów docelowych

| Trasa | Plik | Mock | Real API |
|-------|------|------|----------|
| `/debtors` | `app/debtors/index.tsx` | `@/data/mock` → `debtors` | brak wywołania |
| `/debtors/[id]` | `app/debtors/[id].tsx` | `@/data/mock` + fallback `debtors[0]` | brak wywołania |
| `/settlements` | `app/settlements.tsx` | mock (FV + debtors) | brak — **to nie jest ekran wierzycieli** |
| `/creditors` | — | — | **nie istnieje** |
| `/payments-unassigned` | `app/payments-unassigned.tsx` | `unassignedPayments` | brak |
| `/ksef` | `app/ksef.tsx` | `dashboardMock` + demo sync | brak |
| `/sales-invoices` | `app/sales-invoices.tsx` | `salesInvoices` | brak |
| `/purchase-invoices` | `app/purchase-invoices.tsx` | `purchaseInvoices` | brak |
| `/invoice/[id]` | `app/invoice/[id].tsx` | `allInvoices` + fallback | brak |

---

## 3. Dłużnicy — analiza podłączenia

### 3.1 Istniejący UI (zachować bez zmian layoutu)

**Lista** (`/debtors`):
- `ScreenShell` tytuł „Dłużnicy”, subtitle „Należności po kontrahentach”
- Karta kontrahenta: nazwa, kwota, meta „X faktur · po terminie Y”, opcjonalnie podgląd notatki lub „Brak notatek”
- Sortowanie: `overdueDue DESC`, potem `totalDue DESC`

**Szczegóły** (`/debtors/[id]`):
- Summary 3 kolumny: Należność / Po terminie / Faktury
- Opcjonalny blok „Ostatnia notatka”
- Sekcja „Faktury” — numer, termin, kwota, dni po terminie → link `/invoice/{invoiceId}`
- Sekcja „Historia notatek”

### 3.2 Backend Mobile API (gotowy)

```
GET /api/v1/mobile/debtors
GET /api/v1/mobile/debtors/{debtor_id}
```

**Lista — `CounterpartyListItem`:**
```json
{
  "id": "uuid",
  "name": "string",
  "total_due": "decimal",
  "overdue_due": "decimal",
  "invoices_count": 0,
  "overdue_invoices_count": 0,
  "last_invoice_due_date": "date|null"
}
```

**Szczegóły — `CounterpartyDetailResponse` + `invoices[]`:**
```json
{
  "invoice_id": "uuid",
  "number": "string",
  "issue_date": "date",
  "due_date": "date|null",
  "amount_due": "decimal",
  "overdue_days": 0
}
```

Implementacja: `MobileService.get_debtors()` / `get_debtor()` — agregacja z `PaymentService.get_settlement_summary(side="sales")`.

### 3.3 Mapowanie mock → API (bez zmiany JSX)

| Pole UI (mock) | Pole API | Uwaga |
|----------------|----------|-------|
| `d.id` | `item.id` | UUID z backendu (deterministyczny `uuid5` po nazwie) |
| `d.name` | `item.name` | 1:1 |
| `d.totalDue` | `parseAmount(item.total_due)` | string decimal z API |
| `d.overdueDue` | `parseAmount(item.overdue_due)` | 1:1 |
| `d.invoicesCount` | `item.invoices_count` | 1:1 |
| `d.lastNote` | **brak w API** | Zawsze gałąź „Brak notatek” — UI już obsługuje |
| `debtor.notes` | **brak w API** | Pusta lista → istniejący tekst „Brak notatek windykacyjnych.” |
| `inv.invoiceId` | `inv.invoice_id` | 1:1 |
| `inv.number` | `inv.number` | 1:1 |
| `inv.dueDate` | `inv.due_date` (ISO → `YYYY-MM-DD`) | 1:1 |
| `inv.amountDue` | `parseAmount(inv.amount_due)` | 1:1 |
| `inv.overdueDays` | `inv.overdue_days` | 1:1 |

### 3.4 Minimalny zakres podłączenia (Dłużnicy)

**Pliki do zmiany (wyłącznie warstwa danych, bez layoutu):**

1. `src/api/mobile.ts` — dodać typy + `fetchDebtors()`, `fetchDebtor(id)`
2. `app/debtors/index.tsx`:
   - zamienić import mock → `useEffect` + `fetchDebtors()`
   - dodać stany `loading` / `error` / `retry` (wzorzec z `dashboard.tsx`)
   - sortowanie na polach API (`overdue_due`, `total_due`)
   - sekcja notatek: bez zmian JSX — `lastNote` zawsze `null`
3. `app/debtors/[id].tsx`:
   - `fetchDebtor(id)` zamiast `debtors.find`
   - **usunąć fallback `debtors[0]`** — przy 404 pokazać komunikat (ten sam `ScreenShell`, bez nowego designu)
   - mapowanie `invoices[]` jak w tabeli powyżej

**Czego nie ruszać:**
- `KpiTile`, `ScreenShell`, StyleSheet, struktura kart
- Dashboard — KPI dłużników już z API
- Backend Mobile API — endpointy gotowe

**Poza minimalnym zakresem (later, bez zmiany layoutu):**
- Notatki windykacyjne — wymaga nowego endpointu backendu
- Szczegół faktury `/invoice/[id]` — osobny etap

---

## 4. Wierzyciele — analiza podłączenia

### 4.1 Stan obecny

- **Brak trasy `/creditors`** w `app/`
- Kafel „Wierzyciele” (`dashboard.tsx` L135–143) → `router.push('/settlements')`
- `/settlements` to ekran **„Rozrachunki”** z tabami Należności/Zobowiązania na poziomie **pojedynczych faktur mock**, nie agregatu wierzycieli
- Etykieta w UI: „Wierzyciele — widok listy” (demo) — **placeholder**, nie docelowy ekran IFGM

### 4.2 Backend Mobile API (gotowy)

```
GET /api/v1/mobile/creditors
GET /api/v1/mobile/creditors/{creditor_id}
```

Identyczny kształt odpowiedzi jak dłużnicy (`CounterpartyListItem` / `CounterpartyDetailResponse`), źródło: `get_settlement_summary(side="purchase")`.

### 4.3 Strategia reuse UI (bez nowego designu)

**Nie projektować nowego ekranu** — sklonować istniejący wzorzec dłużników:

| Nowy plik | Bazowany na | Różnice tekstowe |
|-----------|-------------|------------------|
| `app/creditors/index.tsx` | `app/debtors/index.tsx` | tytuł „Wierzyciele”, subtitle „Zobowiązania po kontrahentach”, `fetchCreditors()` |
| `app/creditors/[id].tsx` | `app/debtors/[id].tsx` | subtitle „Szczegóły wierzyciela”, etykieta summary „Zobowiązanie” zamiast „Należność”, `fetchCreditor(id)` |

To **nie jest nowy layout** — ten sam `ScreenShell`, te same `styles`, ta sama struktura kart.

**Jedna zmiana nawigacji na dashboardzie:**
```tsx
// dashboard.tsx — KpiTile Wierzyciele
onPress={() => router.push('/creditors')}  // było: '/settlements'
```

### 4.4 Minimalny zakres podłączenia (Wierzyciele)

1. `src/api/mobile.ts` — `fetchCreditors()`, `fetchCreditor(id)` (mirror debtors)
2. `app/creditors/index.tsx` — kopia logiki listy dłużników + API creditors
3. `app/creditors/[id].tsx` — kopia szczegółów + API
4. `app/dashboard.tsx` — **tylko** zmiana `onPress` kafelka Wierzyciele → `/creditors`

**Czego nie ruszać:**
- `/settlements` — zostaje jako osobny ekran demo (brak linku z dashboardu po zmianie routingu)
- Model kafelkowy `KpiTile` — bez zmian propsów
- Backend — endpointy gotowe

**Mapowanie pól:** identyczne jak dłużnicy (sekcja 3.3).

---

## 5. Ocena kafelkowego frontendu

### 5.1 Co zachować

| Element | Powód |
|---------|-------|
| `KpiTile` | Uniwersalny kafel KPI — już zasilany danymi API na dashboardzie |
| Hero dashboardu (sprzedaż/zakup/VAT) | Działa na API, layout zgodny ze spec |
| `ScreenShell` + istniejące StyleSheet ekranów dłużników | Gotowy wzorzec listy/szczegółów kontrahenta |
| `DashboardHeader` + `PeriodSelector` | Steruje okresem bez zmian |
| Auth guard (`_layout.tsx`) | Działa poprawnie |
| `formatPln` z `@/data/mock` | Helper formatowania — można zostawić (nie jest „danymi demo”) |

### 5.2 Co tylko podłączyć (kolejność)

| Priorytet | Obszar | Effort | Backend |
|-----------|--------|--------|---------|
| **P1** | Dłużnicy lista + szczegóły | niski | gotowy |
| **P1** | Wierzyciele (klon dłużników + routing) | niski | gotowy |
| P2 | Szczegół faktury `/invoice/[id]` | średni | brak mobile endpoint (reuse `/invoices/{id}`?) |
| P2 | Ostatnie zakupy → szczegół faktury | średni | zależy od P2 |
| P3 | Płatności do przypisania | średni | `/payments/transactions` + allocate |
| P3 | KSeF sync | niski | `POST /ksef/sync/purchases` |
| P4 | FV sprzedaż / zakup | średni | brak mobile list |
| P5 | Notatki windykacyjne | wysoki | brak w Mobile API |

### 5.3 Czego nie ruszać

- Układ `kpiGrid` (2×2 kafle)
- Komponent `KpiTile` — API propsów
- Quick linki FV — do czasu gotowości endpointów list faktur
- `/settlements` — nie jest docelowym ekranem wierzycieli; nie rozbudowywać
- Backend Mobile API dla debtors/creditors — gotowy, nie wymaga zmian na etapie P1

### 5.4 Blokery produkcyjnego użycia (poza P1)

1. **Rozjazd dashboard → szczegół faktury** — realne UUID, mock na `/invoice/[id]`
2. **Notatki windykacyjne** — UI jest, API nie ma (dłużnicy będą pokazywać „Brak notatek”)
3. **Płatności / KSeF / listy FV** — nadal mocki po podłączeniu dłużników/wierzycieli
4. **Infrastruktura** — Cloudflare Access; mobile wymaga LAN/Tailscale (`mobile-expo/README.md`)

---

## 6. Plan implementacji P1 (Dłużnicy + Wierzyciele)

### Krok 1 — Klient API (`src/api/mobile.ts`)

```typescript
// Typy (mirror app/schemas/mobile.py)
CounterpartyListItem, CounterpartiesListResponse
CounterpartyDetailResponse, SettlementInvoiceItem

fetchDebtors()      → GET /mobile/debtors
fetchDebtor(id)     → GET /mobile/debtors/{id}
fetchCreditors()    → GET /mobile/creditors
fetchCreditor(id)   → GET /mobile/creditors/{id}
```

Wspólny helper: `parseAmount()` — już istnieje.

### Krok 2 — Dłużnicy

- `debtors/index.tsx`: fetch + loading/error/retry; mapowanie pól; sort; notatki → zawsze „Brak notatek”
- `debtors/[id].tsx`: fetch po `id`; mapowanie faktur; 404 bez fallbacku na mock[0]

### Krok 3 — Wierzyciele

- Utworzyć `creditors/index.tsx` i `creditors/[id].tsx` jako kopie krok 2 z innymi tytułami i endpointami
- `dashboard.tsx`: `onPress` Wierzyciele → `/creditors`

### Krok 4 — Weryfikacja (manual)

1. KPI Wierzyciele/Dłużnicy na dashboardzie = sumy z list API
2. Tap kafel → lista kontrahentów z IFG (nie mock ORLEN/ABC demo)
3. Tap kontrahent → faktury z realnymi numerami
4. Tap faktura → nadal mock (znany bloker P2)

**Szacowany diff:** ~4 pliki nowe/zmienione + rozszerzenie `mobile.ts`; **zero zmian CSS/layoutu**.

---

## 7. Diagram przepływu (stan docelowy P1)

```text
Dashboard (API)
    │
    ├─ KpiTile Dłużnicy ──→ /debtors (API) ──→ /debtors/[id] (API) ──→ /invoice/[id] (mock, P2)
    │
    └─ KpiTile Wierzyciele ─→ /creditors (API) ─→ /creditors/[id] (API) ─→ /invoice/[id] (mock, P2)
```

---

## 8. Pliki referencyjne

```
mobile-expo/app/dashboard.tsx           — kafle KpiTile + quick linki
mobile-expo/src/components/KpiTile.tsx  — komponent kafla
mobile-expo/app/debtors/index.tsx       — wzorzec listy (mock → podłączyć)
mobile-expo/app/debtors/[id].tsx        — wzorzec szczegółów (mock → podłączyć)
mobile-expo/src/api/mobile.ts           — rozszerzyć o debtors/creditors
app/api/routers/mobile.py               — endpointy gotowe
app/schemas/mobile.py                   — kontrakt API
docs/IFGM_SPEC_V1.md                    — spec wierzyciele ≈ dłużnicy
```

---

*Guardian2 — plan reuse kafelkowego frontendu IFGM. Bez implementacji, bez zmian layoutu, bez uruchamiania Expo.*
