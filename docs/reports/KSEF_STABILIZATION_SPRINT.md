# KSEF_STABILIZATION_SPRINT

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Wdrożenie przez Guardian zostało wykonane ponownie i zakończone sukcesem (`ifg deploy run --yes`, LIVE COMPLETE).
- Runtime backend po restarcie odczytuje:
  - `ksef_auto_sync_enabled=True`
  - `ksef_auto_sync_cron=0 8,14 * * *`
- Migracja `a9b1c2d3e4f5_ksef_monitor_transmissions_unified` została wykonana na produkcji.
- Tabela `transmissions` ma kolumny: `operation_type`, `severity`, `correlation_id`, `metadata_json`.
- Autoryzowany test E2E ręcznej synchronizacji zakupów przeszedł (`200 OK`) i zapisał pełny przebieg w Monitorze KSeF:
  - `SESSION_OPEN`
  - `PURCHASE_SYNC_MANUAL` (`RUNNING` -> `WARNING`)
  - `PURCHASE_METADATA_FETCH`
  - `PURCHASE_INVOICE_FETCH`
  - `PURCHASE_IMPORT_SUMMARY`
  - `SESSION_CLOSE`
- Nowy format maila po auto-sync zakupów: testy jednostkowe **36 passed** (treść + warunek 0 faktur = brak maila). Jeszcze bez deploy workera.

⚠️ ZNANE PROBLEMY
- Scheduler auto-sync (uruchamianie o 08:00 i 14:00) nie ma potwierdzonego aktywnego mechanizmu wykonawczego w aktualnym workerze.
- W logach i kodzie brak dowodu aktywnego joba cyklicznego dla auto-sync; konfiguracja ENV jest gotowa, ale sam mechanizm harmonogramu nie został uruchomiony.

❌ CO NIE DZIAŁA
- Nie potwierdzono automatycznego uruchamiania sync o 08:00 i 14:00 (brak aktywnego scheduler runtime).

## 1. WYKONANE ZMIANY
- Zsynchronizowano na DS723+ aktualną implementację IFG dla Monitora KSeF i auto-sync (backend, worker, API, frontend, migracja Alembic).
- Uzupełniono produkcyjny `.env.production`:
  - `KSEF_AUTO_SYNC_ENABLED=true`
  - `KSEF_AUTO_SYNC_CRON=0 8,14 * * *`
- Wykonano pełny deploy przez Guardiana po synchronizacji kodu.

## 2. MIGRACJE
- Backup DB przed migracją:
  - `backups/pre_ksef_stabilization_20260707_122345.sql`
- Wykonano:
  - `alembic upgrade head` (upgrade `f8a9b0c1d2e3 -> a9b1c2d3e4f5`)
- Potwierdzenie kolumn:
  - `operation_type`
  - `severity`
  - `correlation_id`
  - `metadata_json`

## 3. ZMIANY BACKEND
- Backend runtime po restarcie używa nowego `Settings` z polami auto-sync.
- Endpoint ręcznego sync:
  - `POST /api/v1/ksef/sync/purchases`
  - działa autoryzowanie, zapisuje wpisy do `transmissions`.

## 4. ZMIANY ENV
- `KSEF_AUTO_SYNC_ENABLED=true`
- `KSEF_AUTO_SYNC_CRON=0 8,14 * * *`
- Potwierdzone w:
  - pliku `.env.production`
  - runtime kontenera API (`settings.ksef_auto_sync_enabled`, `settings.ksef_auto_sync_cron`)

## 5. WYNIK TESTU RĘCZNEJ SYNCHRONIZACJI
- Autoryzowany test wykonany jako administrator (token JWT administratora).
- `POST /api/v1/ksef/sync/purchases?nip=9670402857`:
  - wynik: `200 OK`
  - payload: `status=incomplete`, `ksef_returned=69`, `created=2`, `skipped_existing=67`, `errors=0`
- Wpisy w `transmissions` potwierdzone:
  - `SESSION_OPEN`
  - `PURCHASE_SYNC_MANUAL`
  - `PURCHASE_METADATA_FETCH`
  - `PURCHASE_INVOICE_FETCH`
  - `PURCHASE_IMPORT_SUMMARY`
  - `SESSION_CLOSE`

## 6. WYNIK TESTU SCHEDULER
- Konfiguracja scheduler (cron) jest obecna i poprawnie czytana.
- Brak dowodu aktywnego mechanizmu cyklicznego uruchamiania auto-sync w działającym workerze.
- Bezpieczny test pojedynczego scheduler-run nie został wykonany, ponieważ brak jawnego aktywnego entrypointa scheduler w runtime.

## 7. STATUS MONITORA KSEF
- Monitor KSeF działa na produkcji.
- `operation_type`, `severity`, `correlation_id`, `metadata_json` są zapisywane i widoczne operacyjnie.
- Dziennik pokazuje przebieg ręcznej synchronizacji zakupów.

## 8. LISTA POZOSTAŁYCH PROBLEMÓW
- Do domknięcia pozostało uruchomienie i potwierdzenie automatycznego scheduler-run o 08:00 i 14:00.

## 9. OCENA KOŃCOWA
**WYMAGA POPRAWEK**

Powód: wszystkie elementy Monitora KSeF i ręcznej synchronizacji działają, ale brak potwierdzenia aktywnego scheduler-run auto-sync w produkcji.

---

## AKCEPTACJA (CHECKLISTA)

- [x] Monitor KSeF działa
- [x] severity działa
- [x] operation_type działa
- [x] correlation_id działa
- [x] metadata_json działa
- [x] auto-sync aktywny (konfiguracja + runtime settings)
- [ ] scheduler aktywny (08:00 / 14:00 potwierdzone wykonaniem)
- [x] ręczny sync działa
- [x] wpisy pojawiają się w Monitorze
- [ ] wdrożenie produkcyjne zakończone (warunkowo: brak potwierdzonego scheduler-run)
- [x] mail po auto-sync: nowy format (lokalne testy PASS; wymaga deploy worker)

---

## 10. FORMAT MAILA PO SYNC ZAKUPÓW (2026-08-17)

Zmieniono treść maila po udanej automatycznej sesji synchronizacji zakupów KSeF.
Mechanizm kolejki / SMTP / warunek „tylko gdy saved > 0” **bez zmian**.

### Zasady (bez zmian)
- mail tylko gdy sesja zapisała ≥ 1 nową fakturę
- 0 nowych faktur → brak maila
- jeden mail podsumowujący na sesję

### Nowy układ
1. Powitanie („Małgosiu!”) + godzina slotu (08:00 / 14:00) + liczba zakupów
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

Pokrycie: 0 faktur (brak maila), 1 faktura, kilka faktur na liście, suma brutto, slot 08:00 / 14:00, dane techniczne pod separatorem, kompresja wielu pozycji.

### Pliki
- `app/services/purchase_sync_email_notifier.py`
- `tests/unit/test_purchase_sync_email_notification.py`

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## A. Root cause
Dotychczasowy mail był formalnym blokiem technicznym bez powitania i bez tytułu pozycji.

## B. Zmienione pliki
- `app/services/purchase_sync_email_notifier.py`
- `tests/unit/test_purchase_sync_email_notification.py`
- `docs/reports/KSEF_STABILIZATION_SPRINT.md`

## C. Deploy
Wymagany rebuild **worker** (notifier działa w workerze). Guardian / IFG compose / SMTP poza zakresem tej zmiany.

## D. Testy
36 passed (`test_purchase_sync_email_notification.py` + `test_purchase_sync_notify_config.py`).

## E. Następny krok
Deploy workera na DS723+ i weryfikacja na kolejnej sesji auto-sync z ≥ 1 nową fakturą.
