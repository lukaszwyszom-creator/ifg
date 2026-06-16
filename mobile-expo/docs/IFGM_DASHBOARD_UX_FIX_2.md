# IFGM Dashboard UX Fix 2

**Data:** 2026-05-22  
**Zakres:** sekcja globalna dashboardu + usunięcie demo KSeF

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/app/dashboard.tsx` | Sekcja „Stan ogólny”, layout kafli, KSeF bez statusu offline |
| `mobile-expo/app/ksef.tsx` | Ekran informacyjny, dane z IFG, bez demo |

**Nie zmieniono:** `mobile-expo/src/api/mobile.ts`, backend, logowanie, FV, płatności, rozrachunki.

---

## Nowa logika sekcji globalnej

Dashboard podzielony na:

1. **Kafel miesięczny** (hero) — Sprzedaż netto, Zakup netto, VAT, przyciski FV sprzedaż/zakup z `month=YYYY-MM`. Reaguje na wybór okresu.

2. **Stan ogólny** — nagłówek + podtytuł „Poza wybranym miesiącem”, zawiera:
   - Dłużnicy
   - Wierzyciele
   - Płatności do przypisania
   - KSeF w IFG

   Dane z `GET /api/v1/mobile/dashboard` (pola globalne: dłużnicy, wierzyciele, płatności, KSeF nie zależą od okresu w KPI — okres wpływa tylko na hero).

3. **Ostatnie zakupy KSeF** — bez zmian (globalny fetch z Fix 1).

---

## Zmiany w kafelkach

### Wierzyciele
Trzy linie po lewej:
- Wierzyciele
- `xx pozycji`
- `Po terminie: yyy zł` (jedna linia, `numberOfLines={1}`)

### Płatności do przypisania
Etykieta w **jednej linii** (`labelCompact`, font 11).

### KSeF w IFG
- Usunięto `ksefStatusLabel` („KSeF offline” / „KSeF OK”).
- Etykieta: **KSeF w IFG**
- Linie: `Ostatni import: …`, `X faktur z KSeF`
- Brak sugestii bezpośredniego połączenia telefonu z KSeF.

---

## Ekran `/ksef`

**Tak — demo usunięte.**

Usunięto:
- import `dashboardMock`
- symulowany import (`setTimeout`)
- przycisk „Pobierz faktury z KSeF”
- sekcję „Ostatnio pobrane (demo)”
- fałszywy status „Sesja aktywna”

Zastąpiono ekranem informacyjnym:
- wyjaśnienie, że sync jest po stronie IFG
- dane z `fetchDashboard` (ostatni import, liczba faktur)
- przycisk „Wróć” (+ `showBack` w nagłówku)

**Nie podłączono** nowego API KSeF mobile — zgodnie z warunkiem stop.

---

## Testy

| Test | Wynik |
|------|-------|
| `npm run lint` | OK |
| `npx tsc --noEmit` | OK |

---

## Ryzyka

| Ryzyko | Ocena |
|--------|-------|
| `ksefStatusLabel` w `mobile.ts` nieużywany | Niskie — helper pozostaje na przyszłość |
| Ekran KSeF pobiera cały dashboard tylko po 2 pola | Akceptowalne (1 request) |

---

*IFGM Dashboard UX Fix 2 — kafle globalne i usunięcie demo KSeF.*
