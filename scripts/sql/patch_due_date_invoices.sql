-- Patch: ustaw due_date dla faktur bez terminu płatności
-- Sprzedaż: termin 14 dni od daty wystawienia
-- Zakupy:   termin 30 dni od daty wystawienia
-- Uruchom: docker compose exec db psql -U ksef_user -d ksef_db -f /scripts/sql/patch_due_date_invoices.sql

BEGIN;

UPDATE invoices
SET    due_date = issue_date + INTERVAL '14 days'
WHERE  due_date IS NULL
  AND  direction = 'sale';

UPDATE invoices
SET    due_date = issue_date + INTERVAL '30 days'
WHERE  due_date IS NULL
  AND  direction = 'purchase';

SELECT direction,
       COUNT(*)                                         AS total,
       COUNT(due_date)                                  AS with_due_date,
       COUNT(*) FILTER (WHERE due_date IS NULL)         AS still_missing
FROM   invoices
GROUP  BY direction
ORDER  BY direction;

COMMIT;
