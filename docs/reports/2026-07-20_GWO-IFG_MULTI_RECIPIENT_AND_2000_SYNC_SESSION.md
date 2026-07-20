# GWO-IFG — Multi-recipient email reporting and 20:00 purchase sync session

**Data:** 2026-07-20  
**Repo:** `~/projekty/ifg_standalone`  
**Branch:** `production`  
**Status końcowy:** **SUCCESS**

---

🩷 STATUS KOŃCOWY

| Obszar | Status |
|--------|--------|
| Audyt implementacji | ✅ |
| Sesja 20:00 w kodzie (default cron + slot label) | ✅ |
| Multi-recipient (CSV) | ✅ 2 odbiorców na produkcji |
| Testy jednostkowe | ✅ 53 passed |
| Commit + push | ✅ `a57a8fd` + `0557c9b` |
| Backup `.env.production` | ✅ `.env.production.bak.gwo-ifg-2000-20260720T112355Z` |
| ENV produkcyjne | ✅ cron + recipients |
| Guardian deploy + docker build | ✅ LIVE COMPLETE (`2026-07-20T112753Z_ifg_deploy_run`) |
| Env reload | ✅ `ifg env reload --yes` |
| Health produkcji | ✅ `environment: production`, Europe/Warsaw |
| Runtime worker: 3 sloty + etykiety 08/14/20 | ✅ |

✅ Co działa
- `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *` w kontenerze worker/api
- `TZ=Europe/Warsaw`
- Parser cron → godziny `(8, 14, 20)`, minuta `(0,)` — dokładnie trzy sloty
- `parse_notify_recipients` → **2** odbiorców
- Etykiety sesji w kodzie: `08:00` / `14:00` / `20:00`
- Worker i API healthy po rebuild

⚠️ Znane problemy
- Pierwszy `ifg deploy run` po pushu **pominął docker build** (diff vs `origin/production` pusty) — wymagał drugiego deployu z dirty backend triggerem (GDD-0016 parity)
- Override `--allow-dirty-build` (lokalny dirty tree Guardiana / archiwum docs)
- Brak dedykowanego workflow `ifg env set` — ENV zaktualizowano przez SSH transport Guardiana (`DS723Config`) + backup, potem oficjalny `ifg env reload`

❌ Co nie działa
- Brak

---

## Commit

| SHA | Opis |
|-----|------|
| `a57a8fd` | feat(ksef): add 20:00 auto-sync slot and multi-recipient notify docs |
| `0557c9b` | chore(ksef): document auto-sync daily slots for image rebuild |

**Produkcja HEAD:** `0557c9b`

---

## Deploy (Guardian)

1. `release evaluate` → PRODUCTION_BLOCKED (dirty tree) → override `--allow-dirty-build`
2. `deploy check` → commit mismatch (przed deployem)
3. Backup ENV: `.env.production.bak.gwo-ifg-2000-20260720T112355Z`
4. ENV:
   - `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *`
   - `PURCHASE_SYNC_NOTIFY_RECIPIENTS` = CSV (2 adresy)
5. `ifg deploy run --yes --allow-dirty-build` — **docker build EXECUTED**, api+worker recreated
6. `ifg env reload --yes`
7. `prod health` → PRODUCTION_RUNNING

Workflow deploy: `2026-07-20T112753Z_ifg_deploy_run`

---

## Weryfikacja produkcyjna (bez sztucznego maila)

| Check | Wynik |
|-------|-------|
| Cron w workerze | `'0 8,14,20 * * *'` |
| TZ | `Europe/Warsaw` |
| Trzy sloty | hours `(8, 14, 20)`, minutes `(0,)` |
| Odbiorcy | count **2** (zanonimizowane) |
| Slot labels | 08:00 / 14:00 / 20:00 |
| Kod `hour == 20` w kontenerze | True |
| Health | HTTP 200, production, Europe/Warsaw |
| Double-job model | bez zmian — jeden `slot_key` / `last_executed_slot` |

---

## A. Root cause / decyzja

Trzecia sesja = rozszerzenie wspólnego crona workera. Multi-recipient = istniejący CSV. Deploy wymagał wymuszenia rebuildu obrazu (parity host↔container).

## B. Zmienione pliki (kod)

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

## C. Deploy

SUCCESS — rebuild + ENV + health.

## D. Testy

53 passed (przed deployem).

## E. Następny krok

Obserwacja naturalnej sesji 20:00 Europe/Warsaw (bez wymuszania syncu).

---

## Technical Debt

**HIGH — GDD-0016:** po pushu clean `origin/production...HEAD` Guardian pomija `docker build` mimo że obraz produkcyjny jest stary.

**MEDIUM:** brak `guardian ifg env set` — aktualizacja kluczy ENV poza `env reload`.

---

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG_MULTI_RECIPIENT_AND_2000_SYNC_SESSION.md` (ten dokument)
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`
- `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_20.md`
- `docs/reports/2026-07-20_GWO-GUARDIAN-0079_ENV_RELOAD.md`
