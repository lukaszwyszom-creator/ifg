# KSeF purchase sync — brak nowych faktur w UI (diagnoza)

**Data:** 2026-06-21  
**Job:** `4d6ad6ef-b187-4fd9-8504-6a63985c5ef9` (status: **done**)  
**Commit:** `ca30742`

---

## Werdykt

Sync **zakończył się poprawnie**. **0 nowych faktur**, bo wszystkie **50 referencji** z KSeF **już były w bazie** (`skipped_existing=50`). KSeF zwrócił w metadata **50 ref** w zakresie **2026-03-23 – 2026-06-21**; najnowsza **issue_date w IFG to 2026-06-05**. UI pokazuje zgodnie z danymi (05.06, 03.06, 01.06) — **to nie błąd UI ani resume**.

**Przyczyna prawdopodobna:** deduplikacja + brak nowszych faktur w odpowiedzi KSeF (metadata kończy się na ~2026-06-05), nie awaria sync.

---

## 1. Zakres dat synchronizacji

Z `payload_json` joba i logów workera:

| Pole | Wartość |
|------|---------|
| `date_from` | **2026-03-23** |
| `date_to` | **2026-06-21** |
| `subject_type` | subject2 |
| `dateType` (metadata) | PermanentStorage |

Log: `KSeF purchases incremental sync ... date_from=2026-03-23 date_to=2026-06-21`

---

## 2. Ile referencji zwróciło metadata KSeF

**50 referencji** — log: `KSeF metadata query subjectType=Subject2 dateType=PermanentStorage refs=50`

Finalny wynik joba: `result.received=50`, `skipped_existing=50`, `saved=0`

---

## 3. hasMore / kolejne strony ponad 50

W logach widać **dwie** strony metadata:

```
POST .../metadata?pageOffset=0&pageSize=50 → 200
POST .../metadata?pageOffset=50&pageSize=50 → 200
→ refs=50 (łącznie)
```

Brak logu `hasMore=true` ani `refs>50`. Po obu stronach klient raportuje **refs=50** — typowy scenariusz: **pierwsza strona = 50 pozycji, druga = pusta** (koniec listy KSeF dla tego zapytania).

**Nie widać dowodu**, że KSeF miał >50 faktur i sync urwał paginację; **możliwe ryzyko** pozostaje tylko przy braku logowania `hasMore` (wymagałoby ręcznego zapytania do API KSeF).

---

## 4. Czy KSeF zwrócił faktury z datą po 2026-06-05

**Nie w bazie IFG** — `COUNT(*) WHERE issue_date > '2026-06-05'` = **0**.

Lista `invoice_refs` w payload joba — ostatnie refy (daty w numerze KSeF):

| ref (skrót) | data w ref |
|-------------|------------|
| `7391214067-20260605-...` | 2026-06-05 |
| `5260250995-20260603-...` | 2026-06-03 |
| `8971840043-20260601-...` | 2026-06-01 |

**Brak ref z 20260606–20260621** w zwróconej liście 50 pozycji.

---

## 5. Czy wszystkie zwrócone ref są już w `invoices`

**TAK — 50/50**

```sql
refs_in_job=50 | refs_in_invoices=50 | missing_in_db=0
```

Potwierdza `skipped_existing=50` i `saved=0`.

---

## 6. UI vs dane

| Źródło | Najnowsze issue_date |
|--------|----------------------|
| Baza `invoices` (purchase) | **2026-06-05** (1 szt.) |
| UI (z raportu użytkownika) | 05.06, 03.06, 01.06 |

Rozkład w bazie (TOP):

```
2026-06-05: 1
2026-06-03: 1
2026-06-01: 3
...
```

**UI jest zgodne z danymi** — nie filtruje „błędnie”; po prostu **nie ma w bazie** faktur z issue_date > 2026-06-05.

`max(created_at)` = **2026-06-17** (poprzedni import), nie z tego joba.

---

## 7. Klasyfikacja problemu

| Hipoteza | Ocena |
|----------|--------|
| Awaria sync / resume | ❌ Job `done`, 50/50 ref przetworzone |
| Deduplikacja | ✅ **Główna przyczyna saved=0** |
| Brak nowych FV w KSeF (w zwróconej liście) | ✅ Najnowsza ~2026-06-05 |
| Zły zakres dat | ❌ Zakres obejmuje do 2026-06-21 |
| Limit pageSize=50 / paginacja | ⚠️ Niskie ryzyko (2 strony, refs=50); do wykluczenia zapytaniem KSeF |
| Błąd UI | ❌ Zgodne z DB |

---

## 8. Następne kroki (bez zmian kodu)

1. **KSeF portal / API** — czy dla NIP `9670402857` istnieją faktury zakupowe z **PermanentStorage** po **2026-06-05** (do 2026-06-21). Jeśli tak, a metadata zwraca tylko 50 — sprawdzić paginację / `hasMore`.
2. **Porównanie liczby FV w KSeF vs 50** — jeśli w KSeF jest np. 60+, uruchomić sync z logowaniem liczby elementów na `pageOffset=50`.
3. **Jeśli w KSeF nie ma FV po 05.06** — oczekiwanie użytkownika jest niezgodne ze stanem KSeF; sync działa poprawnie.
4. **`ksef_sync_states`** — `status=error` w DB mimo `done` joba (state_json ma poprawne `last_counts`); kosmetyka statusu, nie przyczyna braku FV.

---

## Podsumowanie liczbowe

| Metryka | Wartość |
|---------|---------|
| Zakres sync | **2026-03-23 – 2026-06-21** |
| Metadata refs | **50** |
| Zapisane (saved) | **0** |
| Pominięte (existing) | **50** |
| max issue_date w bazie | **2026-06-05** |
| Faktury issue_date > 2026-06-05 | **0** |
