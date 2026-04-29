-- =============================================================================
-- FIX: Draft invoice numbering — 2026-04-26
-- =============================================================================
-- Cel:
--   Faktury ze statusem 'draft' i number_local IS NULL otrzymują numer w formacie
--   NN/MM/YYYY (np. 01/03/2026), numerowany miesięcznie (wg issue_date),
--   po czym status zmienia się na 'ready_for_submission'.
--
-- ZAKRES ZMIAN:
--   Tylko rekordy spełniające JEDNOCZEŚNIE:
--     status = 'draft'
--     AND number_local IS NULL
--
-- Faktury z istniejącym number_local NIE są modyfikowane.
-- Faktury ze statusem accepted/rejected/sending NIE są modyfikowane.
--
-- URUCHOMIENIE:
--   docker compose -f docker/docker-compose.yml exec -T db \
--     psql -U postgres -d ksef_backend \
--     < scripts/sql/fix_draft_invoice_numbering_2026_04_26.sql
--
-- KOLEJNOŚĆ DZIAŁANIA:
--   1. BACKUP  — zrób przed czymkolwiek
--   2. PREVIEW — przejrzyj wyniki, nie wprowadza zmian
--   3. MIGRATION — uruchom po weryfikacji PREVIEW
--   4. VERIFY  — sprawdź wyniki po migracji
-- =============================================================================


-- =============================================================================
-- SEKCJA 0: BACKUP (uruchom PRZED migracją)
-- =============================================================================
-- Skopiuj tabelę invoices do tabeli backup. Wykonaj to RĘCZNIE przed migracją:
--
--   docker compose -f docker/docker-compose.yml exec -T db \
--     psql -U postgres -d ksef_backend -c \
--     "CREATE TABLE invoices_backup_before_draft_fix_20260426 AS SELECT * FROM invoices;"
--
-- Weryfikacja backupu:
--   SELECT COUNT(*) FROM invoices_backup_before_draft_fix_20260426;
--
-- Rollback (jeśli coś pójdzie nie tak):
--   -- Przywrócenie jest możliwe tylko z backupu. Nie ma prostego UNDO.
--   -- Przykład ręcznego przywrócenia statusu i numeru dla konkretnej faktury:
--   --
--   --   UPDATE invoices
--   --   SET status = b.status,
--   --       number_local = b.number_local,
--   --       updated_at = b.updated_at
--   --   FROM invoices_backup_before_draft_fix_20260426 b
--   --   WHERE invoices.id = b.id
--   --     AND b.status = 'draft';
--   --
--   -- UWAGA: To przywraca status i numer, ale nie cofa ewentualnych
--   --        downstream-efektów (np. wysyłek do KSeF).
-- =============================================================================


-- =============================================================================
-- SEKCJA 1: PREVIEW (tylko SELECT, bez zmian)
-- =============================================================================
-- Pokazuje faktury draft bez numeru ORAZ ich proponowane numery po migracji.
-- Bezpieczne do uruchomienia w dowolnym momencie.

\echo '=== PREVIEW: Faktury draft bez numeru — proponowane numery ==='

WITH candidates AS (
  SELECT
    id,
    issue_date,
    number_local,
    status,
    created_at,
    updated_at,
    date_trunc('month', issue_date) AS month_bucket
  FROM invoices
  WHERE status = 'draft'
    AND number_local IS NULL
),
existing_month_max AS (
  SELECT
    date_trunc('month', to_date('01/' || substring(number_local FROM '\\d+/(\\d{2}/\\d{4})'), 'DD/MM/YYYY')) AS month_bucket,
    MAX(substring(number_local FROM '(\\d+)/\\d{2}/\\d{4}')::int)                                            AS max_existing_seq
  FROM invoices
  WHERE number_local IS NOT NULL
    AND number_local ~ '^\\d{2}/\\d{2}/\\d{4}$'
  GROUP BY date_trunc('month', to_date('01/' || substring(number_local FROM '\\d+/(\\d{2}/\\d{4})'), 'DD/MM/YYYY'))
),
numbering AS (
  SELECT
    c.id,
    c.issue_date,
    c.status,
    c.created_at,
    c.month_bucket,
    COALESCE(em.max_existing_seq, 0)                                              AS max_existing_seq,
    row_number() OVER (
      PARTITION BY c.month_bucket
      ORDER BY c.issue_date ASC, c.created_at ASC, c.id ASC
    ) AS seq,
    -- Numer od następnego wolnego numeru w miesiącu: max_existing_seq + row_number()
    LPAD(
      (COALESCE(em.max_existing_seq, 0) + row_number() OVER (
        PARTITION BY c.month_bucket
        ORDER BY c.issue_date ASC, c.created_at ASC, c.id ASC
      ))::text,
      2,
      '0'
    ) || '/' || to_char(c.issue_date, 'MM/YYYY') AS proposed_number
  FROM candidates c
  LEFT JOIN existing_month_max em
    ON em.month_bucket = c.month_bucket
)
SELECT
  n.id,
  n.issue_date,
  n.status AS old_status,
  n.proposed_number
FROM numbering n
ORDER BY n.issue_date ASC, n.created_at ASC, n.id ASC;

\echo ''
\echo '=== PREVIEW: Liczba kandydatów do migracji ==='
SELECT COUNT(*) AS draft_without_number
FROM invoices
WHERE status = 'draft'
  AND number_local IS NULL;

\echo ''
\echo '=== PREVIEW: Podział kandydatów wg miesiąca issue_date ==='
SELECT
  to_char(date_trunc('month', issue_date), 'MM/YYYY') AS miesiac,
  COUNT(*)                                             AS liczba_faktur
FROM invoices
WHERE status = 'draft'
  AND number_local IS NULL
GROUP BY date_trunc('month', issue_date)
ORDER BY date_trunc('month', issue_date);

\echo ''
\echo '=== PREVIEW: Najwyższy istniejący numer per miesiąc (inne faktury) ==='
-- Pomaga ocenić, czy numeracja zacznie się od 01 i nie nałoży się na istniejące
SELECT
  substring(number_local FROM '\d+/(\d{2}/\d{4})') AS miesiac,
  MAX(substring(number_local FROM '(\d+)/\d{2}/\d{4}')::int) AS max_istniejacy_seq
FROM invoices
WHERE number_local IS NOT NULL
  AND number_local ~ '^\d{2}/\d{2}/\d{4}$'
GROUP BY substring(number_local FROM '\d+/(\d{2}/\d{4})')
ORDER BY miesiac;

\echo ''
\echo '=== PREVIEW: Istniejące numery faktur (wszystkie rekordy z number_local) ==='
SELECT issue_date, number_local, status
FROM invoices
WHERE number_local IS NOT NULL
ORDER BY issue_date, number_local;


-- =============================================================================
-- SEKCJA 2: MIGRATION (wykonaj TYLKO po przejrzeniu PREVIEW i zrobieniu BACKUP)
-- =============================================================================
-- Transakcja — w razie błędu całość zostaje wycofana automatycznie.

\echo ''
\echo '=== MIGRATION: Start (BEGIN) ==='

BEGIN;

-- Guard bezpieczeństwa: przerwij migrację, jeśli proponowane numery kolidują
-- z już istniejącymi numerami w tabeli invoices.
DO $$
BEGIN
  IF EXISTS (
    WITH candidates AS (
      SELECT
        i.id,
        i.issue_date,
        i.created_at,
        date_trunc('month', i.issue_date) AS month_bucket
      FROM invoices i
      WHERE i.status = 'draft'
        AND i.number_local IS NULL
    ),
    existing_month_max AS (
      SELECT
        date_trunc('month', to_date('01/' || substring(number_local FROM '\\d+/(\\d{2}/\\d{4})'), 'DD/MM/YYYY')) AS month_bucket,
        MAX(substring(number_local FROM '(\\d+)/\\d{2}/\\d{4}')::int)                                            AS max_existing_seq
      FROM invoices
      WHERE number_local IS NOT NULL
        AND number_local ~ '^\\d{2}/\\d{2}/\\d{4}$'
      GROUP BY date_trunc('month', to_date('01/' || substring(number_local FROM '\\d+/(\\d{2}/\\d{4})'), 'DD/MM/YYYY'))
    ),
    proposed_numbers AS (
      SELECT
        c.id,
        LPAD(
          (COALESCE(em.max_existing_seq, 0) + ROW_NUMBER() OVER (
            PARTITION BY c.month_bucket
            ORDER BY c.issue_date, c.created_at, c.id
          ))::text,
          2,
          '0'
        ) || '/' || TO_CHAR(c.issue_date, 'MM/YYYY') AS new_number
      FROM candidates c
      LEFT JOIN existing_month_max em
        ON em.month_bucket = c.month_bucket
    ),
    existing_numbers AS (
      SELECT
        i.id,
        i.number_local
      FROM invoices i
      WHERE i.number_local IS NOT NULL
        AND i.number_local ~ '^\\d{2}/\\d{2}/\\d{4}$'
    ),
    all_numbers AS (
      SELECT number_local FROM existing_numbers
      UNION ALL
      SELECT new_number AS number_local FROM proposed_numbers
    ),
    duplicates AS (
      SELECT
        number_local,
        COUNT(*) AS cnt
      FROM all_numbers
      GROUP BY number_local
      HAVING COUNT(*) > 1
    )
    SELECT 1
    FROM duplicates
  ) THEN
    RAISE EXCEPTION 'Przerwano migrację: wykryto kolizje number_local z istniejącymi rekordami.';
  END IF;
END $$;

WITH candidates AS (
  SELECT
    i.id,
    i.issue_date,
    i.created_at,
    date_trunc('month', i.issue_date) AS month_bucket
  FROM invoices i
  WHERE i.status = 'draft'
    AND i.number_local IS NULL
),
existing_month_max AS (
  SELECT
    date_trunc('month', to_date('01/' || substring(number_local FROM '\\d+/(\\d{2}/\\d{4})'), 'DD/MM/YYYY')) AS month_bucket,
    MAX(substring(number_local FROM '(\\d+)/\\d{2}/\\d{4}')::int)                                            AS max_existing_seq
  FROM invoices
  WHERE number_local IS NOT NULL
    AND number_local ~ '^\\d{2}/\\d{2}/\\d{4}$'
  GROUP BY date_trunc('month', to_date('01/' || substring(number_local FROM '\\d+/(\\d{2}/\\d{4})'), 'DD/MM/YYYY'))
),
numbered AS (
  SELECT
    c.id,
    LPAD(
      (COALESCE(em.max_existing_seq, 0) + ROW_NUMBER() OVER (
        PARTITION BY c.month_bucket
        ORDER BY c.issue_date, c.created_at, c.id
      ))::text,
      2,
      '0'
    ) || '/' || TO_CHAR(c.issue_date, 'MM/YYYY') AS new_number
  FROM candidates c
  LEFT JOIN existing_month_max em
    ON em.month_bucket = c.month_bucket
)
UPDATE invoices i
SET
  number_local = numbered.new_number,
  status       = 'ready_for_submission',
  updated_at   = now()
FROM numbered
WHERE i.id = numbered.id
  AND i.status = 'draft'
  AND i.number_local IS NULL;

\echo '--- Liczba zmienionych rekordów (powyżej): ==='

-- Pokaż zmienione rekordy przed COMMIT (w obrębie transakcji)
SELECT
  id,
  issue_date,
  number_local,
  status,
  updated_at
FROM invoices
WHERE status = 'ready_for_submission'
  AND updated_at >= now() - interval '5 seconds'
ORDER BY issue_date ASC, id ASC;

\echo ''
\echo '=== MIGRATION: COMMIT ==='
COMMIT;

\echo '=== MIGRATION: Zakończona ==='


-- =============================================================================
-- SEKCJA 3: VERIFY (uruchom po MIGRATION)
-- =============================================================================

\echo ''
\echo '=== VERIFY: Liczba faktur ze statusem draft po migracji ==='
SELECT COUNT(*) AS remaining_draft
FROM invoices
WHERE status = 'draft';

\echo ''
\echo '=== VERIFY: Liczba faktur bez number_local po migracji ==='
SELECT COUNT(*) AS without_number
FROM invoices
WHERE number_local IS NULL;

\echo ''
\echo '=== VERIFY: Wszystkie statusy z liczbą rekordów ==='
SELECT
  status,
  COUNT(*) AS liczba
FROM invoices
GROUP BY status
ORDER BY status;

\echo ''
\echo '=== VERIFY: Numery faktur per miesiąc (nowo przypisane) ==='
SELECT
  substring(number_local FROM '\d+/(\d{2}/\d{4})') AS miesiac,
  COUNT(*)                                          AS liczba_numerow,
  MIN(number_local)                                 AS min_numer,
  MAX(number_local)                                 AS max_numer
FROM invoices
WHERE number_local ~ '^\d{2}/\d{2}/\d{4}$'
GROUP BY substring(number_local FROM '\d+/(\d{2}/\d{4})')
ORDER BY miesiac;

\echo ''
\echo '=== VERIFY: Sprawdzenie duplikatów number_local ==='
SELECT
  number_local,
  COUNT(*) AS wystapienia
FROM invoices
WHERE number_local IS NOT NULL
GROUP BY number_local
HAVING COUNT(*) > 1
ORDER BY number_local;

-- Oczekiwany wynik: 0 wierszy (brak duplikatów)

\echo ''
\echo '=== VERIFY (wymagane minimalne): duplikaty numerów ==='
SELECT number_local, COUNT(*)
FROM invoices
GROUP BY number_local
HAVING COUNT(*) > 1;

\echo ''
\echo '=== VERIFY (wymagane minimalne): statusy ==='
SELECT status, COUNT(*)
FROM invoices
GROUP BY status;

\echo ''
\echo '=== VERIFY (wymagane minimalne): brak numerów ==='
SELECT COUNT(*)
FROM invoices
WHERE number_local IS NULL;
