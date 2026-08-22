# KSEF_STABILIZATION_SPRINT

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Jeden końcowy deploy KSeF na DS723+ przez Guardiana: workflow `2026-08-17T195943Z_ifg_deploy_run`, LIVE COMPLETE, obraz `ifg.git.commit=e5784651e716`.
- Health API (z kontenera, nie z Maca): `status=ok`, `environment=production`.
- Runtime Settings (API i worker): `ksef_auto_sync_enabled=True`, `ksef_auto_sync_cron=0 8,14,20 * * *` (sloty 08:00 / 14:00 / 20:00 Europe/Warsaw).
- Scheduler live: `ksef_purchase_auto_scheduler` `last_executed_slot=2026-08-17T20:00`, `last_success_at=2026-08-17 20:00:01 +02`, `last_attempt_at` aktualizowany co minutę po restarcie workera (dowód: `2026-08-17 22:16:01 +02`).
- Sloty 17.08.2026 wykonane: 08:00, 14:00, 20:00 (`SCHEDULER_SLOT` → `SCHEDULER_ENQUEUE` → `PURCHASE_SYNC_AUTO ok`).
- Monitor KSeF: kolumny `operation_type`, `severity`, `correlation_id`, `metadata_json` obecne; Alembic `p6q7r8s9t0u1` (head) — migracja w tym deployu zbędna.
- Autoryzowany ręczny sync zakupów: `POST /api/v1/ksef/sync/purchases` → `200`, `status=ok`, `ksef_returned=63`, `created=0`, `skipped_existing=63`, `errors=0`.
- Wpisy Monitora po ręcznym sync (22:15 +02): `PURCHASE_SYNC_MANUAL` (`started`/`ok`) + `PURCHASE_METADATA_FETCH` + `PURCHASE_IMPORT_SUMMARY`; `severity` + `correlation_id` + `metadata_json` (`source=manual`).
- Nowy format maila jest w obrazie workera (`Małgosiu`, `(+ N poz.)`, gate `saved <= 0`). Warunek wysyłki bez zmian: 0 faktur = brak maila; ≥1 = jeden mail na sesję **auto**.
- Canonical worker: `ifg-worker-1`, `python -m app.worker`, healthy. Leftover sidecar `ifg-worker-active` usunięty po deployu (ryzyko podwójnego schedulera).

⚠️ ZNANE PROBLEMY
- Nowy format maila nie był weryfikowany sztucznym mailem produkcyjnym. Potwierdzenie treści nastąpi przy pierwszej rzeczywistej sesji auto-sync z ≥1 nową fakturą (kolejny slot 08:00 / 14:00 / 20:00).
- Suite `tests/unit/test_ksef_status_api.py`: 5 faili pre-istniejących (patch `_get_active_db_session` vs `_get_active_online_session`) — poza zakresem sprintu, nie blokuje deployu KSeF.

❌ CO NIE DZIAŁA
- Brak blokujących bramek po walidacji produkcyjnej.

## 1. DEPLOY (2026-08-17)

- Komenda: `python3 scripts/guardian.py ifg deploy run --yes --allow-dirty-build`
- Workflow: `2026-08-17T195943Z_ifg_deploy_run`
- HEAD / label: `e5784651e716` (`feat(ksef): informal purchase-sync email after successful auto session`)
- Rebuild: `docker compose … build api worker` (poprzedni obraz `9b4d187ef83c` ≠ HEAD)
- Alembic: SKIPPED — schema already at head `p6q7r8s9t0u1`
- Compose: recreated `ifg-api-1`, `ifg-worker-1`
- `--allow-dirty-build`: lokalne dirty tree (archiwum docs + Guardian WIP poza image context). Zmiana maila była w commicie `e578465`.

## 2. AUTO-SYNC

| Źródło | Wartość |
|--------|---------|
| `.env.production` | `KSEF_AUTO_SYNC_ENABLED=true`, `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *` |
| `app.core.config.Settings` | aliasy ENV odczytywane w runtime |
| API container | `True` / `0 8,14,20 * * *` / `app_env=production` |
| Worker container | `True` / `0 8,14,20 * * *` |
| DB `ksef_sync_states` | `last_cron=0 8,14,20 * * *`, slot `2026-08-17T20:00` |

Wymagane 08:00 i 14:00 są w cronie. Slot 20:00 pozostaje (nie usuwany).

## 3. MONITOR / MIGRACJE

Tabela `transmissions` (produkcja):

- `operation_type`
- `severity`
- `correlation_id`
- `metadata_json`

Migracje monitora były już na head przed tym deployem. Backup/migracja `a9b1c2d3e4f5` z wcześniejszej fazy sprintu pozostaje w historii.

## 4. MAIL

Implementacja bez zmian w tym kroku (już w `e578465`):

- 0 faktur → brak maila
- ≥1 faktura → nieformalny format (`Małgosiu!`, slot, lista `* sprzedawca | numer | data | kwota – tytuł`)
- wiele pozycji: pierwsza z `invoice_items.name` (FA(3) P_7) + `(+ N poz.)`
- tylko `PURCHASE_SYNC_AUTO` (ręczny sync nie wysyła maila)

Sztuczny mail produkcyjny **nie** był wysyłany.

## 5. WYNIK RĘCZNEJ SYNCHRONIZACJI

Autoryzowany JWT administratora, `POST /api/v1/ksef/sync/purchases` (NIP sprzedawcy z Settings).

| Pole | Wynik |
|------|--------|
| HTTP | 200 |
| status | ok |
| ksef_returned | 63 |
| created | 0 |
| skipped_existing | 63 |
| errors | 0 |
| rate_limited | false |

Monitor (22:15:22–22:15:28 +02):

- `PURCHASE_SYNC_MANUAL` started / RUNNING / `source=manual`
- `PURCHASE_METADATA_FETCH` success / INFO / downloaded=63
- `PURCHASE_IMPORT_SUMMARY` summary / INFO / duplicates=63
- `PURCHASE_SYNC_MANUAL` ok / SUCCESS / `source=manual`

Wszystkie z `correlation_id` i `metadata_json`.

## 6. SCHEDULER PO DEPLOYU

- Worker log: `Worker startuje. poll_interval=5s batch=1` (2026-08-17 22:10:05)
- Tick DB po restarcie: `last_attempt_at=2026-08-17 22:16:01 +02` (idle między slotami — oczekiwane)
- Następny slot: 2026-08-18 08:00 Europe/Warsaw

## 7. OCENA KOŃCOWA

**PRODUCTION_VERIFIED**

Deploy, health, runtime auto-sync, schemat Monitora, ręczny sync i wpisy journala potwierdzone na DS723+. Treść nowego maila czeka na pierwszą realną sesję auto z ≥1 fakturą.

---

## AKCEPTACJA (CHECKLISTA)

- [x] Monitor KSeF działa
- [x] severity działa
- [x] operation_type działa
- [x] correlation_id działa
- [x] metadata_json działa
- [x] auto-sync aktywny (ENV + Settings runtime)
- [x] scheduler aktywny (sloty 08:00 / 14:00 / 20:00 17.08 + tick po deployu)
- [x] ręczny sync działa
- [x] wpisy pojawiają się w Monitorze
- [x] wdrożenie produkcyjne zakończone
- [x] mail: kod w workerze; weryfikacja treści przy następnej sesji auto z ≥1 fakturą

## 10. FORMAT MAILA PO SYNC ZAKUPÓW (2026-08-17)

Zmieniono treść maila po udanej automatycznej sesji synchronizacji zakupów KSeF.
Mechanizm kolejki / SMTP / warunek „tylko gdy saved > 0” **bez zmian**.

### Zasady (bez zmian)
- mail tylko gdy sesja zapisała ≥ 1 nową fakturę
- 0 nowych faktur → brak maila
- jeden mail podsumowujący na sesję

### Nowy układ
1. Powitanie („Małgosiu!”) + godzina slotu (08:00 / 14:00 / 20:00) + liczba zakupów
2. Lista faktur nad separatorem
3. Blok techniczny pod `---`

### Lista faktur
Format: `* sprzedawca | numer | data wystawienia | kwota brutto – tytuł`

Tytuł pozycji: `invoice_items.name` z importu XML FA(3) pole **P_7** (już w modelu, bez nowej architektury).
Wiele pozycji: pierwsza nazwa + `(+ N poz.)`; pełne pozycje zostają w IFG.
Brak pozycji w DB → wpis bez tytułu (bez myślnika).

### Testy
`python3 -m pytest tests/unit/test_purchase_sync_email_notification.py tests/unit/test_purchase_sync_notify_config.py -q`
→ **36 passed**

## A. ROOT CAUSE
Sprint wymagał jednego deployu workera/API z nowym mailem, potwierdzenia auto-sync/Monitora i walidacji na DS723+. Produkcja wcześniej działała na starym workerze; leftover `ifg-worker-active` groził podwójnym schedulerem po recreate compose.

## B. ZMIENIONE PLIKI
- `docs/reports/KSEF_STABILIZATION_SPRINT.md` (ten raport)
- kod maila już w `e578465`: `app/services/purchase_sync_email_notifier.py`, `tests/unit/test_purchase_sync_email_notification.py`
- Guardian / compose IFG **bez** zmian w tym kroku

## C. DEPLOY
Wykonany: Guardian `ifg deploy run` na DS723+. Rebuild API+worker. Alembic skip (head). Sidecar `ifg-worker-active` usunięty.

## D. TESTY
- Mail: 36 passed (lokalnie, przed deployem)
- Ręczny sync prod: HTTP 200, 63 metadane, 0 błędów
- Health prod: `environment=production`

## E. NASTĘPNY KROK
Przy pierwszej sesji auto-sync z `saved >= 1` potwierdzić treść maila (powitanie + lista + `(+ N poz.)`). Nie wysyłać maila testowego.

## TECHNICAL DEBT

- **LOW** — klasyfikacja `PURCHASE_SYNC_AUTO` przy `incremental=true` i włączonym auto-sync, nawet gdy trigger jest z API. Ręczny sync bez `incremental` poprawnie zapisuje `PURCHASE_SYNC_MANUAL`. Świadomie poza zakresem (brak nowych funkcji).

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [x] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/KSEF_STABILIZATION_SPRINT.md`
- `docs/guardian/IFG_DEPLOY_RUN_2026_08_17.md`
- `docs/guardian/PRECHECK_REPORT_2026_08_17.md`
- `docs/guardian/IFG_RELEASE_EVALUATE_2026_08_17.md`
- `docs/guardian/IFG_DOCTOR_2026_08_17.md`
- `docs/guardian/IFG_RELEASE_PLAN_2026_08_17.md`
