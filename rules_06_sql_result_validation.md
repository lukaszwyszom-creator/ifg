# SQL result validation rules

## Cel
Agent ma NIE tylko generować SQL, ale również krytycznie oceniać wynik.

---

## Zasada główna

Jeśli wynik zapytania może:
- zmienić dane
- zmienić statusy
- zmienić numerację
- wpłynąć na KSeF

➡️ MUSISZ zrobić walidację wyniku.

---

## Obowiązkowe pytania kontrolne (agent ma sam sobie zadać)

1. Czy liczba rekordów do zmiany jest zgodna z oczekiwaniem?
2. Czy powstają duplikaty?
3. Czy coś zostaje NULL, a nie powinno?
4. Czy zmieniam tylko to, co chciałem?
5. Czy logika działa dla edge-case’ów?

---

## Edge cases (OBOWIĄZKOWE)

Agent musi sprawdzić:

- brak istniejących numerów w miesiącu
- istniejące numery z lukami (np. 01, 05, 06)
- ręcznie wpisane błędne numery
- wiele faktur z tym samym issue_date
- różne created_at
- równoległe ID

---

## VERIFY – minimalny zestaw

### 1. duplikaty

```sql
SELECT number_local, COUNT(*)
FROM invoices
GROUP BY number_local
HAVING COUNT(*) > 1;
```

### 2. status counts

```sql
SELECT status, COUNT(*)
FROM invoices
GROUP BY status;
```

### 3. brak numerów

```sql
SELECT COUNT(*)
FROM invoices
WHERE number_local IS NULL;
```
