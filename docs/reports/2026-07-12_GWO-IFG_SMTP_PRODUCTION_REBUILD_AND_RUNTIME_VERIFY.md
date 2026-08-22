# GWO-IFG — SMTP Production Rebuild, Deploy i Weryfikacja Runtime

**Data:** 2026-07-12  
**Ticket:** GWO-IFG SMTP Production Rebuild  
**Repo lokalne:** `~/projekty/ifg_standalone`  
**Produkcja:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`  
**Branch:** `production`  
**Status końcowy:** **SUCCESS**

---

🩷 STATUS KOŃCOWY

| Obszar | Status |
|--------|--------|
| Analiza chronologii | ✅ Werdykt A |
| Testy pre-deploy | ✅ 90 passed |
| Preflight Guardian | ✅ Backend/Worker Build YES |
| Deploy z docker build | ✅ LIVE COMPLETE |
| Runtime `parse_smtp_from` (api) | ✅ True |
| Runtime `parse_smtp_from` (worker) | ✅ True |
| Health produkcji | ✅ HTTP 200, `environment: production` |
| SMTP check (REMOTE) | ✅ PASS |
| SMTP test (REMOTE) | ✅ PASS — mail wysłany |
| Retry powiadomienia purchase sync | ✅ SENT (jednorazowy retry aplikacyjny) |
| GDD host–container parity | ✅ Zarejestrowane (GDD-0016) |

✅ Co działa
- Obraz `ifg-api:latest` przebudowany i współdzielony przez `api` + `worker`
- Envelope sender produkcyjny: `ds723@ikonastudio.pl`
- Odbiorca testowy: `lukasz@ikonastudio.pl`
- Brak błędu `554 5.1.0 <IFG>` po rebuild
- Nieudane powiadomienie `7c652ac6-803d-4eba-aa32-323beb97a5b0` ponowione i wysłane
- Journal KSeF: najnowszy wpis `PURCHASE_SYNC_EMAIL` → `email_sent`

⚠️ Znane problemy
- Deploy wymagał `--allow-dirty-build` (lokalny dirty tree — Guardian WIP, raporty, archiwum docs)
- `smtp_client.py` nie był w trigger files planu (już zacommitowany); rebuild wymuszony przez dirty backend files
- Brak dedykowanego workflow Guardiana do retry `FAILED_PERMANENT` — użyto jednorazowego skryptu ORM w workerze
- Pole journal `attempt_no` nadal `1` dla wpisu `email_sent` (fix attempt_no nie był na remote — tylko lokalnie uncommitted)
- Post-deploy `ifg doctor` nadal BLOCKED lokalnie (dirty tree Mac mini) — nie blokuje produkcji

❌ Co nie działa
- Brak

---

## ETAP 1 — Analiza chronologii

### SHA i daty

| Artefakt | SHA / data | Uwagi |
|----------|------------|-------|
| Fix SMTP `parse_smtp_from()` | **`1f05f86`** — 2026-07-12 00:56:17 +0200 | `fix(notify): parse SMTP_FROM display name for envelope sender` |
| Raport post-deploy NOTIFY-0003 | **`3640f65`** — 2026-07-12 00:58:15 +0200 | docs only |
| GWO-GUARDIAN-0076 | **Brak commita na `production`** | Kod i raport istnieją wyłącznie lokalnie (untracked/modified); `git log production -- scripts/ifg_guardian/plugins/ifg/deploy_decision/` → pusty |
| NOTIFY-0003 deploy | 2026-07-12 ~00:58 | `ifg deploy run --yes --allow-dirty-build`; `docker build` **SKIP** |
| Obraz sprzed rebuildu | `sha256:f426134b…` — utworzony **2026-07-11T23:28** | sprzed commita `1f05f86` |
| Obraz po rebuildu | `sha256:49d8619c…` — utworzony **2026-07-12T22:00** | po deploy GWO |

### Werdykt chronologii

## **A. EXPECTED HISTORICAL FAILURE**

Deploy SMTP (NOTIFY-0003) odbył się **przed** wdrożeniem naprawy GWO-GUARDIAN-0076 na branch `production`:

1. **GWO-0076 nie było zacommitowane** na `production` w momencie deployu NOTIFY-0003 ani później (do czasu tego GWO).
2. NOTIFY-0003 deploy używał **starego silnika decyzji** (bez `deploy_decision/git_scope.py` na remote).
3. Po `git push` + `git pull` diff `origin/production...HEAD` był **pusty** dla `smtp_client.py` — plan nie wymusił rebuildu mimo nowego commita na hoście.
4. Architektura produkcyjna: kod w **obrazie Docker**, nie bind-mount → `env reload` / `compose up` bez builda zostawiło stary kod w kontenerze.

**Nie jest to wariant B (GUARDIAN REGRESSION)** — GWO-0076 nie było obecne w kodzie Guardiana na produkcji podczas NOTIFY-0003 deploy.

---

## ETAP 2 — Preflight

### Komendy

```bash
python3 scripts/guardian.py ifg doctor          # BLOCKED (dirty tree lokalnie)
python3 scripts/guardian.py ifg release plan    # Backend YES, Worker YES
python3 scripts/guardian.py release evaluate    # PRODUCTION_BLOCKED bez override
```

### Decyzje build / migration

| Decyzja | Wynik |
|---------|-------|
| Backend Build | **YES** (HIGH) |
| Worker Build | **YES** (HIGH) — współdzielony obraz `ifg-api:latest` |
| Migration Required | **NO** — remote `p6q7r8s9t0u1` = local HEAD |
| Frontend Build | NO |
| Compose Restart | YES |

### Trigger files (release plan)

- `app/services/ksef_transmission_journal_service.py` (dirty lokalnie)
- `app/services/purchase_sync_email_notifier.py` (dirty lokalnie)

Uwaga: `app/integrations/email/smtp_client.py` już na `production` (`1f05f86`) — nie w trigger files, ale **rebuild obrazu** i tak wciąga ten plik z repo DS723+.

### Compose — wspólny obraz

Z `docker/docker-compose.prod.yml`:

- `api.image: ifg-api:latest`
- `worker.image: ifg-api:latest`
- Pipeline Guardiana: **jeden krok** `docker compose build api worker` (nie dwa niezależne obrazy)

### Override

| Flaga | Zastosowanie | Uzasadnienie |
|-------|--------------|--------------|
| `--allow-dirty-build` | **TAK** | Dirty tree na Mac mini (Guardian WIP, raporty, archiwum docs); deploy remote używa `git pull` — **nie** lokalnych uncommitted zmian aplikacji |

---

## ETAP 3 — Deploy

```bash
python3 scripts/guardian.py ifg deploy run --yes --allow-dirty-build
```

**Wynik:** LIVE COMPLETE (197 s)  
**Workflow:** `2026-07-12T195753Z_ifg_deploy_run`  
**Release decision:** `READY_WITH_OVERRIDE`

### Wykonane kroki

| # | Krok | Status |
|---|------|--------|
| 1 | git pull origin production | EXECUTED → remote `3640f65` |
| 2 | frontend build | EXECUTED |
| 3 | artifact verify local | EXECUTED |
| 4 | dist sync | EXECUTED |
| 5 | artifact verify remote | EXECUTED |
| 6 | **docker build api worker** | **EXECUTED** |
| 7 | alembic upgrade | SKIP (schema at head) |
| 8 | compose up -d | EXECUTED (api + worker recreated) |
| 9 | health check | EXECUTED |
| 10 | log verification | EXECUTED |

Rollback point zapisany: commit `3640f65`, alembic `p6q7r8s9t0u1`.

---

## ETAP 4 — Weryfikacja runtime

### Host DS723+

| Check | Wynik |
|-------|-------|
| git HEAD | `3640f65` |
| `parse_smtp_from` w pliku hosta | **2 wystąpienia** (obecny) |

### Obrazy i kontenery

| | Przed | Po |
|---|-------|-----|
| Image ID | `sha256:f426134b9d1bf76b4508f4917d77bde0ba15ffbc71ea90c257ddae70f38873aa` | `sha256:49d8619c4ac4e606d818f75e9675fa7d484cd5d30dcdfc2377adb9fd5cc47e49` |
| Utworzony | 2026-07-11T23:28 | 2026-07-12T22:00 |
| api container image | stary | `sha256:49d8619c…` |
| worker container image | stary | `sha256:49d8619c…` (ten sam) |

### Kod w kontenerach

```
api:    parse_smtp_from=True, from_addr=envelope_from=True
worker: parse_smtp_from=True, from_addr=envelope_from=True
```

### Health

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw"}
```

### Logi startowe

Brak Traceback, import error ani SMTP configuration error w ostatnich 30 liniach api/worker.

---

## ETAP 5 — Test SMTP

### `ifg smtp check` (REMOTE)

| Pole | Wynik |
|------|-------|
| Environment | REMOTE |
| Env source | DS723+ `.env.production` |
| DNS / TCP / STARTTLS / AUTH | PASS |
| Envelope sender | `ds723@ikonastudio.pl` (masked w raporcie) |
| Recipient | `lukasz@ikonastudio.pl` |

### `ifg smtp test --yes` (REMOTE)

| Pole | Wynik |
|------|-------|
| Status | **PASS** |
| Sent | **True** |
| Subject | IFG SMTP Test |
| Błąd `<IFG>` | **Brak** |

---

## ETAP 6 — Powiadomienie purchase sync

### Stan przed retry

| Pole | Wartość |
|------|---------|
| ID | `7c652ac6-803d-4eba-aa32-323beb97a5b0` |
| Status | `FAILED_PERMANENT` |
| attempt_count | 5 / 5 |
| last_error | `554 5.1.0 <IFG>: Sender address rejected` |

Naturalny backoff **nie** ponowi — status terminalny `FAILED_PERMANENT`.

### Retry (mechanizm aplikacyjny)

Brak dedykowanego Guardian workflow / API endpoint. Wykonano **jednorazowy retry** przez worker z użyciem ORM + `PurchaseSyncEmailNotifier.process_pending()`:

1. Reset rekordu: `FAILED_PERMANENT` → `FAILED`, `attempt_count=4`, `next_attempt_at=now`
2. `process_pending()` → wysyłka z nowym kodem SMTP

### Stan po retry

| Pole | Wartość |
|------|---------|
| Status | **SENT** |
| attempt_count | 5 |
| notification_sent_at | `2026-07-12 20:02:23 UTC` |

### Journal KSeF (najnowsze `PURCHASE_SYNC_EMAIL`)

| status | attempt_no | metadata attempt | opis |
|--------|------------|------------------|------|
| `email_sent` | 1 | 5 | Powiadomienie e-mail wysłane. |

**Capability gap:** brak formalnego `guardian ifg notify retry` — proponowany minimalny kolejny GWO: **GWO-IFG-NOTIFY-0004** (admin retry dla `FAILED_PERMANENT` przez workflow Guardiana, bez raw SQL).

---

## ETAP 7 — Technical Debt / GDD

Zarejestrowano **GDD-0016 — HOST–CONTAINER CODE PARITY GATE** w `docs/guardian/deferred_decisions.json`.

Zakres przyszłej funkcji:
- Porównanie host git SHA vs image build SHA vs running container image ID
- Preferowany mechanizm: label/metadata w obrazie z commit SHA
- Mismatch → BLOCKED
- Obowiązkowe dla workerów współdzielących obraz z API

**Nie zaimplementowano** w tym GWO (zgodnie z zakresem).

---

## A. Root cause (podsumowanie)

Produkcja miała aktualny kod na **hoście** (`1f05f86`), ale **stary kod w obrazie Docker** z 2026-07-11. NOTIFY-0003 deploy pominął `docker build` przed naprawą GWO-0076 na branchu `production`.

---

## B. Zmienione pliki (ten GWO)

| Plik | Zmiana |
|------|--------|
| `docs/guardian/deferred_decisions.json` | GDD-0016 host–container parity |
| `docs/reports/2026-07-12_GWO-IFG_SMTP_PRODUCTION_REBUILD_AND_RUNTIME_VERIFY.md` | ten raport |
| `docs/guardian/IFG_DOCTOR_2026_07_12.md` | wygenerowany przez Guardiana |
| `docs/guardian/IFG_RELEASE_PLAN_2026_07_12.md` | wygenerowany przez Guardiana |
| `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_12.md` | wygenerowany przez Guardiana |
| `docs/guardian/IFG_DEPLOY_RUN_2026_07_12.md` | wygenerowany przez Guardiana |
| `docs/guardian/IFG_SMTP_CHECK_2026_07_12.md` | wygenerowany przez Guardiana |
| `docs/guardian/IFG_SMTP_TEST_2026_07_12.md` | wygenerowany przez Guardiana |

Kod aplikacji na produkcji zaktualizowany przez **docker build** z repo `3640f65` (zawiera `1f05f86`).

---

## C. Testy

### Pre-deploy

```bash
python3 -m pytest \
  tests/unit/test_smtp_client.py \
  tests/unit/test_purchase_sync_email_notification.py \
  tests/unit/test_guardian_smtp_workflow.py \
  tests/unit/test_guardian_deploy_decision_engine.py \
  tests/unit/test_guardian_ifg_release_plan_workflow.py \
  tests/unit/test_guardian_ifg_deploy_run_workflow.py -q
```

**Wynik:** 90 passed

### Post-deploy

- Guardian doctor (remote health) — PASS `/health`
- Guardian release evaluate — PRODUCTION_BLOCKED lokalnie (dirty tree, oczekiwane)
- SMTP check — PASS
- SMTP test — PASS
- Runtime probe api/worker — PASS
- Log verification — PASS

---

## D. Plan rollbacku (jeśli potrzebny)

1. Na DS723+: `git checkout f426134b-era-commit` lub rebuild ze starego image ID `sha256:f426134b…` jeśli zachowany
2. `docker compose -f docker/docker-compose.prod.yml build api worker`
3. `docker compose -f docker/docker-compose.prod.yml up -d api worker`
4. Weryfikacja `/health`

Rollback point z deploy run: **`3640f65`**.

---

## Decyzje dla ChatGPT

1. Czy zacommitować GWO-GUARDIAN-0076 na `production` przed kolejnym deployem, aby uniknąć powtórki scenariusza „committed diff empty → no build”?
2. Czy dodać GWO-IFG-NOTIFY-0004 (Guardian admin retry dla `FAILED_PERMANENT`) jako priorytet MEDIUM?

---

## Wygenerowane raporty

- `docs/reports/2026-07-12_GWO-IFG_SMTP_PRODUCTION_REBUILD_AND_RUNTIME_VERIFY.md` (ten dokument)
- `docs/reports/2026-07-12_GWO-IFG_SMTP_ENVELOPE_SENDER_FIX.md` (analiza poprzednia)
- `docs/guardian/IFG_DOCTOR_2026_07_12.md`
- `docs/guardian/IFG_RELEASE_PLAN_2026_07_12.md`
- `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_12.md`
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_12.md`
- `docs/guardian/IFG_SMTP_CHECK_2026_07_12.md`
- `docs/guardian/IFG_SMTP_TEST_2026_07_12.md`

---

## Technical Debt

**HIGH — GDD-0016 Host–Container Code Parity Gate**  
Zarejestrowane; brak automatycznej weryfikacji po deploy.

**MEDIUM — Brak workflow retry `FAILED_PERMANENT`**  
Retry wykonany ad-hoc przez ORM w workerze; wymaga formalnego GWO.

**LOW — Journal `attempt_no` vs metadata `attempt`**  
Fix lokalny uncommitted; produkcyjny journal nadal pokazuje `attempt_no=1` przy `metadata.attempt=5`.
