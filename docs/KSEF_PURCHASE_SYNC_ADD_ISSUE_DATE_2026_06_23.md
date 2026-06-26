# KSeF purchase sync — dodanie dateType Issue (2026-06-23)

## Zmiana

Rozszerzono `_METADATA_DATE_TYPES` o `Issue` obok `PermanentStorage` i `Invoicing`.

Sync zakupów Subject2 zbiera referencje z trzech typów dat, deduplikuje globalnie po `ksefNumber`, bez zmian w zapisie faktur.

Log per dateType: `KSeF metadata dateType=... summary raw_refs=... unique_refs=...`

## Pliki

- `app/integrations/ksef/client.py`
- `tests/unit/test_ksef_metadata_pagination.py`
- `tests/unit/test_ksef_client_retry.py`

## Commit

`fix(ksef): include Issue dateType in purchase metadata query`

## Deploy DS723+

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api worker
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d api worker
```

## Weryfikacja DB

```sql
SELECT MAX(issue_date), MAX(created_at), COUNT(*)
FROM invoices
WHERE direction = 'purchase';
```

Oczekiwanie po sync: `max(issue_date) >= 2026-06-12`.

## Wynik deploy / DB

- **Deploy:** wykonany (DS723+, commit `90ba3fd`, api/worker zrestartowane)
- **Sync:** job `ea5bf164` — **failed** (`Brak aktywnej sesji KSeF dla NIP 9670402857`)
- **DB po deploy (bez udanego sync):**

```sql
SELECT MAX(issue_date), MAX(created_at), COUNT(*)
FROM invoices WHERE direction = 'purchase';

 max_issue_date |        max_created_at         | purchase_count
 2026-06-05     | 2026-06-17 19:28:47.931507+02 |             51
```

Wymagane: aktywna sesja KSeF w UI, potem ponowny sync zakupów.
