# Invoice numbering rules

## Cel
Numeracja faktur musi być deterministyczna, miesięczna i odporna na kolizje.

## Format
Numer lokalny faktury:
NN/MM/YYYY

Przykład:
01/04/2026

## Zasada miesięczna
Numeracja liczona jest osobno dla każdego miesiąca z `issue_date`.

Miesiąc:
`date_trunc('month', issue_date)`

## Nowe numery
Nowy numer ma zaczynać się od następnego wolnego numeru w danym miesiącu.

Przykład:
Istnieją:
01/04/2026
02/04/2026

Nowa faktura:
03/04/2026

## Faktury do numeracji
Uwzględniaj wyłącznie:
- status = 'ready_for_submission'
- number_local IS NULL

## Kolejność
Numerowanie faktur musi być deterministyczne:

```sql
ORDER BY issue_date ASC, created_at ASC, id ASC
```
