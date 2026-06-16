# IFGM RC-FIX — poprawki P1 przed pilotażem

**Data:** 2026-05-22  
**Kontekst:** Release Candidate Audit → rekomendacja „WDRAŻAĆ PILOTAŻOWO”  
**Zakres:** dwa P1 z audytu RC (P1-1, P1-7)

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | Mapowanie `partially_paid` → `partial` w `normalizePaymentStatus()` |
| `mobile-expo/app/payments-unassigned.tsx` | Kwota w modalu wyboru FV: `invoiceListDisplayAmount()` zamiast `total_gross` |

**Nie zmieniono:** backend, dashboard, dłużnicy, wierzyciele, settlements, KSeF, logowanie, architektura.

---

## Poprawka 1 — `partially_paid`

### Problem
Backend zwraca `payment_status: "partially_paid"`. `normalizePaymentStatus()` traktował nieznany status jako `unpaid`, więc faktury częściowo opłacone trafiały do filtra „Nieopłacone”, a filtr „Częściowo” ich nie pokazywał.

### Diff logiczny

**Przed:**
```
paid | partial | unpaid → zwróć bez zmian
inny status → unpaid
```

**Po:**
```
paid | unpaid → zwróć bez zmian
partial | partially_paid → partial
inny status → unpaid
```

### Weryfikacja filtrów list FV
`sales-invoices.tsx` i `purchase-invoices.tsx` używają `normalizePaymentStatus(inv.payment_status)` — poprawka w helperze obejmuje obie listy bez edycji tych plików.

Statusy backendu (z `app/domain/enums.py`): `unpaid`, `partially_paid`, `paid` — alias `partial` zachowany dla kompatybilności wstecznej.

---

## Poprawka 2 — modal przypisywania płatności

### Problem
W modalu wyszukiwania faktury wyświetlano `inv.total_gross` (brutto), podczas gdy użytkownik decyduje o przypisaniu salda.

### Diff logiczny

**Przed:**
```tsx
formatPln(inv.total_gross)
```

**Po:**
```tsx
formatPln(invoiceListDisplayAmount(inv))
```

Helper `invoiceListDisplayAmount()` (istniejący od G2):
- jeśli `remaining_amount != null` → `remaining_amount`
- w przeciwnym razie → `total_gross`

Logika przypisania (`allocatePayment`, kwota z `unassignedPaymentDisplayAmount`) — **bez zmian**.

---

## Testy

| Test | Wynik |
|------|-------|
| `cd mobile-expo && npm run lint` | OK |
| `cd mobile-expo && npx tsc --noEmit` | OK |
| Testy jednostkowe statusów płatności (mobile) | Brak w projekcie |

---

## Pozostałe P1 po poprawkach (z audytu RC)

| ID | Opis | Status |
|----|------|--------|
| P1-1 | Mapowanie `partially_paid` | **Naprawione** |
| P1-2 | Brak linku dashboard → `/settlements` | Otwarte |
| P1-3 | Sesja JWT tylko w pamięci | Otwarte |
| P1-4 | Reassign = reverse + allocate (brak atomowości) | Otwarte |
| P1-5 | Paginacja 100 FV / 200 płatności | Otwarte |
| P1-6 | Ekran `/ksef` — mock demo | Otwarte (poza zakresem) |
| P1-7 | Modal — kwota salda zamiast brutto | **Naprawione** |
| P1-8 | Brak testów routera płatności | Otwarte |

P0 operacyjne (build `EXPO_PUBLIC_API_BASE_URL`, Cloudflare Access) — bez zmian, checklist wdrożenia.

---

*IFGM RC-FIX — dwa P1 zamknięte przed wdrożeniem pilotażowym na DS723+.*
