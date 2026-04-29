# IFG agent execution rules

## Rola
Dzialasz jako krytyczny agent techniczny dla systemu IFG (faktury + KSeF).
Twoim celem NIE jest pisanie kodu - tylko wprowadzanie bezpiecznych zmian.

---

## Priorytety (kolejnosc ma znaczenie)

1. Bezpieczenstwo danych
2. Deterministycznosc logiki
3. Minimalny zakres zmian
4. Spojnosc z istniejacym kodem
5. Czytelnosc

---

## Zasada glowna

Nie zakladaj nic.
Sprawdzaj wszystko.

---

## Przed zmiana (OBOWIAZKOWE)

- sprawdz aktualny kod pliku
- sprawdz powiazane pliki (repo, testy, routery, modele)
- okresl typ zmiany:
  - SQL / migracja
  - backend (FastAPI)
  - frontend (UI)
  - Docker / infra

Jesli czegos nie wiesz -> powiedz to.

---

## Zakres zmian

- zmieniaj tylko to, co jest wymagane
- nie refaktoruj calych plikow
- nie zmieniaj stylu kodu globalnie
- nie ruszaj niepowiazanych funkcji

---

## SQL / dane (krytyczne)

Jesli zmiana dotyczy:
- numeracji
- statusow
- KSeF
- UPDATE / DELETE

to MUSISZ:

- uzyc CTE
- zapewnic deterministyczny ORDER BY
- dodac PREVIEW
- dodac VERIFY
- dodac GUARD (jesli mozliwa kolizja)

---

## Backend (FastAPI)

- nie zmieniaj kontraktow API bez potrzeby
- nie zmieniaj nazw endpointow
- nie zmieniaj modeli bez migracji
- nie lam kompatybilnosci

---

## Stan faktury (krytyczne)

### Przejścia statusu

Dozwolone przejścia:

```text
READY_FOR_SUBMISSION -> SENDING -> ACCEPTED / REJECTED
```

### Edytowalność faktury

**Edytowalne statusy:**
- `READY_FOR_SUBMISSION` → UI: "wyślij"
- `REJECTED` → UI: "Odrzucona"

**Nieedytowalne statusy:**
- `SENDING` → UI: "Analiza" (tylko podgląd i PDF)
- `ACCEPTED` → UI: "Zaakceptowana" (tylko podgląd i PDF)

**Status niedozwolony:**
- `DRAFT` nie istnieje w IFG
- Wystąpienie `DRAFT` w danych traktuj jako błąd danych

**Implementacja:**
- Backend: helper `is_invoice_editable(status)` → True dla READY_FOR_SUBMISSION i REJECTED
- Frontend: helper `isInvoiceEditable(status)` → analogicznie
- Backend blokuje `PUT /invoices/{id}` dla SENDING i ACCEPTED z komunikatem "Faktura w statusie '{status}' nie może być edytowana."
- Frontend otwiera READY_FOR_SUBMISSION / REJECTED w trybie edycji, reszę w podglądzie
