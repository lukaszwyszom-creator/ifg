# IFGM Release Candidate Audit — DS723+

**Data:** 2026-05-22  
**Zakres:** `mobile-expo/` + analiza endpointów API używanych przez mobile  
**Kontekst:** P1–P3 ukończone, G2 audit ukończony, jedyny świadomy mock biznesowy: `/ksef`  
**Pytanie:** Czy IFGM jest gotowe do wdrożenia pilotażowego?

---

## Ocena gotowości produkcyjnej

**78%** — gotowe do **wdrożenia pilotażowego** z ograniczeniami opisanymi poniżej.

| Obszar | Ocena | Uwagi |
|--------|-------|-------|
| Przepływy E2E (P1–P3) | 92% | Wszystkie główne ścieżki działają na realnym API |
| Integralność kwot | 90% | Poprawione w G2 (`remaining_amount` na listach FV) |
| Obsługa błędów / 401 | 95% | Spójny wzorzec na wszystkich ekranach |
| Konfiguracja produkcyjna | 60% | Wymaga `EXPO_PUBLIC_API_BASE_URL` przy buildzie |
| KSeF w mobile | 0% | Ekran demo — poza zakresem pilotażu operacyjnego |
| Skalowalność (paginacja) | 65% | Limity 100 FV / 200 płatności bez UI paginacji |

---

## 1. Weryfikacja przepływów E2E

### 1.1 Dashboard → FV sprzedaży → Szczegół FV

| Krok | Trasa / API | Status |
|------|-------------|--------|
| Dashboard quick link | `/sales-invoices?month=YYYY-MM` | OK |
| Lista | `GET /api/v1/invoices/?direction=sale&month=…` | OK |
| Szczegół | `GET /api/v1/invoices/{id}` | OK |
| Stany UI | loading / error / retry / empty / 401 | OK |

### 1.2 Dashboard → FV zakupu → Szczegół FV

| Krok | Trasa / API | Status |
|------|-------------|--------|
| Dashboard quick link | `/purchase-invoices?month=YYYY-MM` | OK |
| Lista | `GET /api/v1/invoices/?direction=purchase&month=…` | OK |
| Szczegół | `/invoice/{id}` | OK |

### 1.3 Dashboard → Dłużnicy → Szczegół → Faktura

| Krok | Trasa / API | Status |
|------|-------------|--------|
| KPI Dłużnicy | `/debtors` | OK |
| Lista | `GET /api/v1/mobile/debtors` | OK |
| Szczegół | `/debtors/{id}` → `GET /api/v1/mobile/debtors/{id}` | OK |
| Faktura | `/invoice/{invoice_id}` | OK |

### 1.4 Dashboard → Wierzyciele → Szczegół → Faktura

| Krok | Trasa / API | Status |
|------|-------------|--------|
| KPI Wierzyciele | `/creditors` | OK |
| Lista | `GET /api/v1/mobile/creditors` | OK |
| Szczegół | `/creditors/{id}` | OK |
| Faktura | `/invoice/{invoice_id}` | OK |

### 1.5 Dashboard → Płatności → Przypisanie

| Krok | Trasa / API | Status |
|------|-------------|--------|
| KPI Płatności | `/payments-unassigned` | OK |
| Lista | `GET /api/v1/payments/transactions?match_status=unmatched` (+ partial, manual_review) | OK |
| Przypisanie | `POST /api/v1/payments/transactions/{id}/allocate` | OK |
| Wyszukiwanie FV | `GET /api/v1/invoices/?number_filter=…` | OK |

### 1.6 Dashboard → Płatności → Zmiana przypisania

| Krok | Trasa / API | Status |
|------|-------------|--------|
| Wybór starej FV | `GET /api/v1/payments/invoice/{id}/history` | OK |
| Cofnięcie | `DELETE /api/v1/payments/allocations/{id}` | OK |
| Nowe przypisanie | `POST …/allocate` | OK (patrz P1: brak transakcji atomowej) |

### 1.7 Rozrachunki → Faktura

| Krok | Trasa / API | Status |
|------|-------------|--------|
| Ekran | `/settlements` (brak linku z dashboardu) | **Częściowo** — ekran działa, brak wejścia z UI głównego |
| Dane | `GET /api/v1/payments/settlements?side=all` | OK |
| Faktura | `/invoice/{invoice_id}` | OK |
| Agregat | `/debtors` lub `/creditors` | OK |

---

## 2. Endpointy backendowe wykorzystywane przez mobile

| Endpoint | Ekran(y) mobile | Testy backend |
|----------|-----------------|---------------|
| `POST /api/v1/auth/login` | login | (poza zakresem tego audytu) |
| `GET /api/v1/mobile/dashboard` | dashboard | `test_mobile_api.py` |
| `GET /api/v1/mobile/debtors` | dłużnicy | `test_mobile_api.py` |
| `GET /api/v1/mobile/debtors/{id}` | szczegół dłużnika | `test_mobile_api.py` |
| `GET /api/v1/mobile/creditors` | wierzyciele | `test_mobile_api.py` |
| `GET /api/v1/mobile/creditors/{id}` | szczegół wierzyciela | `test_mobile_api.py` |
| `GET /api/v1/invoices/` | listy FV, wyszukiwanie płatności | `test_invoice_api.py` |
| `GET /api/v1/invoices/{id}` | szczegół FV | `test_invoice_api.py` |
| `GET /api/v1/payments/transactions` | płatności | `test_payment_service.py` |
| `POST /api/v1/payments/transactions/{id}/allocate` | przypisanie | `test_payment_service.py` |
| `DELETE /api/v1/payments/allocations/{id}` | zmiana przypisania | `test_payment_service.py` |
| `GET /api/v1/payments/invoice/{id}/history` | zmiana przypisania | `test_payment_service.py` |
| `GET /api/v1/payments/settlements` | rozrachunki | `test_payments_api.py` |

**Wynik testów backendowych (mobile-related):** 67 passed  
**Wynik testów frontendowych:** `npm run lint` OK, `npx tsc --noEmit` OK

---

## 3. Klasyfikacja znalezisk

### P0 — blokuje wdrożenie

| ID | Opis | Typ | Działanie |
|----|------|-----|-----------|
| P0-OPS-1 | **Build produkcyjny bez `EXPO_PUBLIC_API_BASE_URL`** — domyślny `app.json` wskazuje `http://127.0.0.1:8000`, na urządzeniu fizycznym aplikacja nie połączy się z DS723 | Konfiguracja wdrożenia | **Warunek wdrożenia:** build z `EXPO_PUBLIC_API_BASE_URL=https://ifg.ikonastudio.pl` (lub LAN/Tailscale) |
| P0-OPS-2 | **Cloudflare Access na publicznym URL** — klient obsługuje błąd, ale aplikacja nie zadziała bez bezpośredniego dostępu LAN/VPN | Infrastruktura | Użyć adresu omijającego CF Access (jak w `client.ts`) |

**Brak P0 w logice aplikacji** — nie wykryto błędów powodujących crash, utratę danych bez możliwości odzyskania ani całkowicie zepsutych przepływów E2E w zakresie P1–P3.

### P1 — poprawić przed szerszym użyciem

| ID | Opis | Ryzyko |
|----|------|--------|
| P1-1 | **`payment_status: partially_paid`** z backendu nie jest mapowany w `normalizePaymentStatus()` — filtr „Częściowo” na listach FV nie działa; częściowo opłacone mogą trafić do „Nieopłacone” | Niespójne statusy płatności |
| P1-2 | **Brak linku dashboard → `/settlements`** — ekran rozrachunków niedostępny z głównej nawigacji | UX / odkrywalność |
| P1-3 | **Sesja JWT tylko w pamięci** — po restarcie aplikacji wymagane ponowne logowanie (`AuthContext` nie używa SecureStore) | UX pilotażu |
| P1-4 | **Zmiana przypisania (reverse + allocate)** — dwa osobne requesty; błąd po reverse wymaga ręcznego ponownego przypisania | Integralność danych (odwracalna) |
| P1-5 | **Paginacja list FV (limit 100) i płatności (limit 200)** — brak infinite scroll; przy większej bazie dane niewidoczne | Kompletność danych |
| P1-6 | **Ekran `/ksef` — mock demo** — przycisk „Pobierz faktury” symuluje sync; użytkownik może pomylić z realną funkcją | UX / oczekiwania |
| P1-7 | **Modal przypisania płatności** pokazuje `total_gross` faktury zamiast `remaining_amount` | Myjące kwoty przy wyborze FV |
| P1-8 | **Brak dedykowanych testów API** dla `GET /payments/transactions` i `POST …/allocate` na poziomie routera (są testy serwisu) | Pokrycie testami |

### P2 — backlog

| ID | Opis |
|----|------|
| P2-1 | `formatPln` importowany z `@/data/mock` — mylące źródło, działa poprawnie |
| P2-2 | Sekcja „Historia notatek” w detalu dłużnika/wierzyciela — statyczny placeholder |
| P2-3 | Duplikacja `contractorFromInvoice` vs helpery w `mobile.ts` |
| P2-4 | `canReassign` obejmuje status `matched`, który nie występuje na liście |
| P2-5 | Brak testów E2E mobile (Detox / Maestro) |
| P2-6 | `dueLabel` w `@/data/mock` ma hardcoded datę — nieużywany przez ekrany API |

---

## 4. Analiza ryzyk produkcyjnych

### Paginacja

Listy FV pobierają max 100 rekordów (`fetchInvoices`, size=100). Płatności — merge do 200 na status. Dashboard mobile service używa 1000 wewnętrznie. **Ryzyko:** użytkownik pilotażowy z małą bazą (<100 FV/miesiąc) — akceptowalne; przy wzroście — P1-5.

### Wydajność

- Dashboard: jeden request agregujący — OK.
- Płatności: 3 równoległe requesty (`fetchPaymentsForAssignment`) — OK przy <200 rekordach.
- Wyszukiwanie FV w modalu: debounce 350 ms, 2 requesty — OK.
- Brak cache / offline — oczekiwane dla pilotażu.

### Integralność danych

- Kwoty na listach FV: `invoiceListDisplayAmount` preferuje `remaining_amount` (poprawka G2).
- Szczegół FV: `paidAmount` / `remainingAmount` z fallbackiem na obliczenie z brutto.
- Przypisanie płatności: backend waliduje kwotę vs saldo transakcji.
- Zmiana przypisania: ryzyko pośredniego stanu (P1-4).

### UX

- Spójne stany loading/error/retry/empty na wszystkich ekranach P1–P3.
- 401 → logout + redirect `/login` — spójne.
- Brak persystencji sesji (P1-3).
- KSeF tile na dashboardzie pokazuje realne KPI z API, ale ekran `/ksef` to demo (P1-6).

---

## 5. Wykonane poprawki (G2 — przed tym audytem RC)

W ramach audytu RC **nie wprowadzono nowych zmian w kodzie** — brak P0 w logice aplikacji.

Poprawki z audytu G2 (już w repozytorium):

| Plik | Zmiana | Uzasadnienie |
|------|--------|--------------|
| `src/api/mobile.ts` | `invoiceListDisplayAmount()` | Listy FV pokazywały brutto zamiast salda |
| `app/sales-invoices.tsx` | użycie helpera + `overdue_days` | Spójność kwot i terminów |
| `app/purchase-invoices.tsx` | j.w. + styl `dueOver` | j.w. |
| `app/invoice/[id].tsx` | `invoiceDisplayNumber()` | Spójny fallback numeru faktury |

---

## 6. Mocki

| Ekran | Mock biznesowy? |
|-------|-----------------|
| Wszystkie P1–P3 | Nie (realne API) |
| `/ksef` | Tak — `dashboardMock`, symulowany sync |

Import `formatPln` z `@/data/mock` to wyłącznie formatowanie — nie mock danych.

---

## 7. Checklist wdrożenia DS723+ (pilotaż)

1. Backend uruchomiony zgodnie z `docs/DS723_DEPLOYMENT_CHECKLIST.md`
2. Build mobile z `EXPO_PUBLIC_API_BASE_URL` wskazującym na DS723 (HTTPS lub LAN)
3. Upewnić się, że urządzenie ma dostęp do API bez Cloudflare Access (lub skonfigurować CF dla mobile)
4. Konto administratora do logowania w aplikacji
5. Zakres pilotażu: dashboard, FV, dłużnicy/wierzyciele, płatności, rozrachunki (deep link) — **bez KSeF mobile**

---

## 8. Rekomendacja

### **WDRAŻAĆ PILOTAŻOWO**

**Uzasadnienie:**

- Wszystkie kluczowe przepływy operacyjne (FV, rozrachunki po kontrahentach, przypisanie płatności) działają na realnym API z poprawną obsługą błędów.
- Testy backendowe endpointów mobile: 67/67 passed.
- Frontend: lint + TypeScript bez błędów.
- Brak P0 w kodzie aplikacji; P0 dotyczy wyłącznie konfiguracji buildu i sieci (checklist powyżej).
- Ograniczenia pilotażu (KSeF demo, brak persystencji sesji, paginacja, filtr `partially_paid`) są akceptowalne dla wąskiej grupy użytkowników z małą bazą danych.

**Nie rekomendowane:**

- **WDRAŻAĆ** (pełne produkcyjne) — przed pełnym wdrożeniem wymagane P1: sesja, KSeF mobile, paginacja, mapowanie statusów.
- **NIE WDRAŻAĆ** — nieuzasadnione; aplikacja spełnia kryteria pilotażu operacyjnego.

---

*IFGM Release Candidate Audit — ocena gotowości przed wdrożeniem pilotażowym na DS723+.*
