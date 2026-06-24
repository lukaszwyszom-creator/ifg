# KSeF metadata pagination fix (2026-06-23)

## Zmiana

- `page_offset += 1` (numer strony, nie offset rekordów)
- `sortOrder=Asc` w params metadata query
- probe: help `--page-offset` wyjaśnia numer strony

## Commit

_(uzupełnione po commit)_

## Deploy DS723+

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api worker
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d api worker
```

Migracja DB: **brak**. Backup przed migracją: N/A.

## Sync zakupów

_(uzupełnione po deploy)_

## SELECT purchase

```sql
SELECT MAX(issue_date), MAX(created_at), COUNT(*)
FROM invoices WHERE direction = 'purchase';
```

_(wynik poniżej)_
