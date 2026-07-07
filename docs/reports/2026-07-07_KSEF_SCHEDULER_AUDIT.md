# 2026-07-07_KSEF_SCHEDULER_AUDIT

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Ręczny sync zakupów działa przez endpoint `POST /api/v1/ksef/sync/purchases` (autoryzowany test zwrócił `200`).
- Worker przetwarza kolejkę `background_jobs` dla typu `sync_purchase_invoices` (mechanizm asynchronicznego job runnera działa).
- Runtime backend czyta konfigurację:
  - `ksef_auto_sync_enabled=True`
  - `ksef_auto_sync_cron=0 8,14 * * *`

⚠️ ZNANE PROBLEMY
- W kodzie IFG nie ma aktywnego mechanizmu harmonogramu (scheduler) uruchamiającego auto-sync o godzinach 08:00 i 14:00.
- `KSEF_AUTO_SYNC_ENABLED` i `KSEF_AUTO_SYNC_CRON` są obecnie tylko flagami konfiguracyjnymi/warunkowymi w logice syncu, ale bez procesu planującego wywołanie.

❌ CO NIE DZIAŁA
- Auto-sync cykliczny (scheduler-run) nie uruchamia się samoczynnie.

---

## 1) Jaki mechanizm scheduler został zaprojektowany

Nie znaleziono implementacji mechanizmu schedulerowego typu:
- APScheduler,
- Celery Beat,
- system cron wywoływany z aplikacji,
- `asyncio` periodic tasks,
- FastAPI startup task scheduler.

W repo istnieje tylko:
- manualny endpoint syncu,
- asynchroniczny worker kolejki `background_jobs`,
- logika wyboru `PURCHASE_SYNC_AUTO` vs `PURCHASE_SYNC_MANUAL` w serwisie.

To oznacza: **zaprojektowano flagi auto-sync i semantykę zdarzeń, ale nie zaprojektowano/nie wdrożono aktywnego schedulera wykonawczego**.

---

## 2) Gdzie znajduje się entrypoint scheduler

**Nie istnieje entrypoint scheduler.**

Przeszukanie kodu nie wykazało modułu ani funkcji inicjalizującej harmonogram.

---

## 3) W którym miejscu aplikacji scheduler powinien być uruchamiany

Naturalne miejsca (architektonicznie), ale obecnie niewykorzystane:
- `app/main.py` (lifespan/startup API),
- `app/worker/__main__.py` (pętla workera).

Aktualnie żadne z tych miejsc nie inicjalizuje cron/scheduler jobs.

---

## 4) Czy scheduler jest obecnie inicjalizowany podczas startu API lub workera

**Nie.**

Dowody:
- `app/main.py` `application_lifespan` uruchamia logging/bootstrap admin i kończy `yield` — brak rejestracji jobów cyklicznych.
- `app/worker/__main__.py` zawiera tylko pętlę pollingową kolejki (`pending` jobs), brak cron triggerów i brak periodic enqueue auto-sync.
- Logi runtime API/worker nie zawierają wpisów typu scheduler start / job registered / cron tick.

---

## 5) Jeżeli nie — dlaczego i od którego commita przestał być uruchamiany

### Dlaczego nie działa
- Brak implementacji procesu harmonogramu, który enqueue’owałby `sync_purchase_invoices` o zadanych godzinach.
- Flagi `ksef_auto_sync_enabled`/`ksef_auto_sync_cron` nie są podpięte do żadnego rejestratora jobów.

### Od którego commita
- Analiza historii wskazuje, że scheduler **nie był uruchamiany nigdy** w aktualnej linii rozwoju.
- W najwcześniejszym commicie dodającym async sync job (`082e94f`) plik `app/worker/__main__.py` nie zawiera żadnych prymitywów scheduler/cron.
- Dodatkowo linie z `ksef_auto_sync_enabled` i `ksef_auto_sync_cron` są obecnie oznaczone przez `git blame` jako `Not Committed Yet` (lokalne zmiany robocze), więc nie mają jeszcze commit-ID bazowego.

Wniosek: nie da się wskazać „commita, od którego przestał działać”, bo nie ma śladu, żeby był uruchamiany wcześniej.

---

## 6) Jeżeli tak — dowody z logów/runtime

Nie dotyczy (scheduler nie jest inicjalizowany).

---

## 7) Czy job auto-sync jest faktycznie rejestrowany

**Nie jako job cykliczny.**

Rejestrowane są wyłącznie joby:
- ręcznie z endpointu,
- przez istniejącą logikę async flow (kolejka).

Brak automatycznego rejestrowania joba o 08:00/14:00.

---

## 8) Czy istnieje możliwość ręcznego wywołania scheduler-run bez czekania do 08:00

**Nie istnieje scheduler-run**, ale istnieje ręczny odpowiednik operacyjny:
- autoryzowane `POST /api/v1/ksef/sync/purchases`.

To jest ręczne uruchomienie syncu, nie uruchomienie schedulera.

---

## 9) Odpowiedź końcowa (wymagana)

**Czy scheduler istnieje, gdzie jest oraz dlaczego nie wykonuje auto-sync?**

- Scheduler **nie istnieje** jako aktywny mechanizm runtime.
- Nie ma lokalizacji entrypointu, bo nie ma modułu inicjalizującego harmonogram.
- Auto-sync nie wykonuje się automatycznie, bo brak procesu rejestrującego i odpalającego joby wg `KSEF_AUTO_SYNC_CRON`; istnieją tylko flagi konfiguracyjne i ręczny/async flow.

