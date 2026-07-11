# GWO-IFG-NOTIFY-0002 — Utwardzenie powiadomień e-mail i wdrożenie produkcyjne

**Data:** 2026-07-11  
**Repo:** `~/projekty/ifg_standalone`  
**Branch:** `production`  
**Środowisko:** DS723+ (`/volume1/docker/ifg_v2/ifg_standalone`)

---

## 1. Status końcowy

**STATUS:** `SUCCESS_CODE / BLOCKED_CONFIG`

- Kod, testy, commit `4a71c14`, push i deploy Guardian **LIVE COMPLETE**
- Migracje `o5p6q7r8s9t0` + `p6q7r8s9t0u1` zastosowane na DS723+ (head=`p6q7r8s9t0u1`)
- API `/health` OK, worker uruchomiony, tabela `purchase_sync_notifications` istnieje
- **Funkcja e-mail wyłączona na produkcji** — brak zmiennych `PURCHASE_SYNC_NOTIFY_*` i `SMTP_*` w `.env.production`

**Uwaga deploy:** Guardian pominął `docker build` i `alembic upgrade` (fałszywie: schema at head). Operator wykonał ręcznie na DS723+: `docker compose build api worker && up -d && alembic upgrade head` — wymagane, bo kod aplikacji jest w obrazie Docker, nie w bind-mount.

---

## 2. Audyt stanu wejściowego (ETAP 1)

| Element | Stan przed GWO-0002 |
|---------|---------------------|
| Model `purchase_sync_notifications` | Istniał (NOTIFY-0001, niezacommitowany) |
| Migracja `o5p6q7r8s9t0` | W repo, **nie uruchomiona** na produkcji (head=`a9b1c2d3e4f5`) |
| `PurchaseSyncEmailNotifier` | Podstawowy enqueue + wysyłka bez backoff |
| Retry SMTP | Brak — natychmiastowe ponowienie przy każdym ticku |
| Wielu odbiorców | Tylko `PURCHASE_SYNC_NOTIFY_EMAIL` |
| Snapshot sesji | Tylko `new_invoice_ids`, brak `gross_sum` / `invoice_count` |
| Współbieżność | `list_processable` bez `FOR UPDATE SKIP LOCKED` |
| Testy NOTIFY-0001 | 10 testów PASS |
| Frontend dist | Wymagał `npm run build` przed deployem |
| Workflow deploy | `guardian ifg deploy run --yes` (zależności: release plan/evaluate) |

**Niespójności:** brak blokujących — kod NOTIFY-0001 był spójny z raportem, ale niezacommitowany.

---

## 3. Zmienione pliki

### Backend
- `app/persistence/models/purchase_sync_notification.py` — pola retry + snapshot
- `alembic/versions/o5p6q7r8s9t0_purchase_sync_notification_queue.py` — kolejka (NOTIFY-0001)
- `alembic/versions/p6q7r8s9t0u1_purchase_sync_notification_hardening.py` — retry + snapshot
- `app/persistence/repositories/purchase_sync_notification_repository.py` — `claim_processable`, backoff
- `app/services/purchase_sync_email_notifier.py` — pełne utwardzenie
- `app/services/purchase_sync_notify_config.py` — parser CSV, slot 08/14, backoff
- `app/integrations/email/smtp_client.py` — wielu odbiorców
- `app/core/config.py` — `RECIPIENTS`, `MAX_ATTEMPTS`
- `app/services/ksef_session_service.py`, `ksef_purchase_sync_audit.py`, `worker/__main__.py`
- `app/services/ksef_transmission_journal_service.py` — metadata journal

### Frontend
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js` — statusy prób e-mail

### Testy / konfiguracja
- `tests/unit/test_purchase_sync_email_notification.py` (26 scenariuszy)
- `tests/unit/test_purchase_sync_notify_config.py`
- `.env.example`

### Raporty
- `docs/reports/2026-07-11_GWO-IFG-NOTIFY-0001_PURCHASE_SESSION_EMAIL.md`
- Ten dokument

---

## 4. Migracje

| Revision | Opis |
|----------|------|
| `o5p6q7r8s9t0` | Tabela `purchase_sync_notifications` |
| `p6q7r8s9t0u1` | `attempt_count`, `next_attempt_at`, `last_attempt_at`, `max_attempts`, `invoice_count`, `gross_sum`, status VARCHAR(20) |

Downgrade `p6q7r8s9t0u1` usuwa nowe kolumny bez kasowania danych bazowych.

---

## 5. Retry i ochrona przed współbieżnością

**Backoff po nieudanej próbie N:**

| Po próbie | Opóźnienie |
|-----------|------------|
| 1 | 5 min |
| 2 | 15 min |
| 3 | 30 min |
| 4 | 60 min |
| 5 | `FAILED_PERMANENT` |

**Statusy:** `PENDING` → `SENT` | `FAILED` (z `next_attempt_at`) | `FAILED_PERMANENT`

**Współbieżność:** `claim_processable()` używa `SELECT … FOR UPDATE SKIP LOCKED` na PostgreSQL; na SQLite (testy) `FOR UPDATE` bez SKIP LOCKED.

**Deduplikacja wysyłki:** `notification_sent_at` + status `SENT` / `FAILED_PERMANENT` wykluczone z claim.

---

## 6. Parsowanie odbiorców

1. `PURCHASE_SYNC_NOTIFY_RECIPIENTS` (CSV, trim, deduplikacja case-insensitive)
2. Fallback: `PURCHASE_SYNC_NOTIFY_EMAIL` (deprecated)
3. Brak poprawnego `@` → brak enqueue

SMTP: jedna wiadomość, nagłówek `To:` z listą odbiorców.

---

## 7. Snapshot sesji (przy enqueue)

| Pole | Źródło |
|------|--------|
| `invoice_count` | `len(saved_invoice_ids)` |
| `gross_sum` | suma `total_gross` faktur purchase z bazy |
| `started_at` / `finished_at` | czasy sesji sync |
| `skipped_duplicates` | audit |
| `errors_count` | audit |
| `new_invoice_ids` | lista UUID (bez zmian) |

Treść maila używa snapshotu dla podsumowania liczbowego; lista kontrahentów z aktualnego stanu bazy (ID z sesji).

---

## 8. Wyniki testów

```bash
python3 -m pytest tests/unit/test_purchase_sync_email_notification.py tests/unit/test_purchase_sync_notify_config.py -q
# 26 passed

python3 -m pytest tests/unit/test_ksef_purchase_sync_audit.py tests/unit/test_ksef_purchase_sync_resume.py -q
# 17 passed
```

Scenariusze NOTIFY-0002: sukces 1. próby, FAILED+attempt_count, respekt `next_attempt_at`, retry po czasie, FAILED_PERMANENT po 5, brak ponowienia SENT/PERMANENT, CSV odbiorców, fallback legacy, snapshot, brak kolejki przy 0/manual/incomplete, sync_status=SUCCESS przy błędzie SMTP.

---

## 9. Commit i push

- **Commit:** `4a71c14` — `feat(ksef): harden purchase sync email notifications`
- **Push:** `production` → `origin/production` (33c8d17..4a71c14)

## 10. Workflow Guardiana

```bash
python3 scripts/guardian.py ifg deploy run --yes --allow-dirty-build
```

- **Workflow ID:** `2026-07-11T212532Z_ifg_deploy_run`
- **Decyzja:** `READY_WITH_OVERRIDE` (dirty tree — niezwiązane pliki poza commitem NOTIFY)
- **Raport:** `docs/guardian/IFG_DEPLOY_RUN_2026_07_11.md`
- **Wykonane:** git pull DS723+, frontend build, rsync dist, compose up, health OK
- **Pominięte (błąd detekcji):** `docker build`, `alembic upgrade` — naprawione ręcznie post-deploy

## 11. Deploy produkcyjny

| Krok | Wynik |
|------|-------|
| git pull DS723+ | `4a71c14` |
| frontend build + rsync | OK |
| docker build api/worker | Wykonane post-deploy (Guardian SKIP) |
| compose up -d | api/worker recreated |
| health `/health` | `{"status":"ok",...}` |

## 12. Migracja produkcyjna

```
a9b1c2d3e4f5 -> o5p6q7r8s9t0 (purchase_sync_notification_queue)
o5p6q7r8s9t0 -> p6q7r8s9t0u1 (purchase_sync_notification_hardening)
```

**Head:** `p6q7r8s9t0u1` — potwierdzone `alembic current` w kontenerze `api`.

## 13. Health produkcyjny

- `ifg-api-1` — Up, healthy
- `ifg-worker-1` — Up
- `ifg-db-1` — Up, healthy
- `purchase_sync_notifications` — 0 rekordów (oczekiwane — brak nowych faktur / notify disabled)
- Monitor KSeF — frontend zaktualizowany (dist rsync)

---

## 14. Konfiguracja operatora (bez sekretów)

| Zmienna | Wymagane do włączenia | Opis |
|---------|----------------------|------|
| `PURCHASE_SYNC_NOTIFY_ENABLED` | tak | `true` aby aktywować |
| `PURCHASE_SYNC_NOTIFY_RECIPIENTS` | tak* | CSV, np. `ops@firma.pl,ksiegowosc@firma.pl` |
| `PURCHASE_SYNC_NOTIFY_EMAIL` | fallback | deprecated |
| `SMTP_HOST` | tak | serwer SMTP |
| `SMTP_FROM` | tak | nadawca |
| `SMTP_USER` / `SMTP_PASSWORD` | wg serwera | tylko w `.env.production` |
| `SMTP_PORT` | nie | domyślnie 587 |
| `SMTP_USE_TLS` | nie | domyślnie true |
| `PURCHASE_SYNC_NOTIFY_MAX_ATTEMPTS` | nie | domyślnie 5 |

\* lub poprawny fallback `PURCHASE_SYNC_NOTIFY_EMAIL`

**Uwaga:** deploy kodu możliwy bez SMTP — funkcja pozostaje wyłączona dopóki `PURCHASE_SYNC_NOTIFY_ENABLED=false` lub brak odbiorców/SMTP.

---

## 15. Ryzyka i dług techniczny

| Priorytet | Opis |
|-----------|------|
| LOW | Brak przycisku ręcznego „Wyślij ponownie” w Monitorze |
| LOW | Slot 08:00/14:00 rozpoznawany heurystycznie z `finished_at` (Europe/Warsaw) |
| MEDIUM | Guardian `build_detector` nie wymusza `docker build` przy zmianach `app/` — wymaga ręcznego rebuild obrazu |
| MEDIUM | Test współbieżności dwóch workerów wymaga PostgreSQL (SKIP LOCKED) |

---

## 16. Rollback plan

1. `git revert <commit>` na `production` + push
2. Guardian deploy run z poprzednim SHA
3. `alembic downgrade p6q6q7r8s9t0` (jeśli nowe kolumny blokują) lub pozostaw kolumny (backward compatible)
4. Przywrócenie `.env.production` z backupu jeśli zmieniano SMTP
5. SQL backup z etapu Guardian backup stage

---

## Decyzje dla ChatGPT

1. Czy po `FAILED_PERMANENT` dodać alert webhook (osobny GWO)?
2. Czy snapshot listy faktur w JSON (kontrahent/numer/kwota) ma być zamrożony w kolejce, czy wystarczy obecny model (liczby w snapshot, lista z DB)?

---

🩷 STATUS KOŃCOWY

✅ Co działa — retry 5 prób z backoff, CSV odbiorców, snapshot, SKIP LOCKED, journal rozszerzony, 26+ testów PASS  
⚠️ Znane problemy — weryfikacja produkcyjna zależy od deployu i konfiguracji SMTP operatora  
❌ Co nie działa — brak naturalnego e-maila bez sesji auto z nowymi fakturami (oczekiwane)
