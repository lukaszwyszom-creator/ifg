# GWO-IFG — Multi-recipient email + 20:00 purchase sync session

**Data:** 2026-07-20  
**Repo:** `/Users/lukasz/projekty/ifg_standalone`  
**Branch:** `production`  
**STATUS:** SUCCESS  
**VERDICT:** READY_FOR_NEXT_SESSION  

---

## STATUS

| Gate | Wynik |
|------|-------|
| Lokalny default cron `0 8,14,20 * * *` | PASS |
| Etykiety 08/14/20 (CET + CEST) | PASS |
| CSV recipients (2 adresy) | PASS (count only) |
| Testy objęte zmianą | **53 passed** |
| Pełny `tests/unit/` | 1396 passed / **18 failed** (poza zakresem GWO — pre-existing) |
| Commit feature | `a57a8fd` / rebuild doc `0557c9b` / docs `66ba7ee` |
| Release evaluate | PRODUCTION_BLOCKED (dirty tree) → override `--allow-dirty-build` |
| Deploy check | mismatch 66ba7ee vs 0557c9b → deploy wymagany |
| Backup ENV | `.env.production.bak.gwo-ifg-2000-20260720T112355Z` (prev cron `0 8,14 * * *`) + close `.env.production.bak.gwo-ifg-2000-close-20260720T115917Z` |
| ENV update | PASS — cron 20:00; recipients **count=2** (adresy nie ujawniane) |
| Docker rebuild worker | PASS (wcześniej `2026-07-20T112753Z`; closure deploy: build SKIP — obraz już zawiera kod) |
| Env reload / restart | PASS (`ifg env reload --yes`) |
| Production health | PASS — `environment: production`, Europe/Warsaw |
| Scheduler runtime | PASS — 3 sloty, 1 kontener worker |

**VERDICT:** Produkcja gotowa na najbliższą sesję auto-sync (08:00 / 14:00 / 20:00 Europe/Warsaw).

---

## Commit hash

| SHA | Rola |
|-----|------|
| **`a57a8fd`** | Feature: slot 20:00 + dokumentacja multi-recipient |
| `0557c9b` | Document slots / wymuszenie rebuildu obrazu |
| **`66ba7ee`** | Post-deploy report (aktualny remote HEAD po closure) |

Feature commit do cytowania: **`a57a8fd581f471968bb931ffd767ed45172c2685`**  
Remote HEAD po domknięciu: **`66ba7ee`**

---

## Wyniki testów

```text
# Zakres GWO
53 passed  — scheduler + notify_config + email_notification + smtp_client

# Pełny tests/unit/
1396 passed, 18 failed
```

**18 FAIL poza zakresem** (m.in. `test_domain_invoice`, `test_invoice_api` PDF, numbering, ksef_status, guardian plugins sprint2). Nie dotyczą crona 20:00 ani CSV recipients. Nie blokują tego GWO.

Dowody reguł biznesowych (testy, bez wysyłki produkcyjnej):
- `test_zero_new_invoices_no_enqueue` → brak maila gdy `saved <= 0`
- `test_multiple_recipients_csv` → jeden send, lista `to_addrs`
- `test_same_session_no_second_enqueue` → brak ponownego raportu tej samej sesji (`correlation_id`)
- slot 20:00 CET/CEST w `test_purchase_sync_notify_config.py`

---

## Release evaluate / Deploy check

| Krok | Wynik |
|------|-------|
| `guardian release evaluate` | PRODUCTION_BLOCKED — dirty working tree (Guardian WIP / archiwum docs) |
| Override | `--allow-dirty-build` (świadomy, zalogowany) |
| `guardian deploy check` | PRODUKCJA NIEZGODNA — local `66ba7ee` vs remote `0557c9b` |
| Closure deploy | LIVE COMPLETE — git pull → `66ba7ee`; docker build **SKIP** (brak nowych zmian backend vs origin); compose up OK |
| Feature rebuild (wcześniej) | LIVE COMPLETE `2026-07-20T112753Z` — **docker build EXECUTED** |

---

## Backup i rollback

| Artefakt | Wartość |
|----------|---------|
| Backup przed zmianą crona | `.env.production.bak.gwo-ifg-2000-20260720T112355Z` |
| Poprzedni cron | `KSEF_AUTO_SYNC_CRON=0 8,14 * * *` |
| Backup before closure | `.env.production.bak.gwo-ifg-2000-close-20260720T115917Z` |
| Rollback ENV | przywrócić backup + `guardian ifg env reload --yes` |
| Rollback kodu | `git checkout a57a8fd^` / poprzedni image + Guardian deploy z build |

Rollback **nie był wymagany** — wszystkie gate’y runtime PASS.

---

## ENV produkcyjne (bez adresów)

| Klucz | Stan |
|-------|------|
| `KSEF_AUTO_SYNC_CRON` | `0 8,14,20 * * *` |
| `PURCHASE_SYNC_NOTIFY_RECIPIENTS` | **2** poprawne adresy (CSV, ze spacją po przecinku OK) |
| Sekrety / adresy w raporcie | **nie ujawniane** |

---

## Runtime po wdrożeniu

| Check | Wynik |
|-------|-------|
| Worker containers | **1** (`ifg-worker-1`) — brak równoległych schedulerów |
| TZ | `Europe/Warsaw` |
| Cron | dokładnie `0 8,14,20 * * *` |
| Sloty | hours `(8,14,20)`, minutes `(0,)` |
| Etykiety | 08:00 / 14:00 / 20:00 (CEST + CET) |
| Recipients | count **2**, wszystkie z `@` |
| Health | HTTP 200, production |
| Double job model | bez zmian — `slot_key` + `last_executed_slot` |
| Mail tylko purchase KSeF, `saved > 0` | potwierdzone w kodzie/testach |
| Jeden raport → obu odbiorców | `send_email(to_addrs=list)` |
| Brak re-raportu wcześniejszych sesji | unikalny `correlation_id` enqueue |

**Nie wykonano:** ręcznego sync KSeF, testowego maila do odbiorców.

---

## Zmienione pliki (feature)

- `app/core/config.py`
- `app/services/purchase_sync_notify_config.py`
- `app/services/ksef_transmission_journal_service.py`
- `app/services/purchase_sync_email_notifier.py`
- `tests/unit/test_ksef_auto_sync_scheduler.py`
- `tests/unit/test_purchase_sync_notify_config.py`
- `tests/unit/test_purchase_sync_email_notification.py`
- `tests/unit/test_smtp_client.py`
- `.env.example`
- `docs/architecture/KSEF_SCHEDULER.md`
- `docs/reports/2026-07-20_GWO-IFG_MULTI_RECIPIENT_AND_2000_SYNC_SESSION.md`

---

## Odstępstwa i ryzyka

1. **GDD-0016:** po clean push Guardian często pomija `docker build` — wymagał wcześniej dirty-backend triggera.
2. Closure deploy: build SKIP (obraz już z feature rebuild) — akceptowalne po weryfikacji runtime.
3. `--allow-dirty-build` przez lokalny dirty tree (poza zakresem GWO).
4. 18 FAIL w pełnym `tests/unit/` — debt / pre-existing, nie regresja tego GWO.
5. Brak workflow `ifg env set` — patch ENV przez SSH transport Guardiana + oficjalny `env reload`.

---

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG_MULTI_RECIPIENT_AND_2000_SYNC_SESSION.md`
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`
- `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_20.md`
- `docs/reports/2026-07-20_GWO-GUARDIAN-0079_ENV_RELOAD.md`
