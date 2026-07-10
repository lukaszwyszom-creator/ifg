# Guardian2 recover-prod — DS723+

Tryb recovery: `python3 scripts/guardian2.py recover-prod --yes`

Bezpieczne operacje: `up -d db`, `up -d api worker` — **bez** `down -v`, bez resetu DB.

**Wygenerowano:** 2026-07-10 21:56:44 UTC  
**Host:** `ds723`  
**Repo:** `/volume1/docker/ifg_v2/ifg_standalone`  

## Podsumowanie

- **db:** działa
- **api:** działa
- **worker:** działa
- **cloudflared-ifg:** działa
- **health check:** `http://127.0.0.1:8000/health` → OK
- **KSeF Connect blocker:** brak (API+worker OK)

## Notatki

- db ready: ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  3 days ago          Up 13 seconds (healthy)   5432/tcp
- backup OK: backups/pre_recovery_20260710_215602.dump (1406922 B)
- api running: ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 47 hours ago        Up 3 seconds (health: starting)   127.0.0.1:8000->8000/tcp
- cloudflared logs zawierają 'error' — sprawdź origin/ingress.

## Precheck recovery

✅ compose config: OK
✅ stack IFG zatrzymany: NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                      PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 47 hours ago        Exited (137) 25 hours ago   127.0.0.1:8000->8000/tcp
ifg
✅ obraz ifg-api:latest: ifg-api:latest
✅ obraz postgres:17: postgres:17
✅ wolumen docker_postgres_data: docker_postgres_data
✅ .env.production: 3440
✅ frontend-react/dist/index.html: 494
✅ wolne miejsce /volume1: /dev/mapper/cachedev_0   96G   32G   65G  33% /volume1
✅ brak równoległego compose build: (brak)

## Backup przed recovery

- ścieżka: `/volume1/docker/ifg_v2/ifg_standalone/backups/pre_recovery_20260710_215602.dump`
- rozmiar: 1406922 B
- OK: True

## Smoke test (read-only)

✅ GET /health → HTTP 200
✅ GET /openapi.json (fragment)
✅ frontend dist/index.html (host)
✅ API container /health → HTTP 200

## Git

- branch: `production`
- HEAD: `f5215b0`

```
?? logs/
```

## Compose services (config)

```
db
api
worker
```

## docker compose ps (przed)

```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                      PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 47 hours ago        Exited (137) 25 hours ago   127.0.0.1:8000->8000/tcp
ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  3 days ago          Exited (0) 25 hours ago     5432/tcp
ifg-worker-1        ifg-api:latest      "sh -c 'python -m ap…"   worker              47 hours ago        Exited (137) 25 hours ago
```

## docker compose ps (po)

```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                            PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 47 hours ago        Up 5 seconds (health: starting)   127.0.0.1:8000->8000/tcp
ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  3 days ago          Up 29 seconds (healthy)           5432/tcp
ifg-worker-1        ifg-api:latest      "sh -c 'python -m ap…"   worker              47 hours ago        Up 6 seconds
```

## Health

- URL: `http://127.0.0.1:8000/health`
- OK: True

```
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

## API logs (tail 120)

```
ifg-api-1  | INFO:     127.0.0.1:56634 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56692 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56708 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56746 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56758 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56796 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56806 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56846 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56868 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56908 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56920 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:56988 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57000 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57038 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57052 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57094 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57106 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57144 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57166 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57200 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57222 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57270 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57290 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57320 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57340 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57370 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57392 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57422 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57464 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57478 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57540 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57554 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57594 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57608 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57644 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57656 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57694 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57706 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57750 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57762 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57820 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57832 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57870 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57882 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57922 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57934 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57970 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:57984 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58024 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58038 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58104 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58116 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58154 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58166 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58208 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58222 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58264 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58278 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58316 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58328 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58388 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58400 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58436 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58448 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58488 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58500 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58536 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58554 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58594 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58606 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58672 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58684 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58720 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58734 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58770 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58782 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58822 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58838 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58876 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58890 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58950 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58962 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:58998 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59016 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59046 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59066 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59096 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59142 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59174 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59200 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59252 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59272 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59302 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59338 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59352 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59388 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59402 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59450 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59464 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59518 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59532 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59572 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59586 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59622 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59640 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59678 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59690 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59730 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59744 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59824 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:59858 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     Shutting down
ifg-api-1  | INFO:     Waiting for application shutdown.
ifg-api-1  | INFO:     Application shutdown complete.
ifg-api-1  | INFO:     Finished server process [1]
ifg-api-1  | INFO:     Started server process [1]
ifg-api-1  | INFO:     Waiting for application startup.
ifg-api-1  | INFO:     Application startup complete.
ifg-api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
ifg-api-1  | INFO:     172.20.0.1:59078 - "GET /health HTTP/1.1" 200 OK
```

## Worker logs (tail 80)

```
ifg-worker-1  | {"time": "2026-07-09 08:00:12,199", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_existing count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,199", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_invalid count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,199", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_error count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,199", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT MISSING metadata_not_in_db_count=0 metadata_not_in_db_sample= xml_not_in_db_count=0 xml_not_in_db_sample= saved_not_in_db_count=0 saved_not_in_db_sample= db_extra_count=0 db_extra_sample= incomplete=False"}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,199", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT SUMMARY nip=9670402857 date_from=2026-07-06 date_to=2026-07-09 sync_path=incremental metadata_returned=0 pages_downloaded=3 invoice_ids_received=0 xml_downloaded=0 saved=0 skipped_existing=0 skipped_invalid=0 skipped_error=0 final_database_count=0 rate_limited=False incomplete=False"}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,226", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases sync done: status=ok incremental=True date_from=2026-07-06 date_to=2026-07-09 subjectType=subject2 ksef_returned=0 created=0 skipped_existing=0 errors=0 incomplete=False"}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,227", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_DONE job_id=2f7ed875-9b9a-463a-8cf6-575729ea0730 saved=0 received=0 rate_limited=False"}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,254", "level": "INFO", "logger": "app.worker", "msg": "Job 2f7ed875-9b9a-463a-8cf6-575729ea0730 (sync_purchase_invoices) zakończony."}
ifg-worker-1  | {"time": "2026-07-09 08:00:12,684", "level": "INFO", "logger": "app.worker", "msg": "Przetworzone joby: 1"}
ifg-worker-1  | {"time": "2026-07-09 14:00:04,200", "level": "INFO", "logger": "app.worker", "msg": "WORKER_POLL_TICK pending_count=1 claimable_count=1 processing=0"}
ifg-worker-1  | {"time": "2026-07-09 14:00:04,293", "level": "INFO", "logger": "app.worker", "msg": "WORKER_JOB_CLAIMED job_id=6ee0a5af-27e1-42bc-88bb-2fadf01ce59f job_type=sync_purchase_invoices attempts=1"}
ifg-worker-1  | {"time": "2026-07-09 14:00:04,395", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_START job_id=6ee0a5af-27e1-42bc-88bb-2fadf01ce59f nip=9670402857"}
ifg-worker-1  | {"time": "2026-07-09 14:00:04,501", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT WINDOW nip=9670402857 date_from=2026-07-07 date_to=2026-07-09 source=incremental requested_date_from=n/a requested_date_to=n/a force_full=False incremental=True days_back=90 overlap_days=2 last_date_to=2026-07-09 last_date_from=2026-07-06 last_success_at=n/a date_types=PermanentStorage,Invoicing,Issue resume=n/a"}
ifg-worker-1  | {"time": "2026-07-09 14:00:05,094", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/auth/token/refresh "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-09 14:00:05,306", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'PermanentStorage', 'from': '2026-07-07T00:00:00Z', 'to': '2026-07-09T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-09 14:00:05,989", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-09 14:00:06,010", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=1 dateType=PermanentStorage pageOffset=0 received=0 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=2026-07-09T11:58:05.854164+00:00"}
ifg-worker-1  | {"time": "2026-07-09 14:00:06,010", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=PermanentStorage pageOffset=0 pageSize=50 page_refs=0 hasMore=False isTruncated=False permanentStorageHwmDate=2026-07-09T11:58:05.854164+00:00 total_refs=0 page_date_min=None page_date_max=None"}
ifg-worker-1  | {"time": "2026-07-09 14:00:06,010", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'Invoicing', 'from': '2026-07-07T00:00:00Z', 'to': '2026-07-09T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-09 14:00:07,475", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-09 14:00:07,476", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=2 dateType=Invoicing pageOffset=0 received=0 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=None"}
ifg-worker-1  | {"time": "2026-07-09 14:00:07,476", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=Invoicing pageOffset=0 pageSize=50 page_refs=0 hasMore=False isTruncated=False permanentStorageHwmDate=None total_refs=0 page_date_min=None page_date_max=None"}
ifg-worker-1  | {"time": "2026-07-09 14:00:07,476", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'Issue', 'from': '2026-07-07T00:00:00Z', 'to': '2026-07-09T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,788", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,788", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=3 dateType=Issue pageOffset=0 received=0 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=None"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,788", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=Issue pageOffset=0 pageSize=50 page_refs=0 hasMore=False isTruncated=False permanentStorageHwmDate=None total_refs=0 page_date_min=None page_date_max=None"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,790", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases incremental sync subjectType=subject2 refs=0 offset=0 date_from=2026-07-07 date_to=2026-07-09"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_received_from_metadata count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_xml_downloaded count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_saved count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_existing count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_invalid count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_error count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,845", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT MISSING metadata_not_in_db_count=0 metadata_not_in_db_sample= xml_not_in_db_count=0 xml_not_in_db_sample= saved_not_in_db_count=0 saved_not_in_db_sample= db_extra_count=0 db_extra_sample= incomplete=False"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,846", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT SUMMARY nip=9670402857 date_from=2026-07-07 date_to=2026-07-09 sync_path=incremental metadata_returned=0 pages_downloaded=3 invoice_ids_received=0 xml_downloaded=0 saved=0 skipped_existing=0 skipped_invalid=0 skipped_error=0 final_database_count=0 rate_limited=False incomplete=False"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,863", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases sync done: status=ok incremental=True date_from=2026-07-07 date_to=2026-07-09 subjectType=subject2 ksef_returned=0 created=0 skipped_existing=0 errors=0 incomplete=False"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,865", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_DONE job_id=6ee0a5af-27e1-42bc-88bb-2fadf01ce59f saved=0 received=0 rate_limited=False"}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,865", "level": "INFO", "logger": "app.worker", "msg": "Job 6ee0a5af-27e1-42bc-88bb-2fadf01ce59f (sync_purchase_invoices) zakończony."}
ifg-worker-1  | {"time": "2026-07-09 14:00:08,913", "level": "INFO", "logger": "app.worker", "msg": "Przetworzone joby: 1"}
ifg-worker-1  | {"time": "2026-07-10 23:56:21,425", "level": "INFO", "logger": "app.worker", "msg": "Worker startuje. poll_interval=5s batch=1"}
ifg-worker-1  | {"time": "2026-07-10 23:56:27,258", "level": "INFO", "logger": "app.worker", "msg": "WORKER_POLL_TICK pending_count=1 claimable_count=1 processing=0"}
ifg-worker-1  | {"time": "2026-07-10 23:56:27,266", "level": "INFO", "logger": "app.worker", "msg": "WORKER_JOB_CLAIMED job_id=21672371-aa04-4916-a475-fd6b2554d05b job_type=sync_purchase_invoices attempts=1"}
ifg-worker-1  | {"time": "2026-07-10 23:56:27,266", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_START job_id=21672371-aa04-4916-a475-fd6b2554d05b nip=9670402857"}
ifg-worker-1  | {"time": "2026-07-10 23:56:27,427", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT WINDOW nip=9670402857 date_from=2026-07-07 date_to=2026-07-10 source=incremental requested_date_from=n/a requested_date_to=n/a force_full=False incremental=True days_back=90 overlap_days=2 last_date_to=2026-07-09 last_date_from=2026-07-07 last_success_at=n/a date_types=PermanentStorage,Invoicing,Issue resume=n/a"}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,408", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/auth/token/refresh "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,465", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'PermanentStorage', 'from': '2026-07-07T00:00:00Z', 'to': '2026-07-10T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,533", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,534", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=1 dateType=PermanentStorage pageOffset=0 received=3 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=2026-07-10T21:54:28.518922+00:00"}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,534", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=PermanentStorage pageOffset=0 pageSize=50 page_refs=3 hasMore=False isTruncated=False permanentStorageHwmDate=2026-07-10T21:54:28.518922+00:00 total_refs=3 page_date_min=20260710 page_date_max=20260710"}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,534", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata dateType=PermanentStorage summary raw_refs=3 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-10 23:56:28,534", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'Invoicing', 'from': '2026-07-07T00:00:00Z', 'to': '2026-07-10T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-10 23:56:29,796", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:29,797", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=2 dateType=Invoicing pageOffset=0 received=3 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=None"}
ifg-worker-1  | {"time": "2026-07-10 23:56:29,797", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=Invoicing pageOffset=0 pageSize=50 page_refs=3 hasMore=False isTruncated=False permanentStorageHwmDate=None total_refs=3 page_date_min=20260710 page_date_max=20260710"}
ifg-worker-1  | {"time": "2026-07-10 23:56:29,798", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata dateType=Invoicing summary raw_refs=3 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-10 23:56:29,798", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'Issue', 'from': '2026-07-07T00:00:00Z', 'to': '2026-07-10T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-10 23:56:31,057", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:31,058", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=3 dateType=Issue pageOffset=0 received=3 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=None"}
ifg-worker-1  | {"time": "2026-07-10 23:56:31,058", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=Issue pageOffset=0 pageSize=50 page_refs=3 hasMore=False isTruncated=False permanentStorageHwmDate=None total_refs=3 page_date_min=20260710 page_date_max=20260710"}
ifg-worker-1  | {"time": "2026-07-10 23:56:31,058", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata dateType=Issue summary raw_refs=3 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-10 23:56:31,058", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata query subjectType=Subject2 dateTypes=PermanentStorage,Invoicing,Issue raw_refs=9 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-10 23:56:31,060", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases incremental sync subjectType=subject2 refs=3 offset=0 date_from=2026-07-07 date_to=2026-07-10"}
ifg-worker-1  | {"time": "2026-07-10 23:56:32,323", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: GET https://api.ksef.mf.gov.pl/v2/invoices/ksef/5611563887-20260710-50E75D000009-F2 "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:32,672", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF sync: zapisano fakturę zakupową 5611563887-20260710-50E75D000009-F2"}
ifg-worker-1  | {"time": "2026-07-10 23:56:33,579", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: GET https://api.ksef.mf.gov.pl/v2/invoices/ksef/5261009190-20260710-5CFA4E400000-30 "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:33,588", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF sync: zapisano fakturę zakupową 5261009190-20260710-5CFA4E400000-30"}
ifg-worker-1  | {"time": "2026-07-10 23:56:34,839", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: GET https://api.ksef.mf.gov.pl/v2/invoices/ksef/9532297910-20260710-7363DD000003-E0 "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-10 23:56:34,848", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF sync: zapisano fakturę zakupową 9532297910-20260710-7363DD000003-E0"}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,180", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_received_from_metadata count=3 first20=5261009190-20260710-5CFA4E400000-30,5611563887-20260710-50E75D000009-F2,9532297910-20260710-7363DD000003-E0 last20="}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,180", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_xml_downloaded count=3 first20=5261009190-20260710-5CFA4E400000-30,5611563887-20260710-50E75D000009-F2,9532297910-20260710-7363DD000003-E0 last20="}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,181", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_saved count=3 first20=5261009190-20260710-5CFA4E400000-30,5611563887-20260710-50E75D000009-F2,9532297910-20260710-7363DD000003-E0 last20="}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,181", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_existing count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,181", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_invalid count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,181", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_error count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,181", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT MISSING metadata_not_in_db_count=0 metadata_not_in_db_sample= xml_not_in_db_count=0 xml_not_in_db_sample= saved_not_in_db_count=0 saved_not_in_db_sample= db_extra_count=0 db_extra_sample= incomplete=False"}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,181", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT SUMMARY nip=9670402857 date_from=2026-07-07 date_to=2026-07-10 sync_path=incremental metadata_returned=3 pages_downloaded=3 invoice_ids_received=3 xml_downloaded=3 saved=3 skipped_existing=0 skipped_invalid=0 skipped_error=0 final_database_count=3 rate_limited=False incomplete=False"}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,184", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases sync done: status=ok incremental=True date_from=2026-07-07 date_to=2026-07-10 subjectType=subject2 ksef_returned=3 created=3 skipped_existing=0 errors=0 incomplete=False"}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,185", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_DONE job_id=21672371-aa04-4916-a475-fd6b2554d05b saved=3 received=3 rate_limited=False"}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,186", "level": "INFO", "logger": "app.worker", "msg": "Job 21672371-aa04-4916-a475-fd6b2554d05b (sync_purchase_invoices) zakończony."}
ifg-worker-1  | {"time": "2026-07-10 23:56:35,298", "level": "INFO", "logger": "app.worker", "msg": "Przetworzone joby: 1"}
```

## DB logs (tail 80)

```
ifg-db-1  | 2026-07-09 20:03:57.893 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.356 s, total=1.004 s; sync files=2, longest=0.301 s, average=0.178 s; distance=4 kB, estimate=14 kB; lsn=0/37C1490, redo lsn=0/37C1438
ifg-db-1  | 2026-07-09 20:08:56.983 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:08:57.732 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.188 s, total=0.750 s; sync files=2, longest=0.143 s, average=0.094 s; distance=5 kB, estimate=13 kB; lsn=0/37C2B20, redo lsn=0/37C2AC8
ifg-db-1  | 2026-07-09 20:13:56.802 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:13:57.938 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.538 s, total=1.136 s; sync files=2, longest=0.405 s, average=0.269 s; distance=7 kB, estimate=12 kB; lsn=0/37C4790, redo lsn=0/37C4738
ifg-db-1  | 2026-07-09 20:18:57.037 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:18:59.075 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=1.099 s, total=2.038 s; sync files=2, longest=0.601 s, average=0.550 s; distance=8 kB, estimate=12 kB; lsn=0/37C6AC0, redo lsn=0/37C6A68
ifg-db-1  | 2026-07-09 20:23:57.148 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:23:58.361 CEST [26] LOG:  checkpoint complete: wrote 4 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.318 s, sync=0.427 s, total=1.213 s; sync files=3, longest=0.261 s, average=0.143 s; distance=17 kB, estimate=17 kB; lsn=0/37CB050, redo lsn=0/37CAFF8
ifg-db-1  | 2026-07-09 20:28:57.460 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:28:58.078 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.119 s, sync=0.104 s, total=0.667 s; sync files=2, longest=0.070 s, average=0.052 s; distance=4 kB, estimate=16 kB; lsn=0/37CC300, redo lsn=0/37CC2A8
ifg-db-1  | 2026-07-09 20:33:57.209 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:33:58.527 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.152 s, sync=0.652 s, total=1.363 s; sync files=2, longest=0.449 s, average=0.326 s; distance=6 kB, estimate=15 kB; lsn=0/37CDBE8, redo lsn=0/37CDB90
ifg-db-1  | 2026-07-09 20:38:57.627 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:38:58.577 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.420 s, total=0.951 s; sync files=2, longest=0.288 s, average=0.210 s; distance=7 kB, estimate=14 kB; lsn=0/37CFB00, redo lsn=0/37CFAA8
ifg-db-1  | 2026-07-09 20:43:57.665 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:43:58.461 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.432 s, total=0.797 s; sync files=2, longest=0.366 s, average=0.216 s; distance=9 kB, estimate=13 kB; lsn=0/37D20B8, redo lsn=0/37D2060
ifg-db-1  | 2026-07-09 20:48:57.554 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:48:58.444 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.321 s, total=0.890 s; sync files=2, longest=0.189 s, average=0.161 s; distance=3 kB, estimate=12 kB; lsn=0/37D2FA8, redo lsn=0/37D2F50
ifg-db-1  | 2026-07-09 20:53:57.540 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:53:58.528 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.548 s, total=0.988 s; sync files=2, longest=0.321 s, average=0.274 s; distance=5 kB, estimate=12 kB; lsn=0/37D4500, redo lsn=0/37D44A8
ifg-db-1  | 2026-07-09 20:58:57.648 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 20:58:58.578 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.332 s, total=0.951 s; sync files=2, longest=0.265 s, average=0.166 s; distance=6 kB, estimate=11 kB; lsn=0/37D6070, redo lsn=0/37D6018
ifg-db-1  | 2026-07-09 21:03:57.669 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:03:58.383 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.100 s, total=0.714 s; sync files=2, longest=0.056 s, average=0.050 s; distance=8 kB, estimate=11 kB; lsn=0/37D81C0, redo lsn=0/37D8168
ifg-db-1  | 2026-07-09 21:08:57.454 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:08:58.022 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.110 s, total=0.569 s; sync files=2, longest=0.066 s, average=0.055 s; distance=2 kB, estimate=10 kB; lsn=0/37D8D78, redo lsn=0/37D8D20
ifg-db-1  | 2026-07-09 21:13:57.120 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:13:57.583 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.133 s, total=0.464 s; sync files=2, longest=0.067 s, average=0.067 s; distance=4 kB, estimate=9 kB; lsn=0/37D9ED8, redo lsn=0/37D9E80
ifg-db-1  | 2026-07-09 21:18:57.671 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:18:58.700 CEST [26] LOG:  checkpoint complete: wrote 4 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.302 s, sync=0.362 s, total=1.030 s; sync files=3, longest=0.230 s, average=0.121 s; distance=20 kB, estimate=20 kB; lsn=0/37DEFB8, redo lsn=0/37DEF60
ifg-db-1  | 2026-07-09 21:23:57.740 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:23:58.661 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.266 s, total=0.922 s; sync files=2, longest=0.155 s, average=0.133 s; distance=7 kB, estimate=18 kB; lsn=0/37E0D98, redo lsn=0/37E0D40
ifg-db-1  | 2026-07-09 21:28:57.757 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:28:58.499 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.333 s, total=0.743 s; sync files=2, longest=0.288 s, average=0.167 s; distance=9 kB, estimate=17 kB; lsn=0/37E31C8, redo lsn=0/37E3170
ifg-db-1  | 2026-07-09 21:33:57.600 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:33:58.405 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.165 s, total=0.806 s; sync files=2, longest=0.121 s, average=0.083 s; distance=3 kB, estimate=16 kB; lsn=0/37E3FF0, redo lsn=0/37E3F60
ifg-db-1  | 2026-07-09 21:38:57.477 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:38:58.299 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.295 s, total=0.823 s; sync files=2, longest=0.222 s, average=0.148 s; distance=5 kB, estimate=15 kB; lsn=0/37E53D8, redo lsn=0/37E5380
ifg-db-1  | 2026-07-09 21:43:57.385 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:43:58.049 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.266 s, total=0.665 s; sync files=2, longest=0.222 s, average=0.133 s; distance=6 kB, estimate=14 kB; lsn=0/37E6DD8, redo lsn=0/37E6D80
ifg-db-1  | 2026-07-09 21:48:57.144 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:48:57.921 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.282 s, total=0.778 s; sync files=2, longest=0.227 s, average=0.141 s; distance=8 kB, estimate=13 kB; lsn=0/37E8E28, redo lsn=0/37E8DD0
ifg-db-1  | 2026-07-09 21:53:57.990 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:53:59.738 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.537 s, total=1.749 s; sync files=2, longest=0.292 s, average=0.269 s; distance=9 kB, estimate=13 kB; lsn=0/37EB4C8, redo lsn=0/37EB470
ifg-db-1  | 2026-07-09 21:58:57.828 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 21:58:58.954 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.228 s, total=1.127 s; sync files=2, longest=0.195 s, average=0.114 s; distance=4 kB, estimate=12 kB; lsn=0/37EC540, redo lsn=0/37EC4B0
ifg-db-1  | 2026-07-09 22:03:58.034 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 22:03:58.570 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.102 s, sync=0.110 s, total=0.537 s; sync files=2, longest=0.087 s, average=0.055 s; distance=5 kB, estimate=11 kB; lsn=0/37EDB80, redo lsn=0/37EDB28
ifg-db-1  | 2026-07-09 22:08:59.225 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 22:08:59.225 CEST [926] LOG:  could not send data to client: Broken pipe
ifg-db-1  | 2026-07-09 22:08:59.326 CEST [926] FATAL:  connection to client lost
ifg-db-1  | 2026-07-09 22:09:09.821 CEST [26] LOG:  checkpoint complete: wrote 4 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=1.932 s, sync=2.479 s, total=11.162 s; sync files=3, longest=2.045 s, average=0.827 s; distance=18 kB, estimate=18 kB; lsn=0/37F3EA0, redo lsn=0/37F23D0
ifg-db-1  | 2026-07-09 22:14:03.440 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 22:19:03.663 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 22:19:45.374 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=9.588 s, sync=3.183 s, total=43.908 s; sync files=2, longest=3.183 s, average=1.592 s; distance=8 kB, estimate=16 kB; lsn=0/37F65F8, redo lsn=0/37F6540
ifg-db-1  | 2026-07-09 22:24:01.450 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 22:24:19.851 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.119 s, sync=6.706 s, total=16.392 s; sync files=2, longest=5.448 s, average=3.353 s; distance=3 kB, estimate=14 kB; lsn=0/37F7D28, redo lsn=0/37F7208
ifg-db-1  | 2026-07-09 22:29:07.159 CEST [26] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-09 22:29:15.524 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.607 s, sync=2.882 s, total=13.586 s; sync files=2, longest=2.406 s, average=1.441 s; distance=4 kB, estimate=13 kB; lsn=0/37F9660, redo lsn=0/37F8528
ifg-db-1  | 2026-07-09 22:32:26.621 CEST [1] LOG:  received fast shutdown request
ifg-db-1  | 2026-07-09 22:32:27.460 CEST [1] LOG:  aborting any active transactions
ifg-db-1  | 2026-07-09 22:32:27.480 CEST [4758] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-09 22:32:27.610 CEST [1] LOG:  background worker "logical replication launcher" (PID 31) exited with exit code 1
ifg-db-1  | 2026-07-09 22:32:28.374 CEST [4759] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-09 22:32:28.537 CEST [32205] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-09 22:32:28.612 CEST [5071] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-09 22:32:28.985 CEST [26] LOG:  shutting down
ifg-db-1  | 2026-07-09 22:32:29.123 CEST [26] LOG:  checkpoint starting: shutdown immediate
ifg-db-1  | 2026-07-09 22:32:31.668 CEST [26] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.001 s, sync=1.299 s, total=2.683 s; sync files=2, longest=1.154 s, average=0.650 s; distance=5 kB, estimate=13 kB; lsn=0/37F9C88, redo lsn=0/37F9C88
ifg-db-1  | 2026-07-09 22:32:31.821 CEST [1] LOG:  database system is shut down
ifg-db-1  | 
ifg-db-1  | 
ifg-db-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
ifg-db-1  | 
ifg-db-1  | 
ifg-db-1  | 2026-07-10 23:55:52.175 CEST [1] LOG:  starting PostgreSQL 17.9 (Debian 17.9-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
ifg-db-1  | 2026-07-10 23:55:52.196 CEST [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
ifg-db-1  | 2026-07-10 23:55:52.196 CEST [1] LOG:  listening on IPv6 address "::", port 5432
ifg-db-1  | 2026-07-10 23:55:52.255 CEST [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
ifg-db-1  | 2026-07-10 23:55:52.343 CEST [30] LOG:  database system was shut down at 2026-07-09 22:32:31 CEST
ifg-db-1  | 2026-07-10 23:55:52.444 CEST [1] LOG:  database system is ready to accept connections
```

## cloudflared-ifg

```
cloudflared-ifg	Up 20 hours
```

```
2026-07-10T20:10:23Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:10:25Z WRN failed to serve tunnel connection error="datagram manager encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:10:25Z WRN Serve tunnel error error="datagram manager encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:10:25Z INF Retrying connection in up to 1s connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:11:05Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:11:08Z INF Registered tunnel connection connIndex=0 connection=85935156-c929-44aa-b93a-3192cf00ef8a event=0 ip=198.41.200.193 location=waw05 protocol=quic
2026-07-10T20:12:49Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:12:51Z ERR failed to run the datagram handler error="timeout: no recent network activity" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:12:51Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:12:51Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:12:49Z ERR failed to run the datagram handler error="timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:12:51Z ERR failed to run the datagram handler error="context canceled" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:12:51Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:12:55Z WRN failed to serve tunnel connection error="datagram manager encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:12:55Z ERR failed to run the datagram handler error="context canceled" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:12:55Z WRN failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:12:55Z WRN failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:13:25Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:13:25Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:13:25Z INF Retrying connection in up to 1s connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:13:25Z INF Retrying connection in up to 1s connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:13:25Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:13:25Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:13:25Z INF Retrying connection in up to 1s connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:13:25Z ERR Serve tunnel error error="datagram manager encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:13:25Z INF Retrying connection in up to 1s connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:13:25Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:13:25Z ERR Connection terminated error="accept stream listener encountered a failure while serving" connIndex=3
2026-07-10T20:13:26Z ERR Connection terminated error="accept stream listener encountered a failure while serving" connIndex=2
2026-07-10T20:13:26Z ERR Connection terminated error="datagram manager encountered a failure while serving" connIndex=1
2026-07-10T20:13:46Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:13:46Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:13:46Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:13:47Z INF Registered tunnel connection connIndex=3 connection=7fb17bf2-bba3-4e9c-a447-e46693b935bd event=0 ip=198.41.192.77 location=waw03 protocol=quic
2026-07-10T20:13:47Z INF Registered tunnel connection connIndex=1 connection=fa970d29-f21e-4294-9274-02e635eff1e3 event=0 ip=198.41.192.227 location=waw03 protocol=quic
2026-07-10T20:13:47Z INF Registered tunnel connection connIndex=2 connection=2bd380f0-92ee-4dcd-ab86-2a138d649e78 event=0 ip=198.41.200.63 location=waw06 protocol=quic
2026-07-10T20:14:00Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:14:00Z ERR failed to run the datagram handler error="timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:14:01Z WRN failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:14:02Z WRN Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:14:02Z INF Retrying connection in up to 4s connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:14:08Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:14:09Z INF Registered tunnel connection connIndex=0 connection=faa9eead-ae34-41e1-b08a-10e7a6632ddf event=0 ip=198.41.200.193 location=waw05 protocol=quic
2026-07-10T20:15:54Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:15:54Z ERR failed to run the datagram handler error="timeout: no recent network activity" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:15:56Z WRN failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:15:56Z WRN Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:15:56Z INF Retrying connection in up to 1s connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:15:57Z WRN Connection terminated error="accept stream listener encountered a failure while serving" connIndex=3
2026-07-10T20:16:05Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:16:04Z ERR failed to run the datagram handler error="timeout: no recent network activity" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:16:04Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:16:05Z ERR failed to accept incoming stream requests error="failed to accept QUIC stream: timeout: no recent network activity" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:16:05Z ERR failed to run the datagram handler error="context canceled" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:16:05Z ERR failed to run the datagram handler error="timeout: no recent network activity" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:16:05Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:16:05Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:16:05Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:16:05Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:16:05Z INF Retrying connection in up to 1s connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:16:05Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:16:05Z INF Retrying connection in up to 1s connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:16:05Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:16:05Z INF Retrying connection in up to 1s connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:16:06Z ERR Connection terminated error="accept stream listener encountered a failure while serving" connIndex=2
2026-07-10T20:16:06Z ERR Connection terminated error="accept stream listener encountered a failure while serving" connIndex=1
2026-07-10T20:16:08Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=0 event=0 ip=198.41.200.193
2026-07-10T20:16:13Z INF Registered tunnel connection connIndex=0 connection=f06de756-c73a-4d9a-bf97-41149f131300 event=0 ip=198.41.200.193 location=waw05 protocol=quic
2026-07-10T20:16:15Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=3 event=0 ip=198.41.192.77
2026-07-10T20:16:15Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=1 event=0 ip=198.41.192.227
2026-07-10T20:16:15Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=2 event=0 ip=198.41.200.63
2026-07-10T20:16:15Z INF Registered tunnel connection connIndex=1 connection=70ad81a3-047f-477e-8d5f-4bc316d67a5c event=0 ip=198.41.192.227 location=waw03 protocol=quic
2026-07-10T20:16:15Z INF Registered tunnel connection connIndex=2 connection=37e1b974-2540-4ee9-9497-fe83a46dab56 event=0 ip=198.41.200.63 location=waw06 protocol=quic
2026-07-10T20:16:15Z INF Registered tunnel connection connIndex=3 connection=f7640f78-eb0e-49fb-a7b9-9b5ee7e0a01d event=0 ip=198.41.192.77 location=waw03 protocol=quic
2026-07-10T21:42:41Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-07-10T21:42:41Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/ event=0 ip=198.41.200.193 type=http
2026-07-10T21:42:41Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-07-10T21:42:41Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/ event=0 ip=198.41.200.193 type=http
2026-07-10T21:42:42Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-07-10T21:42:42Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/favicon.ico event=0 ip=198.41.200.193 type=http
```

## Cloudflare / sieć

Jeśli API odpowiada tylko wewnątrz compose (`127.0.0.1:8000` na hoście DS723+), tunel **cloudflared-ifg** musi wskazywać ten reachable origin (np. `http://127.0.0.1:8000`) albo współdzielić sieć Docker z kontenerem `api`. Ten krok **nie modyfikuje** config cloudflared — tylko diagnostyka.

## Bezpieczeństwo

- Nie wykonano `docker compose down -v`
- Nie usuwano wolumenów
- Dozwolone: `up -d db`, `up -d api worker`
