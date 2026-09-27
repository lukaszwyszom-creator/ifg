# Guardian2 recover-prod — DS723+

Tryb recovery: `python3 scripts/guardian2.py recover-prod --yes`

Bezpieczne operacje: `up -d db`, `up -d api worker` — **bez** `down -v`, bez resetu DB.

**Wygenerowano:** 2026-07-11 08:56:36 UTC  
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

- db ready: ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  3 days ago          Up 15 seconds (healthy)   5432/tcp
- backup OK: backups/pre_recovery_20260711_085538.dump (1415408 B)
- api running: ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 2 days ago          Up 2 seconds (health: starting)   127.0.0.1:8000->8000/tcp
- cloudflared logs zawierają 'error' — sprawdź origin/ingress.

## Precheck recovery

✅ compose config: OK
✅ stack IFG zatrzymany: NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                     PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 2 days ago          Exited (137) 9 hours ago   127.0.0.1:8000->8000/tcp
ifg-d
✅ obraz ifg-api:latest: ifg-api:latest
✅ obraz postgres:17: postgres:17
✅ wolumen docker_postgres_data: docker_postgres_data
✅ .env.production: 3440
✅ frontend-react/dist/index.html: 494
✅ wolne miejsce /volume1: /dev/mapper/cachedev_0   96G   31G   66G  32% /volume1
✅ brak równoległego compose build: (brak)

## Backup przed recovery

- ścieżka: `/volume1/docker/ifg_v2/ifg_standalone/backups/pre_recovery_20260711_085538.dump`
- rozmiar: 1415408 B
- OK: True

## Smoke test (read-only)

✅ GET /health → HTTP 200
✅ GET /openapi.json (fragment)
✅ frontend dist/index.html (host)
✅ API container /health → HTTP 200

## Git

- branch: `production`
- HEAD: `5b906c2`

```
?? backups/
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
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                     PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 2 days ago          Exited (137) 9 hours ago   127.0.0.1:8000->8000/tcp
ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  3 days ago          Exited (0) 9 hours ago     5432/tcp
ifg-worker-1        ifg-api:latest      "sh -c 'python -m ap…"   worker              2 days ago          Exited (137) 9 hours ago
```

## docker compose ps (po)

```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                            PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 2 days ago          Up 3 seconds (health: starting)   127.0.0.1:8000->8000/tcp
ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  3 days ago          Up 37 seconds (healthy)           5432/tcp
ifg-worker-1        ifg-api:latest      "sh -c 'python -m ap…"   worker              2 days ago          Up 3 seconds
```

## Health

- URL: `http://127.0.0.1:8000/health`
- OK: True

```
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

## API logs (tail 120)

```
ifg-api-1  | INFO:     127.0.0.1:42804 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42860 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42864 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42898 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42904 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42932 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42938 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42968 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:42972 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43026 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43032 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43060 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43064 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43100 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43104 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43138 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43144 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43178 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43184 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43238 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43242 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43274 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43280 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43312 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43316 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43344 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43356 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43380 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43396 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43438 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43450 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43472 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43498 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43522 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43534 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43558 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43570 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43592 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43614 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43656 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43670 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43692 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43706 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43728 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43760 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43768 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43800 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43806 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43864 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43870 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43900 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43908 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43938 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43944 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43974 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:43982 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44012 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44020 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44074 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44080 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44108 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44114 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44144 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44152 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44182 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44188 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44224 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44230 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44280 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44288 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44316 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44322 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44352 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44358 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44386 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44394 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44422 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44428 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44482 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44488 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44520 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44528 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44560 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44566 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44596 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44602 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44630 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44638 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44692 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44698 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44728 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44734 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44766 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44774 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44802 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44808 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44838 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44844 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44900 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44908 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44942 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44948 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44978 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:44984 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45014 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45022 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45050 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45056 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45108 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45114 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45142 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45150 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45180 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     127.0.0.1:45192 - "GET /health HTTP/1.1" 200 OK
ifg-api-1  | INFO:     Shutting down
ifg-api-1  | INFO:     Started server process [1]
ifg-api-1  | INFO:     Waiting for application startup.
ifg-api-1  | INFO:     Application startup complete.
ifg-api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
ifg-api-1  | INFO:     172.20.0.1:34412 - "GET /health HTTP/1.1" 200 OK
```

## Worker logs (tail 80)

```
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
ifg-worker-1  | {"time": "2026-07-11 10:56:13,400", "level": "INFO", "logger": "app.worker", "msg": "Worker startuje. poll_interval=5s batch=1"}
ifg-worker-1  | {"time": "2026-07-11 10:56:15,502", "level": "INFO", "logger": "app.worker", "msg": "WORKER_POLL_TICK pending_count=1 claimable_count=1 processing=0"}
ifg-worker-1  | {"time": "2026-07-11 10:56:15,508", "level": "INFO", "logger": "app.worker", "msg": "WORKER_JOB_CLAIMED job_id=cffc3d07-f6a5-436b-9d36-d20f04bf7598 job_type=sync_purchase_invoices attempts=1"}
ifg-worker-1  | {"time": "2026-07-11 10:56:15,508", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_START job_id=cffc3d07-f6a5-436b-9d36-d20f04bf7598 nip=9670402857"}
ifg-worker-1  | {"time": "2026-07-11 10:56:15,515", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT WINDOW nip=9670402857 date_from=2026-07-08 date_to=2026-07-11 source=incremental requested_date_from=n/a requested_date_to=n/a force_full=False incremental=True days_back=90 overlap_days=2 last_date_to=2026-07-10 last_date_from=2026-07-07 last_success_at=n/a date_types=PermanentStorage,Invoicing,Issue resume=n/a"}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,081", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/auth/token/refresh "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,242", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'PermanentStorage', 'from': '2026-07-08T00:00:00Z', 'to': '2026-07-11T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,305", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,306", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=1 dateType=PermanentStorage pageOffset=0 received=3 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=2026-07-11T08:54:17.294198+00:00"}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,306", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=PermanentStorage pageOffset=0 pageSize=50 page_refs=3 hasMore=False isTruncated=False permanentStorageHwmDate=2026-07-11T08:54:17.294198+00:00 total_refs=3 page_date_min=20260710 page_date_max=20260710"}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,306", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata dateType=PermanentStorage summary raw_refs=3 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-11 10:56:17,306", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'Invoicing', 'from': '2026-07-08T00:00:00Z', 'to': '2026-07-11T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-11 10:56:18,576", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-11 10:56:18,576", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=2 dateType=Invoicing pageOffset=0 received=3 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=None"}
ifg-worker-1  | {"time": "2026-07-11 10:56:18,576", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=Invoicing pageOffset=0 pageSize=50 page_refs=3 hasMore=False isTruncated=False permanentStorageHwmDate=None total_refs=3 page_date_min=20260710 page_date_max=20260710"}
ifg-worker-1  | {"time": "2026-07-11 10:56:18,576", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata dateType=Invoicing summary raw_refs=3 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-11 10:56:18,577", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata request body={'subjectType': 'Subject2', 'dateRange': {'dateType': 'Issue', 'from': '2026-07-08T00:00:00Z', 'to': '2026-07-11T23:59:59Z'}} pageOffset=0 pageSize=50"}
ifg-worker-1  | {"time": "2026-07-11 10:56:19,840", "level": "INFO", "logger": "httpx", "msg": "HTTP Request: POST https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50&sortOrder=Asc "HTTP/1.1 200 OK""}
ifg-worker-1  | {"time": "2026-07-11 10:56:19,841", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT page=3 dateType=Issue pageOffset=0 received=3 hasMore=False isTruncated=False continuationToken=None permanentStorageHwmDate=None"}
ifg-worker-1  | {"time": "2026-07-11 10:56:19,842", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata page subjectType=Subject2 dateType=Issue pageOffset=0 pageSize=50 page_refs=3 hasMore=False isTruncated=False permanentStorageHwmDate=None total_refs=3 page_date_min=20260710 page_date_max=20260710"}
ifg-worker-1  | {"time": "2026-07-11 10:56:19,842", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata dateType=Issue summary raw_refs=3 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-11 10:56:19,842", "level": "INFO", "logger": "app.integrations.ksef.client", "msg": "KSeF metadata query subjectType=Subject2 dateTypes=PermanentStorage,Invoicing,Issue raw_refs=9 unique_refs=3"}
ifg-worker-1  | {"time": "2026-07-11 10:56:19,844", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases incremental sync subjectType=subject2 refs=3 offset=0 date_from=2026-07-08 date_to=2026-07-11"}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,302", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_received_from_metadata count=3 first20=5261009190-20260710-5CFA4E400000-30,5611563887-20260710-50E75D000009-F2,9532297910-20260710-7363DD000003-E0 last20="}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_xml_downloaded count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_saved count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_existing count=3 first20=5261009190-20260710-5CFA4E400000-30,5611563887-20260710-50E75D000009-F2,9532297910-20260710-7363DD000003-E0 last20="}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_invalid count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT REFS refs_skipped_error count=0 first20= last20="}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT MISSING metadata_not_in_db_count=0 metadata_not_in_db_sample= xml_not_in_db_count=0 xml_not_in_db_sample= saved_not_in_db_count=0 saved_not_in_db_sample= db_extra_count=0 db_extra_sample= incomplete=False"}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,303", "level": "INFO", "logger": "app.services.ksef_purchase_sync_audit", "msg": "KSEF_PURCHASE_SYNC_AUDIT SUMMARY nip=9670402857 date_from=2026-07-08 date_to=2026-07-11 sync_path=incremental metadata_returned=3 pages_downloaded=3 invoice_ids_received=3 xml_downloaded=0 saved=0 skipped_existing=3 skipped_invalid=0 skipped_error=0 final_database_count=3 rate_limited=False incomplete=False"}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,306", "level": "INFO", "logger": "app.services.ksef_session_service", "msg": "KSeF purchases sync done: status=ok incremental=True date_from=2026-07-08 date_to=2026-07-11 subjectType=subject2 ksef_returned=3 created=0 skipped_existing=3 errors=0 incomplete=False"}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,308", "level": "INFO", "logger": "app.worker.job_handlers.sync_purchase_invoices", "msg": "KSEF_ASYNC_SYNC_WORKER_DONE job_id=cffc3d07-f6a5-436b-9d36-d20f04bf7598 saved=0 received=3 rate_limited=False"}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,308", "level": "INFO", "logger": "app.worker", "msg": "Job cffc3d07-f6a5-436b-9d36-d20f04bf7598 (sync_purchase_invoices) zakończony."}
ifg-worker-1  | {"time": "2026-07-11 10:56:20,389", "level": "INFO", "logger": "app.worker", "msg": "Przetworzone joby: 1"}
```

## DB logs (tail 80)

```
ifg-db-1  | 2026-07-10 23:55:52.196 CEST [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
ifg-db-1  | 2026-07-10 23:55:52.196 CEST [1] LOG:  listening on IPv6 address "::", port 5432
ifg-db-1  | 2026-07-10 23:55:52.255 CEST [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
ifg-db-1  | 2026-07-10 23:55:52.343 CEST [30] LOG:  database system was shut down at 2026-07-09 22:32:31 CEST
ifg-db-1  | 2026-07-10 23:55:52.444 CEST [1] LOG:  database system is ready to accept connections
ifg-db-1  | 2026-07-11 00:00:52.450 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:01:00.336 CEST [28] LOG:  checkpoint complete: wrote 63 buffers (0.4%); 0 WAL file(s) added, 0 removed, 0 recycled; write=6.102 s, sync=1.288 s, total=7.896 s; sync files=45, longest=0.100 s, average=0.029 s; distance=257 kB, estimate=257 kB; lsn=0/383A390, redo lsn=0/383A300
ifg-db-1  | 2026-07-11 00:05:52.436 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:05:52.818 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.054 s, total=0.383 s; sync files=2, longest=0.032 s, average=0.027 s; distance=9 kB, estimate=232 kB; lsn=0/383C7C0, redo lsn=0/383C768
ifg-db-1  | 2026-07-11 00:10:52.926 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:10:53.712 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.104 s, sync=0.074 s, total=0.794 s; sync files=2, longest=0.040 s, average=0.037 s; distance=3 kB, estimate=209 kB; lsn=0/383D5B0, redo lsn=0/383D558
ifg-db-1  | 2026-07-11 00:15:52.777 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:15:53.140 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.102 s, sync=0.065 s, total=0.364 s; sync files=2, longest=0.043 s, average=0.033 s; distance=5 kB, estimate=189 kB; lsn=0/383E9D0, redo lsn=0/383E978
ifg-db-1  | 2026-07-11 00:20:52.240 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:20:52.756 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.166 s, total=0.516 s; sync files=2, longest=0.099 s, average=0.083 s; distance=6 kB, estimate=171 kB; lsn=0/3840408, redo lsn=0/38403B0
ifg-db-1  | 2026-07-11 00:25:52.845 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:25:53.605 CEST [28] LOG:  checkpoint complete: wrote 5 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.402 s, sync=0.154 s, total=0.761 s; sync files=4, longest=0.077 s, average=0.039 s; distance=26 kB, estimate=156 kB; lsn=0/3846F20, redo lsn=0/3846EC8
ifg-db-1  | 2026-07-11 00:30:52.705 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:30:53.199 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.102 s, sync=0.176 s, total=0.494 s; sync files=2, longest=0.112 s, average=0.088 s; distance=9 kB, estimate=141 kB; lsn=0/3849600, redo lsn=0/38495A8
ifg-db-1  | 2026-07-11 00:35:52.279 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:35:52.838 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.214 s, total=0.559 s; sync files=2, longest=0.137 s, average=0.107 s; distance=4 kB, estimate=128 kB; lsn=0/384A680, redo lsn=0/384A628
ifg-db-1  | 2026-07-11 00:40:52.957 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:40:53.409 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.066 s, total=0.472 s; sync files=2, longest=0.044 s, average=0.033 s; distance=5 kB, estimate=115 kB; lsn=0/384BD00, redo lsn=0/384BCA8
ifg-db-1  | 2026-07-11 00:45:52.460 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:45:53.081 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.188 s, total=0.621 s; sync files=2, longest=0.099 s, average=0.094 s; distance=7 kB, estimate=105 kB; lsn=0/384D9B0, redo lsn=0/384D958
ifg-db-1  | 2026-07-11 00:50:52.120 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:50:52.664 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.221 s, total=0.545 s; sync files=2, longest=0.133 s, average=0.111 s; distance=8 kB, estimate=95 kB; lsn=0/384FCE8, redo lsn=0/384FC90
ifg-db-1  | 2026-07-11 00:55:52.731 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 00:55:53.336 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.102 s, sync=0.099 s, total=0.605 s; sync files=2, longest=0.077 s, average=0.050 s; distance=3 kB, estimate=86 kB; lsn=0/38509C0, redo lsn=0/3850968
ifg-db-1  | 2026-07-11 01:00:52.398 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:00:52.952 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.099 s, total=0.554 s; sync files=2, longest=0.065 s, average=0.050 s; distance=4 kB, estimate=78 kB; lsn=0/3851C98, redo lsn=0/3851C40
ifg-db-1  | 2026-07-11 01:05:53.020 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:05:53.579 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.102 s, sync=0.226 s, total=0.560 s; sync files=2, longest=0.148 s, average=0.113 s; distance=6 kB, estimate=70 kB; lsn=0/38535A0, redo lsn=0/3853548
ifg-db-1  | 2026-07-11 01:10:53.677 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:10:54.050 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.061 s, total=0.374 s; sync files=2, longest=0.033 s, average=0.031 s; distance=7 kB, estimate=64 kB; lsn=0/38554C0, redo lsn=0/3855468
ifg-db-1  | 2026-07-11 01:15:53.138 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:15:53.855 CEST [28] LOG:  checkpoint complete: wrote 5 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.302 s, sync=0.120 s, total=0.718 s; sync files=3, longest=0.076 s, average=0.040 s; distance=22 kB, estimate=60 kB; lsn=0/385AE50, redo lsn=0/385ADF8
ifg-db-1  | 2026-07-11 01:20:53.949 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:20:54.327 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.066 s, total=0.379 s; sync files=2, longest=0.034 s, average=0.033 s; distance=3 kB, estimate=54 kB; lsn=0/385BD80, redo lsn=0/385BD28
ifg-db-1  | 2026-07-11 01:25:53.406 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:25:53.743 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.054 s, total=0.338 s; sync files=2, longest=0.032 s, average=0.027 s; distance=5 kB, estimate=49 kB; lsn=0/385D2A8, redo lsn=0/385D250
ifg-db-1  | 2026-07-11 01:30:53.826 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:30:54.214 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.066 s, total=0.389 s; sync files=2, longest=0.034 s, average=0.033 s; distance=6 kB, estimate=45 kB; lsn=0/385EE20, redo lsn=0/385EDC8
ifg-db-1  | 2026-07-11 01:35:53.307 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:35:53.675 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.054 s, total=0.369 s; sync files=2, longest=0.032 s, average=0.027 s; distance=8 kB, estimate=41 kB; lsn=0/3860FB0, redo lsn=0/3860F58
ifg-db-1  | 2026-07-11 01:40:53.770 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:40:54.136 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.066 s, total=0.367 s; sync files=2, longest=0.033 s, average=0.033 s; distance=2 kB, estimate=37 kB; lsn=0/3861B70, redo lsn=0/3861B18
ifg-db-1  | 2026-07-11 01:45:53.217 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:45:53.574 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.076 s, total=0.357 s; sync files=2, longest=0.043 s, average=0.038 s; distance=4 kB, estimate=34 kB; lsn=0/3862D28, redo lsn=0/3862CD0
ifg-db-1  | 2026-07-11 01:50:53.669 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:50:54.146 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.055 s, total=0.477 s; sync files=2, longest=0.034 s, average=0.028 s; distance=5 kB, estimate=31 kB; lsn=0/38644F8, redo lsn=0/38644A0
ifg-db-1  | 2026-07-11 01:55:53.232 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 01:55:53.662 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.076 s, total=0.430 s; sync files=2, longest=0.045 s, average=0.038 s; distance=7 kB, estimate=29 kB; lsn=0/38662E0, redo lsn=0/3866288
ifg-db-1  | 2026-07-11 02:00:53.758 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 02:00:54.600 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.101 s, sync=0.188 s, total=0.843 s; sync files=2, longest=0.100 s, average=0.094 s; distance=9 kB, estimate=27 kB; lsn=0/3868750, redo lsn=0/38686F8
ifg-db-1  | 2026-07-11 02:05:53.691 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 02:05:54.327 CEST [28] LOG:  checkpoint complete: wrote 4 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.302 s, sync=0.110 s, total=0.637 s; sync files=3, longest=0.054 s, average=0.037 s; distance=17 kB, estimate=26 kB; lsn=0/386CCE0, redo lsn=0/386CC88
ifg-db-1  | 2026-07-11 02:08:53.945 CEST [6413] LOG:  could not send data to client: Broken pipe
ifg-db-1  | 2026-07-11 02:08:54.045 CEST [6413] FATAL:  connection to client lost
ifg-db-1  | 2026-07-11 02:10:55.293 CEST [28] LOG:  checkpoint starting: time
ifg-db-1  | 2026-07-11 02:14:08.461 CEST [1] LOG:  received fast shutdown request
ifg-db-1  | 2026-07-11 02:14:09.529 CEST [1] LOG:  aborting any active transactions
ifg-db-1  | 2026-07-11 02:14:10.251 CEST [58] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-11 02:14:10.682 CEST [177] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-11 02:14:11.181 CEST [176] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-11 02:14:11.700 CEST [68] FATAL:  terminating connection due to administrator command
ifg-db-1  | 2026-07-11 02:14:13.329 CEST [1] LOG:  background worker "logical replication launcher" (PID 33) exited with exit code 1
ifg-db-1  | 2026-07-11 02:14:13.620 CEST [28] LOG:  shutting down
ifg-db-1  | 2026-07-11 02:14:14.726 CEST [28] LOG:  checkpoint starting: shutdown immediate
ifg-db-1  | 2026-07-11 02:14:22.324 CEST [28] LOG:  checkpoint complete: wrote 2 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=2.431 s, sync=0.598 s, total=8.068 s; sync files=2, longest=0.420 s, average=0.299 s; distance=5 kB, estimate=22 kB; lsn=0/386F128, redo lsn=0/386F128
ifg-db-1  | 2026-07-11 02:14:25.385 CEST [1] LOG:  database system is shut down
ifg-db-1  | 
ifg-db-1  | 
ifg-db-1  | PostgreSQL Database directory appears to contain a database; Skipping initialization
ifg-db-1  | 
ifg-db-1  | 
ifg-db-1  | 2026-07-11 10:55:30.642 CEST [1] LOG:  starting PostgreSQL 17.9 (Debian 17.9-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
ifg-db-1  | 2026-07-11 10:55:30.664 CEST [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
ifg-db-1  | 2026-07-11 10:55:30.664 CEST [1] LOG:  listening on IPv6 address "::", port 5432
ifg-db-1  | 2026-07-11 10:55:30.767 CEST [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
ifg-db-1  | 2026-07-11 10:55:30.922 CEST [29] LOG:  database system was shut down at 2026-07-11 02:14:21 CEST
ifg-db-1  | 2026-07-11 10:55:31.089 CEST [1] LOG:  database system is ready to accept connections
```

## cloudflared-ifg

```
cloudflared-ifg	Up 9 hours
```

```
2026-07-11T00:12:14Z WRN Connection terminated error="accept stream listener encountered a failure while serving" connIndex=2
2026-07-11T00:12:30Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=3 event=0 ip=198.41.192.77
2026-07-11T00:12:30Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=2 event=0 ip=198.41.200.63
2026-07-11T00:12:30Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=1 event=0 ip=198.41.192.227
2026-07-11T00:12:35Z INF Registered tunnel connection connIndex=1 connection=6c98691c-6488-4c47-84d1-0e06c001723b event=0 ip=198.41.192.227 location=waw03 protocol=quic
2026-07-11T00:12:35Z INF Registered tunnel connection connIndex=3 connection=2e026408-cc1b-4bb6-aa57-7beb190d1570 event=0 ip=198.41.192.77 location=waw03 protocol=quic
2026-07-11T00:12:35Z INF Registered tunnel connection connIndex=2 connection=819afa0e-99f0-4a47-aaf5-7305b2680f97 event=0 ip=198.41.200.63 location=waw06 protocol=quic
2026-07-11T00:14:14Z INF Initiating graceful shutdown due to signal terminated ...
2026-07-11T00:14:14Z ERR failed to run the datagram handler error="context canceled" connIndex=0 event=0 ip=198.41.200.193
2026-07-11T00:14:14Z WRN failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-11T00:14:14Z WRN Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.193
2026-07-11T00:14:14Z INF Retrying connection in up to 1s connIndex=0 event=0 ip=198.41.200.193
2026-07-11T00:14:14Z ERR failed to run the datagram handler error="Application error 0x0 (remote)" connIndex=2 event=0 ip=198.41.200.63
2026-07-11T00:14:14Z ERR Connection terminated connIndex=0
2026-07-11T00:14:14Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.63
2026-07-11T00:14:14Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.63
2026-07-11T00:14:14Z INF Retrying connection in up to 1s connIndex=2 event=0 ip=198.41.200.63
2026-07-11T00:14:14Z ERR Connection terminated connIndex=2
2026-07-11T00:14:14Z ERR failed to run the datagram handler error="Application error 0x0 (remote)" connIndex=1 event=0 ip=198.41.192.227
2026-07-11T00:14:14Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.227
2026-07-11T00:14:14Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.227
2026-07-11T00:14:14Z INF Retrying connection in up to 1s connIndex=1 event=0 ip=198.41.192.227
2026-07-11T00:14:14Z ERR Connection terminated connIndex=1
2026-07-11T00:14:14Z ERR failed to run the datagram handler error="Application error 0x0 (remote)" connIndex=3 event=0 ip=198.41.192.77
2026-07-11T00:14:14Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=3 event=0 ip=198.41.192.77
2026-07-11T00:14:14Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=3 event=0 ip=198.41.192.77
2026-07-11T00:14:14Z INF Retrying connection in up to 1s connIndex=3 event=0 ip=198.41.192.77
2026-07-11T00:14:14Z ERR Connection terminated connIndex=3
2026-07-11T00:14:14Z ERR no more connections active and exiting
2026-07-11T00:14:14Z INF Tunnel server stopped
2026-07-11T00:14:14Z INF Metrics server stopped
2026-07-11T00:15:04Z INF Starting tunnel tunnelID=6a8cca6d-1d4f-4e18-979e-c0def7d120f0
2026-07-11T00:15:04Z INF Version 2026.6.0 (Checksum 17d853580a4dd9d4d6613691c9123039c20712c38e504f028c0bb4454d43e19f)
2026-07-11T00:15:04Z INF GOOS: linux, GOVersion: go1.26.4, GoArch: amd64
2026-07-11T00:15:04Z INF Settings: map[config:/home/nonroot/.cloudflared/config.yml cred-file:/home/nonroot/.cloudflared/6a8cca6d-1d4f-4e18-979e-c0def7d120f0.json credentials-file:/home/nonroot/.cloudflared/6a8cca6d-1d4f-4e18-979e-c0def7d120f0.json no-autoupdate:true]
2026-07-11T00:15:04Z INF Generated Connector ID: adb90524-9834-4f8d-9767-ae8973f60433
2026-07-11T00:15:04Z INF Initial protocol quic
2026-07-11T00:15:04Z INF ICMP proxy will use 10.0.0.146 as source for IPv4
2026-07-11T00:15:04Z INF ICMP proxy will use ::1 in zone lo as source for IPv6
2026-07-11T00:15:04Z WRN The user running cloudflared process has a GID (group ID) that is not within ping_group_range. You might need to add that user to a group within that range, or instead update the range to encompass a group the user is already in by modifying /proc/sys/net/ipv4/ping_group_range. Otherwise cloudflared will not be able to ping this network error="Group ID 65532 is not between ping group 1 to 0"
2026-07-11T00:15:04Z WRN ICMP proxy feature is disabled error="cannot create ICMPv4 proxy: Group ID 65532 is not between ping group 1 to 0 nor ICMPv6 proxy: socket: permission denied"
2026/07/11 00:15:04 failed to sufficiently increase receive buffer size (was: 208 kiB, wanted: 7168 kiB, got: 416 kiB). See https://github.com/quic-go/quic-go/wiki/UDP-Buffer-Sizes for details.
2026-07-11T00:15:04Z INF ICMP proxy will use 10.0.0.146 as source for IPv4
2026-07-11T00:15:04Z INF ICMP proxy will use ::1 in zone lo as source for IPv6
2026-07-11T00:15:04Z INF Starting metrics server on [::]:20241/metrics
2026-07-11T00:15:04Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=0 event=0 ip=198.41.200.113
2026-07-11T00:15:05Z INF Registered tunnel connection connIndex=0 connection=c9165e32-57cb-4bb9-9d06-c1623b937f4c event=0 ip=198.41.200.113 location=waw05 protocol=quic
2026-07-11T00:15:05Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=1 event=0 ip=198.41.192.227
2026-07-11T00:15:05Z INF Updated to new configuration config="{\"ingress\":[{\"hostname\":\"ifg.ikonastudio.pl\",\"originRequest\":{},\"service\":\"http://127.0.0.1:8000\"},{\"hostname\":\"api.ikonastudio.pl\",\"originRequest\":{},\"service\":\"http://127.0.0.1:8000\"},{\"originRequest\":{},\"service\":\"http_status:404\"}],\"warp-routing\":{\"enabled\":false}}" version=5
2026-07-11T00:15:05Z INF Registered tunnel connection connIndex=1 connection=2ead060c-74cd-4378-88b9-672b8be6bda1 event=0 ip=198.41.192.227 location=waw03 protocol=quic
2026-07-11T00:15:06Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=2 event=0 ip=198.41.192.57
2026-07-11T00:15:06Z INF Registered tunnel connection connIndex=2 connection=6baf052a-9c79-4ec5-b3c1-ff3bfac8c430 event=0 ip=198.41.192.57 location=waw03 protocol=quic
2026-07-11T00:15:07Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=3 event=0 ip=198.41.200.33
2026-07-11T00:15:07Z INF Registered tunnel connection connIndex=3 connection=ccd3f81b-9fbb-4e0d-96b1-bfe49161eb2c event=0 ip=198.41.200.33 location=waw02 protocol=quic
2026-07-11T00:15:10Z INF +-------------------------------------------------------------------------------------+
2026-07-11T00:15:10Z INF |                               CONNECTIVITY PRE-CHECKS                               |
2026-07-11T00:15:10Z INF +-------------------------------------------------------------------------------------+
2026-07-11T00:15:10Z INF |  COMPONENT         TARGET                     STATUS  DETAILS                       |
2026-07-11T00:15:10Z INF |  DNS Resolution    region1.v2.argotunnel.com  PASS    DNS Resolved successfully     |
2026-07-11T00:15:10Z INF |  DNS Resolution    region2.v2.argotunnel.com  PASS    DNS Resolved successfully     |
2026-07-11T00:15:10Z INF |  UDP Connectivity  region1.v2.argotunnel.com  PASS    QUIC connection successful    |
2026-07-11T00:15:10Z INF |  UDP Connectivity  region2.v2.argotunnel.com  PASS    QUIC connection successful    |
2026-07-11T00:15:10Z INF |  TCP Connectivity  region1.v2.argotunnel.com  PASS    HTTP/2 connection successful  |
2026-07-11T00:15:10Z INF |  TCP Connectivity  region2.v2.argotunnel.com  PASS    HTTP/2 connection successful  |
2026-07-11T00:15:10Z INF |  Cloudflare API    api.cloudflare.com:443     PASS    API is reachable              |
2026-07-11T00:15:10Z INF |                                                                                     |
2026-07-11T00:15:10Z INF |  SUMMARY: Environment is healthy. cloudflared will use 'quic' as primary protocol.  |
2026-07-11T00:15:10Z INF +-------------------------------------------------------------------------------------+
2026-07-11T00:15:10Z INF precheck component="DNS Resolution" details="DNS Resolved successfully" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=region1.v2.argotunnel.com
2026-07-11T00:15:10Z INF precheck component="DNS Resolution" details="DNS Resolved successfully" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=region2.v2.argotunnel.com
2026-07-11T00:15:10Z INF precheck component="UDP Connectivity" details="QUIC connection successful" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=region1.v2.argotunnel.com
2026-07-11T00:15:10Z INF precheck component="UDP Connectivity" details="QUIC connection successful" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=region2.v2.argotunnel.com
2026-07-11T00:15:10Z INF precheck component="TCP Connectivity" details="HTTP/2 connection successful" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=region1.v2.argotunnel.com
2026-07-11T00:15:10Z INF precheck component="TCP Connectivity" details="HTTP/2 connection successful" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=region2.v2.argotunnel.com
2026-07-11T00:15:10Z INF precheck component="Cloudflare API" details="API is reachable" run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f status=pass target=api.cloudflare.com:443
2026-07-11T00:15:10Z INF precheck complete hard_fail=false run_id=318ca273-c0ac-40a9-814d-de0cdbd9c83f suggested_protocol=quic
2026-07-11T08:31:05Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=3 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-07-11T08:31:05Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=3 dest=https://ifg.ikonastudio.pl/api/v1/auth/login event=0 ip=198.41.200.33 type=http
2026-07-11T08:34:56Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=3 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-07-11T08:34:56Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=3 dest=https://ifg.ikonastudio.pl/ event=0 ip=198.41.200.33 type=http
```

## Cloudflare / sieć

Jeśli API odpowiada tylko wewnątrz compose (`127.0.0.1:8000` na hoście DS723+), tunel **cloudflared-ifg** musi wskazywać ten reachable origin (np. `http://127.0.0.1:8000`) albo współdzielić sieć Docker z kontenerem `api`. Ten krok **nie modyfikuje** config cloudflared — tylko diagnostyka.

## Bezpieczeństwo

- Nie wykonano `docker compose down -v`
- Nie usuwano wolumenów
- Dozwolone: `up -d db`, `up -d api worker`
