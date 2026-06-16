# IFGM — audyt gotowości produkcyjnej (Guardian2)

**Data:** 2026-05-22  
**Zakres:** `mobile-expo/` + Mobile API (`app/api/routers/mobile.py`, `app/services/mobile_service.py`)  
**Metoda:** analiza statyczna kodu (bez uruchamiania Expo, bez deploya, bez zmian kodu)  
**Spec referencyjna:** `docs/IFGM_SPEC_V1.md`

---

## Werdykt skrócony

| Metryka | Wartość |
|---------|---------|
| **Gotowość do codziennego używania (IFGM v1)** | **~28%** |
| **Gotowość dashboard-only (monitoring KPI)** | **~75%** |
| **Ekrany na realnym API** | 2 / 12 (login + dashboard) |
| **Ekrany na mockach** | 9 |
| **Ekrany brakujące względem spec** | 1 (wierzyciele — dedykowany ekran) |

IFGM ma **działający szkielet produkcyjny** (logowanie JWT, guard tras, dashboard z API), ale **nie spełnia modelu IFGM v1** — większość ekranów operacyjnych nadal serwuje dane demo z `src/data/mock.ts`, mimo że backend Mobile API dla dłużników/wierzycieli jest gotowy.

---

## 1. Inwentaryzacja ekranów

| # | Trasa | Plik | Status | Źródło danych |
|---|-------|------|--------|---------------|
| 1 | `/` (index) | `app/index.tsx` | **Działa** — redirect auth | `AuthContext` |
| 2 | `/login` | `app/login.tsx` | **Real API** | `POST /api/v1/auth/login` |
| 3 | `/dashboard` | `app/dashboard.tsx` | **Real API** | `GET /api/v1/mobile/dashboard` |
| 4 | `/sales-invoices` | `app/sales-invoices.tsx` | **Mocki** | `@/data/mock` → `salesInvoices` |
| 5 | `/purchase-invoices` | `app/purchase-invoices.tsx` | **Mocki** | `@/data/mock` → `purchaseInvoices` |
| 6 | `/debtors` | `app/debtors/index.tsx` | **Mocki** | `@/data/mock` → `debtors` |
| 7 | `/debtors/[id]` | `app/debtors/[id].tsx` | **Mocki** | `@/data/mock` (fallback: `debtors[0]`) |
| 8 | `/settlements` | `app/settlements.tsx` | **Mocki** | `@/data/mock` (rozrachunki demo) |
| 9 | `/payments-unassigned` | `app/payments-unassigned.tsx` | **Mocki** | `@/data/mock` + etykieta „Prototyp” |
| 10 | `/ksef` | `app/ksef.tsx` | **Mocki** | `@/data/mock` + `setTimeout` demo sync |
| 11 | `/invoice/[id]` | `app/invoice/[id].tsx` | **Mocki** | `@/data/mock` (fallback: `allInvoices[0]`) |
| 12 | *(brak)* `/creditors` | — | **Nie istnieje** | KPI „Wierzyciele” → `/settlements` |

**Layout / auth:** `app/_layout.tsx` — `AuthProvider` + `AuthGate` (redirect niezalogowanych na `/login`).

---

## 2. Backend Mobile API

### 2.1 Endpointy istniejące

| Endpoint | Auth | Implementacja | Używany przez IFGM |
|----------|------|---------------|-------------------|
| `GET /api/v1/mobile/dashboard?period=YYYY-MM` | JWT | `MobileService.get_dashboard()` | **TAK** (`fetchDashboard`) |
| `GET /api/v1/mobile/notifications` | JWT | `MobileService.get_notifications()` | **NIE** |
| `GET /api/v1/mobile/debtors` | JWT | `MobileService.get_debtors()` | **NIE** |
| `GET /api/v1/mobile/debtors/{id}` | JWT | `MobileService.get_debtor()` | **NIE** |
| `GET /api/v1/mobile/creditors` | JWT | `MobileService.get_creditors()` | **NIE** |
| `GET /api/v1/mobile/creditors/{id}` | JWT | `MobileService.get_creditor()` | **NIE** |
| `POST /api/v1/auth/login` | — | AuthService | **TAK** |

Testy jednostkowe: `tests/unit/test_mobile_api.py` — pokrycie 6 endpointów mobile (200 OK z mockiem serwisu).

### 2.2 Endpointy IFG użyte pośrednio przez dashboard

Dashboard agreguje dane z istniejących serwisów IFG (faktury, rozrachunki, płatności, KSeF sync status, sesja KSeF). Nie wymaga dodatkowych endpointów mobile poza `/mobile/dashboard`.

### 2.3 Rozbieżności frontend ↔ backend

| Obszar | Backend | Frontend | Rozbieżność |
|--------|---------|----------|-------------|
| Dashboard KPI | `/mobile/dashboard` | Podłączony | Brak |
| Dłużnicy lista/szczegóły | `/mobile/debtors`, `/mobile/debtors/{id}` | Mocki | **Krytyczna** — API gotowe, UI niepodłączone |
| Wierzyciele | `/mobile/creditors`, `/mobile/creditors/{id}` | Brak ekranu, mock w `/settlements` | **Krytyczna** |
| Powiadomienia | `/mobile/notifications` | Brak ekranu | Średnia |
| Faktury (lista/szczegół) | Brak w Mobile API (ogólne `/invoices/*`) | Mocki | **Krytyczna** — brak warstwy mobile |
| Płatności nieprzypisane | Częściowo w dashboard KPI; pełna lista: `/payments/transactions` | Mocki | **Krytyczna** — brak integracji + brak akcji przypisania |
| KSeF sync ręczny | `POST /api/v1/ksef/sync/purchases` | Mock `setTimeout` | **Krytyczna** |
| Notatki windykacyjne | Brak w Mobile API | Mock w dłużnikach | **Krytyczna** względem spec |
| Szczegół faktury z dashboardu | UUID z API w `recent_purchase_invoices` | Ekran mock → fallback na `allInvoices[0]` | **Krytyczna niespójność danych** |

### 2.4 Luki backendu względem IFGM_SPEC_V1

- Brak endpointów mobile dla **notatek windykacyjnych** i **historii kontaktów**
- Brak endpointów mobile dla **przypisania / zmiany / cofnięcia płatności** (logika istnieje w `/payments/*`, ale nie w warstwie mobile)
- Brak dedykowanego **listingu faktur** w Mobile API (możliwe reuse `/invoices`, ale IFGM tego nie woła)
- `MobileService._build_notification_items()` — TODO: powiadomienie `ksef_new_invoice`
- Paginacja dashboardu — TODO gdy faktur > 1000 w miesiącu

---

## 3. Bezpieczeństwo

### 3.1 Logowanie

| Scenariusz | Zachowanie | Ocena |
|------------|------------|-------|
| Nieudane logowanie | `AuthContext.login` → `clearSession()`, `isAuthenticated=false`, błąd na ekranie, użytkownik zostaje na `/login` | **OK** |
| Puste pola | Komunikat lokalny „Nieprawidłowy login lub hasło” | **OK** |
| Brak tokena | `ensureApiAuth()` rzuca `AuthError`; dashboard pokazuje błąd / redirect | **OK** |
| 401 z API | `IfgApiClient` → `AuthError`; dashboard wywołuje `logout()` + redirect `/login` | **OK** |

### 3.2 Ochrona tras

- `AuthGate` w `_layout.tsx`: niezalogowany użytkownik → `router.replace('/login')` dla wszystkich tras poza `login`
- Zalogowany na `/login` → redirect na `/dashboard`
- **Brak per-route guard poza globalnym AuthGate** — wystarczające przy obecnej architekturze Stack

### 3.3 Obejścia / ryzyka

| Ryzyko | Opis | Wpływ prod. |
|--------|------|-------------|
| `EXPO_PUBLIC_API_TOKEN` | W dev ustawia token i `isAuthenticated=true` bez logowania | **Niskie** — tylko build dev; nie stosować w produkcji |
| Brak persystencji JWT | Token tylko w pamięci (`apiClient`); restart app = ponowne logowanie | **UX**, nie luka bezpieczeństwa |
| Mock ekrany po zalogowaniu | Użytkownik widzi fałszywe dane operacyjne | **Wysokie ryzyko biznesowe** — mylące decyzje |
| Dashboard → faktura | Real UUID → mock ekran z błędnymi danymi | **Wysokie** — pozorna autentyczność |
| Cloudflare Access | Publiczny URL `https://ifg.ikonastudio.pl` blokuje mobile API (302/HTML) | **Bloker infra** — wymaga LAN/Tailscale (`mobile-expo/README.md`) |
| Brak testu 401 na mobile API | Endpointy chronione `get_current_user`, brak testu negatywnego w `test_mobile_api.py` | **Niskie** — wzorzec spójny z resztą API |

**Wniosek bezpieczeństwa:** warstwa auth **blokuje dostęp bez logowania** poprawnie. Główne ryzyko to **integralność danych** (mieszanka API + mocki), nie bypass autoryzacji.

---

## 4. Porównanie z IFGM_SPEC_V1

| Moduł spec | Wymaganie | Stan implementacji | % |
|------------|-----------|-------------------|---|
| **Dashboard** | KPI, okres, ostatnie zakupy KSeF | API działa; brak KSeF status w nagłówku (tylko w kafelku KPI) | 80% |
| **KPI** | Dłużnicy, wierzyciele, płatności, KSeF | Wszystkie z `/mobile/dashboard` | 90% |
| **FV sprzedaż** | Lista faktur sprzedażowych | Ekran mock, brak API w IFGM | 0% |
| **FV zakup** | Lista + KSeF | Ekran mock; fragment na dashboardzie z API | 15% |
| **Dłużnicy** | Lista, notatki, szczegóły, akcje (tel/email/notatka) | UI mock; backend list/detail gotowy; brak notatek/akcji | 20% |
| **Wierzyciele** | Analogicznie do dłużników | Brak ekranu; backend gotowy | 10% |
| **Rozrachunki** | Należności/zobowiązania | `/settlements` — mock demo | 0% |
| **Płatności do przypisania** | Lista + przypisanie + korekta | KPI z API; ekran mock; brak akcji | 10% |
| **KSeF** | Status, sync ręczny, nowe zakupy | Status/KPI z API; ekran sync mock | 25% |

**Funkcje spec poza zakresem ekranów, ale wymagane w v1:**
- Zmiana/cofnięcie przypisania płatności — **0%**
- Historia kontaktów / notatki przypisane do faktury — **0%** (mock UI bez backendu)

---

## 5. Ocena gotowości produkcyjnej

### 5.1 Gotowe do codziennego używania

- **Logowanie** — JWT przez `/auth/login`, obsługa błędów
- **Dashboard (monitoring)** — sprzedaż/zakup netto, VAT, KPI, ostatnie zakupy z KSeF (realne dane)
- **Auth guard** — brak dostępu do aplikacji bez sesji (poza dev token)
- **Backend Mobile API** — dashboard + debtors/creditors/notifications (serwer)

### 5.2 Wymaga dopracowania

- Podłączenie ekranów dłużnicy/wierzyciele do istniejących endpointów mobile
- Ekran wierzycieli (dedykowany) zamiast mockowego `/settlements`
- Integracja list faktur i szczegółu faktury (Mobile API lub `/invoices`)
- Ekran KSeF → `POST /ksef/sync/purchases` + status z API
- Ekran płatności → `/payments/transactions` + allocate/reverse
- Persystencja sesji (SecureStore) dla wygody użytkownika
- Ekran powiadomień z `/mobile/notifications`
- KSeF status w nagłówku dashboardu (zgodnie ze spec)

### 5.3 Blokery wdrożenia

1. **9 ekranów operacyjnych na mockach** — aplikacja nie odzwierciedla stanu firmy poza dashboardem
2. **Niespójność dashboard → szczegół faktury** — realne UUID, fałszywe dane na ekranie szczegółów
3. **Brak ekranu wierzycieli** mimo gotowego API
4. **Brak workflow przypisywania płatności** (wymóg spec v1)
5. **Brak notatek windykacyjnych** (backend + frontend)
6. **KSeF sync ręczny niepodłączony** do IFG
7. **Infrastruktura sieciowa** — Cloudflare Access uniemożliwia użycie publicznego URL; wymagany LAN/Tailscale

---

## 6. Metodologia oceny procentowej

Wagi modułów IFGM v1 (suma = 100%):

| Moduł | Waga | Realizacja | Wkład |
|-------|------|------------|-------|
| Dashboard + KPI | 25% | 85% | 21.3% |
| Dłużnicy | 15% | 20% | 3.0% |
| Wierzyciele | 15% | 10% | 1.5% |
| Płatności do przypisania | 15% | 10% | 1.5% |
| KSeF | 10% | 25% | 2.5% |
| Faktury (sprzedaż/zakup/listy) | 10% | 5% | 0.5% |
| Auth + bezpieczeństwo tras | 10% | 90% | 9.0% |

**Suma: ~28%** gotowości IFGM v1 do codziennego używania na iPhone.

*(Dashboard-only: logowanie + dashboard ≈ 75% użyteczności w narrow scope monitoringu finansowego.)*

---

## 7. Rekomendacje (bez implementacji — wyłącznie audyt)

Priorytet integracji (kolejność):

1. Podłączyć `/debtors` i `/debtors/[id]` do `/mobile/debtors*`
2. Dodać `/creditors` + szczegóły z `/mobile/creditors*`
3. Naprawić `/invoice/[id]` — real API (blokuje zaufanie do dashboardu)
4. Podłączyć `/payments-unassigned` + akcje allocate/reverse
5. Podłączyć `/ksef` do sync IFG
6. Dodać notatki windykacyjne (backend mobile + UI)
7. Ekran powiadomień

---

## 8. Pliki kluczowe audytu

```
mobile-expo/app/*.tsx          — ekrany
mobile-expo/src/api/mobile.ts  — jedyny klient mobile API (dashboard)
mobile-expo/src/data/mock.ts   — dane demo
mobile-expo/app/_layout.tsx    — AuthGate
app/api/routers/mobile.py      — router Mobile API
app/services/mobile_service.py — agregacja danych
docs/IFGM_SPEC_V1.md           — spec referencyjna
tests/unit/test_mobile_api.py  — testy API
```

---

*Raport wygenerowany przez audyt Guardian2 — analiza statyczna, bez uruchamiania Expo i bez modyfikacji kodu.*
