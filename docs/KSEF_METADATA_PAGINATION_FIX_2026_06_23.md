# KSeF metadata pagination fix (2026-06-23)

## Zmiana

| Plik | Diff |
|------|------|
| `app/integrations/ksef/client.py` | `page_offset += 1`; `sortOrder=Asc` w params |
| `scripts/ksef_metadata_probe.py` | help `--page-offset`: numer strony 0,1,2… |

Root cause: OpenAPI MF — `pageOffset` to numer strony, nie offset rekordów.

Migracja DB: **brak**.

## Commit

`2c5591f` — `fix(ksef): use page number not record offset for metadata pagination`

## Deploy DS723+

- `git pull` → OK
- `docker compose build api worker` → OK
- `docker compose up -d api worker` → OK

## Sync zakupów

Job `dd5d2849-c8ee-473d-8369-ea22c7aebb2a` — **failed**

```
Brak aktywnej sesji KSeF dla NIP 9670402857.
```

Brak aktywnej sesji w DB — sync nie wszedł w metadata query. Wymagane połączenie KSeF w UI przed ponownym sync.

## SELECT purchase (po deploy)

```
 max_issue_date |        max_created_at         | purchase_count
 2026-06-05     | 2026-06-17 19:28:47.931507+02 |             51
```

Bez zmian względem stanu sprzed sync (sesja nieaktywna).

## Weryfikacja paginacji (po aktywnej sesji)

Probe strona 1:

```bash
python scripts/ksef_metadata_probe.py --env production --auth fresh --nip 9670402857 \
  --subject Subject2 --date-type PermanentStorage \
  --date-from 2026-03-25 --date-to 2026-06-23 --page-offset 1 --page-size 50
```

Oczekiwanie: ref > 0 jeśli `hasMore=true` na stronie 0.
