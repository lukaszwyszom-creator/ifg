# GWO-IFG-0034 — Post-Deploy Verification (DS723+)

**Data:** 2026-07-07  
**Commit:** `b7ad331` — `feat(ksef): split purchase auth from online session (GWO-IFG-0032/0033)`  
**Środowisko:** DS723+ produkcyjne (`zdalny_admin@ds723:32122`)

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Deploy LIVE przez Guardian `ifg.deploy.run` — **SUCCESS** (9/9 kroków, 0 failed).
- `/health` — OK (`environment=production`).
- Worker uruchomiony bez restart loop (`RestartCount=0`).
- `KSEF_AUTH_TOKEN`, `KSEF_AUTO_SYNC_ENABLED=true`, `KSEF_AUTO_SYNC_CRON=0 8,14 * * *` — potwierdzone w `.env.production`.
- Ręczny sync weryfikacyjny — **done** (14 refs, purchase auth bez sesji online).
- Rekord `ksef_sessions`: `status=auth_active`, `session_reference=NULL`.

### ⚠️ Znane problemy

- Ostatni job schedulera sprzed deployu (`dec20445…`) — **failed** z `Brak aktywnej sesji KSeF` (stary kod); naprawione po deployu.
- Guardian doctor lokalnie: `READY_WITH_WARNINGS` (dirty tree poza commitem GWO, untracked docs).
- Tabela `ksef_transmission_journal` nie istnieje w prod DB — scheduler journal przez serwis może być w innej tabeli; stan schedulera w `ksef_sync_states` OK.

### ❌ Co nie działo się przed deployem

- Auto-sync o 14:00 failował na wymaganiu sesji online — **root cause usunięty** w GWO-IFG-0032.

---

## Decyzja

# **DEPLOY SUCCESS**

---

## ETAP 1 — Pre-deploy

| Kryterium | Wynik |
|-----------|-------|
| Branch | `production` |
| Commit GWO | `b7ad331` (push `origin/production`) |
| Guardian `ksef check` | **GREEN** (exit 0) |
| Guardian `doctor` | **READY_WITH_WARNINGS** (backend committed; inne lokalne zmiany poza scope) |
| `KSEF_AUTH_TOKEN` | ✅ obecny (redacted w logach) |
| `KSEF_AUTO_SYNC_ENABLED` | `true` |
| `KSEF_AUTO_SYNC_CRON` | `0 8,14 * * *` |

**Uwaga:** Working tree lokalnie nadal zawiera niezcommitowane zmiany spoza GWO-IFG-0032/0033 — nie wpływają na deploy (commit i push tylko plików KSeF).

---

## ETAP 2 — Deploy

### Workflow Guardiana

| Workflow | ID | Wynik |
|----------|-----|-------|
| `ifg.release.plan` | `2026-07-07T204817Z_ifg_release_plan` | SUCCESS |
| `ifg.release.evaluate` | `2026-07-07T204822Z_ifg_release_evaluate` | SUCCESS (READY_WITH_WARNINGS) |
| `ifg.deploy.run` (dry-run) | `2026-07-07T204743Z_ifg_deploy_run` | SUCCESS |
| `ifg.deploy.run` (LIVE `--yes`) | `2026-07-07T204817Z_ifg_deploy_run` | **SUCCESS** (~354s) |

Komenda:

```bash
python scripts/guardian.py ifg deploy run --yes --markdown
```

### Wykonane kroki pipeline

1. `git pull origin production` na DS723+ → HEAD `b7ad331`
2. `npm run build` (frontend-react)
3. Artifact gate local + remote — GO
4. rsync `frontend-react/dist/` → DS723+
5. `docker compose build api worker`
6. **Alembic upgrade — SKIPPED** (schema at head, brak nowych migracji — zgodnie z oczekiwaniem)
7. `docker compose up -d`
8. Health check — OK
9. Log verification — OK

### Zmodyfikowane obrazy/kontenery

| Artefakt | Stan po deploy |
|----------|----------------|
| `ifg-api:latest` | przebudowany, recreated |
| `ifg-worker-1` | przebudowany, recreated (`ifg-api:latest`) |
| `ifg-db-1` | bez zmian (healthy) |
| Rollback point | commit `b7ad331`, alembic `a9b1c2d3e4f5 (head)` |

Raport Guardian: `docs/guardian/IFG_DEPLOY_RUN_2026_07_07.md`

---

## ETAP 3 — Smoke test

| Test | Wynik |
|------|-------|
| `GET /health` | `{"status":"ok","environment":"production",...}` |
| Backend API | healthy (compose healthcheck) |
| Worker | `Up`, `RestartCount=0` |
| Frontend | `GET /` → HTTP 302 (SPA routing) |
| Brak restart loop | ✅ worker stabilny >3 min po deploy |

---

## ETAP 4 — Scheduler

### Stan w DB (`ksef_sync_states`)

```json
{
  "last_cron": "0 8,14 * * *",
  "last_executed_slot": "2026-07-07T14:00",
  "last_enqueued_job_id": "dec20445-a4d5-4a0b-9eba-e62456e79f5b"
}
```

| Parametr | Wartość |
|----------|---------|
| Czas weryfikacji (Warsaw) | 2026-07-07 ~22:57 |
| Ostatni slot | 14:00 (dziś) |
| **Następny slot** | **2026-07-08 08:00** |
| Scheduler tick | Worker startuje pętlę (`poll_interval=5s`); slot 22:xx nie jest w CRON → brak enqueue (poprawne) |

### Ręczny sync weryfikacyjny (GWO-IFG-0034)

Job: `0da3bdbe-a476-4b97-a7fd-902799563e2a` — **done**

```json
{
  "saved": 0,
  "received": 14,
  "skipped_existing": 14,
  "rate_limited": false
}
```

**Dowód ścieżki PurchaseAuthService:**

1. `POST /auth/challenge` → 200
2. `POST /auth/ksef-token` → 202
3. `POST /auth/token/redeem` → 200
4. Metadata query → 14 refs
5. Brak błędu sesji online

**DB po sync:**

| nip | status | session_reference | expires_at |
|-----|--------|-------------------|------------|
| 9670402857 | `auth_active` | NULL | 2026-07-07 23:11+02 |

---

## ETAP 5 — Monitoring logów

| Obszar | Wynik |
|--------|-------|
| Scheduler | Worker start bez `SystemExit` (fail-fast OK — token obecny) |
| Worker | `KSEF_ASYNC_SYNC_WORKER_START` → `DONE` |
| PurchaseAuthService | Pełna autoryzacja tokenem ENV → auth_active |
| Traceback | **Brak** |
| Błędy auth | **Brak** (po deployu) |
| Błędy KSeF API | **Brak** |

Poprzedni błąd (pre-deploy job `dec20445…`):

```
Brak aktywnej sesji KSeF dla NIP 9670402857.
```

---

## Ocena ryzyka po deployu

| Ryzyko | Poziom |
|--------|--------|
| Regresja sprzedaży | Niskie (online session bez zmian semantycznych) |
| Auto-sync jutro 08:00 | Niskie (auth_active w DB + refresh path) |
| Worker crash bez tokena | Wyeliminowane (fail-fast + token w ENV) |

---

## A. Root cause (pre-deploy failure)

Slot 14:00 używał starego kodu wymagającego sesji online. Po deployu `ensure_purchase_auth()` działa bez `session_reference`.

## B. Zmienione pliki (deploy)

Commit `b7ad331` — 17 plików GWO-IFG-0032/0033 (serwisy, worker, testy, docs).

## C. Deploy

Wykonano przez Guardian LIVE — patrz ETAP 2.

## D. Testy

- Pre-deploy: 42 testów core KSeF — passed
- Post-deploy: ręczny job produkcyjny — **done** (dowód operacyjny)

## E. Następny krok

- Monitor slot **2026-07-08 08:00** — oczekiwany `SCHEDULER_ENQUEUE` + job `done` bez błędu sesji.
- UI sprzedaży: nadal wymaga „Połącz” (online session) — zamierzone.

---

## Lista wykonanych analiz

1. Git status, branch, commit scope GWO-IFG-0032/0033.
2. Guardian `ksef check` i `doctor` pre-deploy.
3. Guardian `ifg.deploy.run` dry-run i LIVE.
4. Weryfikacja ENV KSeF na DS723+.
5. Smoke `/health`, compose ps, frontend HTTP.
6. Stan schedulera w `ksef_sync_states`.
7. Ręczny enqueue `sync_purchase_invoices` + analiza logów workera.
8. Weryfikacja rekordu `auth_active` w `ksef_sessions`.
9. Worker `RestartCount` i brak traceback.
10. Porównanie pre/post deploy job error (`Brak aktywnej sesji`).

## Lista wykonanych raportów (sesja GWO-IFG-0032 → 0034)

| # | Raport |
|---|--------|
| 1 | `docs/reports/2026-07-07_KSEF_AUTO_SYNC_SESSION_DEPENDENCY_AUDIT.md` |
| 2 | `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_REFACTOR_DESIGN.md` |
| 3 | `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_FINAL_REVIEW.md` |
| 4 | `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_DEPLOY_READY.md` |
| 5 | `docs/guardian/IFG_DEPLOY_RUN_2026_07_07.md` (Guardian deploy) |
| 6 | **`docs/reports/2026-07-07_GWO-IFG-0034_POST_DEPLOY_VERIFICATION.md`** (ten dokument) |

## Lista workflow Guardiana użytych podczas wdrożenia

| Workflow | Cel |
|----------|-----|
| `guardian.py ksef check` | Pre-deploy KSeF gate |
| `guardian.py doctor` | Pre-deploy IFG doctor |
| `ifg.release.plan` | Plan deploy (dependency) |
| `ifg.release.evaluate` | Decyzja READY_WITH_WARNINGS |
| `ifg.deploy.run --dry-run` | Podgląd pipeline |
| `ifg.deploy.run --yes` | **LIVE deploy DS723+** |
