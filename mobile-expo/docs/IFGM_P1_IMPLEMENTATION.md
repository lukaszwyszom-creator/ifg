# IFGM P1 — raport implementacji

**Data:** 2026-05-22  
**Plan źródłowy:** `mobile-expo/docs/IFGM_TILE_FRONTEND_REUSE_PLAN.md`  
**Zakres:** podłączenie Dłużników i Wierzycieli do Mobile API (bez zmian layoutu).

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | Typy `CounterpartyListItem`, `CounterpartyDetail`, `SettlementInvoiceItem`; `fetchDebtors`, `fetchDebtor`, `fetchCreditors`, `fetchCreditor` |
| `mobile-expo/app/debtors/index.tsx` | Mock → `GET /mobile/debtors`; loading/error/retry |
| `mobile-expo/app/debtors/[id].tsx` | Mock → `GET /mobile/debtors/{id}`; usunięty fallback `debtors[0]` |
| `mobile-expo/app/creditors/index.tsx` | **Nowy** — reuse UI listy dłużników + `GET /mobile/creditors` |
| `mobile-expo/app/creditors/[id].tsx` | **Nowy** — reuse UI szczegółów + `GET /mobile/creditors/{id}` |
| `mobile-expo/app/dashboard.tsx` | Kafel Wierzyciele: `/settlements` → `/creditors` |

**Nie zmieniano:** `/settlements`, layout, `KpiTile`, backend Mobile API.

---

## Co działa na realnym API

| Ekran / trasa | Endpoint |
|---------------|----------|
| Dashboard — KPI Dłużnicy / Wierzyciele | `GET /mobile/dashboard` (wcześniej) |
| `/debtors` — lista | `GET /mobile/debtors` |
| `/debtors/[id]` — szczegóły + faktury | `GET /mobile/debtors/{id}` |
| `/creditors` — lista | `GET /mobile/creditors` |
| `/creditors/[id]` — szczegóły + faktury | `GET /mobile/creditors/{id}` |

Wszystkie wywołania wymagają JWT (`ensureApiAuth`). Błąd 401 → logout + redirect `/login` (wzorzec z dashboardu).

---

## Mapowanie danych

- Lista: `name`, `total_due`, `overdue_due`, `invoices_count` — sortowanie po `overdue_due`, potem `total_due`
- Szczegóły: summary + `invoices[]` (`invoice_id`, `number`, `due_date`, `amount_due`, `overdue_days`)
- Notatki: zawsze „Brak notatek” / „Brak notatek windykacyjnych.” (poza zakresem P1)

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` (`tsc --noEmit`) | **PASS** |
| `tests/unit/test_mobile_api.py` | **6 passed** |

Brak dedykowanych testów jednostkowych w `mobile-expo/` (tylko `tsc`).

---

## Znane ograniczenia

1. **Szczegół faktury** (`/invoice/[id]`) — nadal mock; tap z listy faktur dłużnika/wierzyciela pokazuje dane demo
2. **Notatki windykacyjne** — brak w Mobile API; UI pokazuje pusty stan
3. **Blok „Ostatnia notatka”** — usunięty z renderu (nigdy nie występuje bez API)
4. **`/settlements`** — bez zmian, nadal mock; brak linku z dashboardu po P1
5. **Płatności, KSeF, listy FV** — poza zakresem P1, nadal mocki
6. **Typy expo-router** — trasy `/creditors` wymagają `as Href` do czasu regeneracji typów przez `expo start`
7. **Infrastruktura** — mobile API wymaga LAN/Tailscale (Cloudflare Access)

---

## Następny krok (P2, poza tym commitem)

Podłączyć `/invoice/[id]` do `GET /invoices/{id}` lub dedykowanego mobile endpoint — usuwa rozjazd UUID z API vs mock.

---

*Implementacja IFGM P1 — minimalny diff, bez refaktoru layoutu.*
