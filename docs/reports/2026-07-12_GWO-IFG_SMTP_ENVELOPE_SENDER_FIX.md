# GWO-IFG — Diagnostyka i naprawa nadawcy powiadomień Purchase Sync

**Data:** 2026-07-12  
**Ticket:** GWO-IFG SMTP Envelope Sender Fix  
**Repo:** `~/projekty/ifg_standalone`  
**Produkcja:** DS723+ (`ifg` compose project)  
**Status końcowy:** **PARTIAL** — root cause potwierdzony, fix w repo i testy PASS; produkcja wymaga rebuild obrazu Docker (deploy nie wykonany)

---

🩷 STATUS KOŃCOWY

| Obszar | Status |
|--------|--------|
| Diagnostyka root cause | ✅ Zakończona |
| Porównanie ścieżek test vs produkcja | ✅ Zakończone |
| Fix kodu (`parse_smtp_from`) | ✅ W repo (`1f05f86`) |
| Testy jednostkowe SMTP + notifier | ✅ 52 PASS (dedykowany zestaw) |
| Testy regresyjne transmission | ✅ 97 PASS |
| Worker produkcyjny — nowy kod | ❌ **Brak** (`parse_smtp_from=False`) |
| API produkcyjne — nowy kod | ❌ **Brak** (`parse_smtp_from=False`) |
| Guardian SMTP test (Mac mini) | ✅ PASS (lokalny Python, nowy kod) |
| Deploy z `docker build` | ⏸️ **Nie wykonany** (wymaga potwierdzenia operatora) |

✅ Co działa
- Jedna ścieżka wysyłki: `send_email()` w `app/integrations/email/smtp_client.py`
- Guardian `ifg smtp test` i `purchase_sync_notify` korzystają z tego samego adaptera (lokalnie)
- `parse_smtp_from()` poprawnie ustawia envelope `ds723@ikonastudio.pl` i nagłówek `"IFG [DS 723+]" <ds723@ikonastudio.pl>`
- `PURCHASE_SYNC_NOTIFY_RECIPIENTS` trafia wyłącznie do `to_addrs` — brak zamiany z senderem w kodzie
- Testy regresyjne wykrywające zamianę sender/recipient — dodane i PASS
- Poprawka niskiego ryzyka: pole journal `attempt_no` dla zdarzeń e-mail (spójność z metadata `attempt`)

⚠️ Znane problemy
- Produkcja: obraz `ifg-api:latest` nie został przebudowany po `1f05f86` — kontenery `api` i `worker` nadal mają stary `smtp_client.py`
- Raport NOTIFY-0003 błędnie zakładał „bind-mount kodu” — worker montuje tylko `.env.production`, nie źródła aplikacji
- Pełny `pytest tests/unit/` — 1 niepowiązany FAIL (`test_domain_invoice.py`, regex `number_local`) — poza zakresem tego GWO

❌ Co nie działa
- Automatyczne powiadomienie `purchase_sync_notify` na produkcji — worker wysyła ze **starym** envelope senderem (`IFG`), Zenbox odrzuca: `554 5.1.0 <IFG>: Sender address rejected`

---

## A. Root cause

### 1. Główna przyczyna (produkcja)

**Fix NOTIFY-0003 (`1f05f86`) nigdy nie trafił do kontenerów `api`/`worker`.**

Architektura produkcyjna (`docker/docker-compose.prod.yml`):

| Serwis | Obraz | Bind-mount kodu | Bind-mount env |
|--------|-------|-----------------|----------------|
| `api` | `ifg-api:latest` | ❌ tylko `frontend-react/dist` | ✅ `.env.production` |
| `worker` | `ifg-api:latest` | ❌ brak | ✅ `.env.production` |

Deploy NOTIFY-0003 wykonał `git pull` + `compose up` + `env reload`, ale **pominął `docker build`** (backend „no changes” względem `origin/production` w momencie planu). Kod na dysku DS723+ jest aktualny, ale **Python w kontenerze pochodzi z ostatniego buildu obrazu** sprzed fixu.

**Weryfikacja na DS723+ (2026-07-12):**

```
api:    parse_smtp_from=False
worker: parse_smtp_from=False
```

### 2. Mechanizm błędu envelope sendera (stary kod)

Stary `smtp_client.py` (przed `1f05f86`):

```python
message["From"] = config.from_addr  # surowe SMTP_FROM
smtp.send_message(message, to_addrs=recipients)  # bez jawnego from_addr
```

Dla `SMTP_FROM="IFG [DS 723+] <ds723@ikonastudio.pl>"`:

1. `EmailMessage["From"]` bez cudzysłowów wokół display name z `[` `]` psuje parser.
2. `email.utils.getaddresses()` zwraca `[('', 'IFG'), ('', '')]`.
3. `smtplib.send_message()` używa **`IFG`** jako `MAIL FROM`.
4. Zenbox: `554 5.1.0 <IFG>: Sender address rejected: User unknown in local recipient table`.

Symulacja lokalna (stara ścieżka): `envelope would be: IFG` — potwierdzone.

### 3. Czy odbiorca jest używany jako sender?

**Nie w kodzie aplikacji.** Przegląd wszystkich implementacji wysyłki e-mail w IFG:

| Plik | Rola |
|------|------|
| `app/integrations/email/smtp_client.py` | Jedyny adapter SMTP (`send_email`) |
| `app/services/purchase_sync_email_notifier.py` | Wywołuje `send_email(config=..., to_addrs=recipients, ...)` |
| `scripts/ifg_guardian/plugins/ifg/smtp/test_send.py` | Guardian test — ten sam `send_email()` |

Kolejność argumentów w notifierze jest poprawna; `recipients` pochodzi z `PURCHASE_SYNC_NOTIFY_RECIPIENTS` / rekordu kolejki, `config.from_addr` z `SMTP_FROM`.

**Dlaczego w UI widać `lukasz@ikonastudio.pl` jako „odrzucony sender”?**

- Błąd SMTP w journalu to komunikat Zenbox z envelope `<IFG>`, nie adres odbiorcy.
- `lukasz@ikonastudio.pl` to jedyny odbiorca (`recipient_email` w kolejce, nagłówek `To`, pole konfiguracyjne) — łatwo pomylić z envelope w szczegółach zdarzenia.
- Kod **nie** przekazuje odbiorcy jako `from_addr` / `sender` / `envelope_from`.

### 4. Niespójność monitora „Próby” (osobny, niski wpływ)

| Źródło | Wartość | Znaczenie |
|--------|---------|-----------|
| Pole UI `Próby` (`TransmissionDetails.jsx`) | `row.attempt_no` | Z journal service |
| `KSeFTransmissionJournalService.log_event` | **zawsze `1`** (przed fixem) | Hardcoded |
| Metadata JSON | `"attempt": 2` | Z `begin_attempt()` notifiera |
| Opis zdarzenia | „próba 2/5” | Z metadata — **poprawne** |

**Przyczyna:** `attempt_no` w ORM było stałe `1`, podczas gdy metadata i opis używały `attempt_no` z notifiera (np. 2 przy retry).

**Fix (niskie ryzyko):** opcjonalny parametr `attempt_no` w `log_event()` + przekazanie z `_log_journal()` w notifierze.

---

## B. Porównanie ścieżek: test SMTP vs purchase_sync_notify

| Aspekt | Guardian `ifg smtp test` | Worker `purchase_sync_notify` |
|--------|--------------------------|-------------------------------|
| Runtime | Python na **Mac mini** (lokalne repo) | Kontener **worker** (`ifg-api:latest`) |
| Moduł | `app.integrations.email.smtp_client.send_email` | Ten sam moduł — **stara wersja w obrazie** |
| Konfiguracja | `.env.production` z DS723+ (REMOTE) lub `--local` | `.env.production` mount w kontenerze |
| `SMTP_FROM` parser | `parse_smtp_from()` ✅ | Brak — stary kod ❌ |
| `MAIL FROM` | `ds723@ikonastudio.pl` ✅ | `IFG` ❌ |
| Odbiorcy | `PURCHASE_SYNC_NOTIFY_RECIPIENTS` / argument CLI | `PURCHASE_SYNC_NOTIFY_RECIPIENTS` z env |
| Retry | Brak (jednorazowy test) | `PurchaseSyncNotificationRepository.begin_attempt()` + backoff |

**Wniosek:** Test SMTP PASS nie gwarantuje działania powiadomień produkcyjnych — różne runtime (host vs kontener) i różna wersja kodu w obrazie.

---

## C. Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/integrations/email/smtp_client.py` | Fix NOTIFY-0003 (`1f05f86`) — `parse_smtp_from`, jawny `from_addr` |
| `app/services/ksef_transmission_journal_service.py` | Opcjonalny `attempt_no` w `log_event()` |
| `app/services/purchase_sync_email_notifier.py` | Przekazanie `attempt_no` do journal |
| `tests/unit/test_smtp_client.py` | Test regresyjny: envelope ≠ recipient (produkcja) |
| `tests/unit/test_purchase_sync_email_notification.py` | Test E2E notifier: `ds723@` / `lukasz@` bez zamiany |

---

## D. Dodane testy

1. **`test_production_recipient_not_used_as_envelope_sender`** (`test_smtp_client.py`)
   - `SMTP_FROM`: `IFG [DS 723+] <ds723@ikonastudio.pl>`
   - Recipient: `lukasz@ikonastudio.pl`
   - Asercje: `from_addr == ds723@...`, `to_addrs == [lukasz@...]`, envelope ∉ recipients

2. **`test_notifier_recipient_not_swapped_with_envelope_sender`** (`test_purchase_sync_email_notification.py`)
   - Pełna ścieżka enqueue → `process_pending` z mock SMTP
   - Te same asercje na poziomie notifiera

3. **Istniejące (NOTIFY-0003):** display name, CSV recipients, invalid FROM, Guardian SMTP path

---

## E. Wyniki testów

```bash
python3 -m pytest tests/unit/test_smtp_client.py \
  tests/unit/test_purchase_sync_email_notification.py \
  tests/unit/test_guardian_smtp_workflow.py -q
# 52 passed

python3 -m pytest tests/unit/test_smtp_client.py \
  tests/unit/test_purchase_sync_email_notification.py \
  tests/unit/test_guardian_smtp_workflow.py \
  tests/unit/test_transmission_service.py \
  tests/unit/test_transmission_api.py -q
# 97 passed
```

Hasła SMTP: nie logowane w testach ani w tym raporcie.

---

## F. Ocena wpływu

| Obszar | Wpływ |
|--------|-------|
| Powiadomienia KSeF purchase sync | **Krytyczny** — brak e-maili po sesji auto-sync |
| Test SMTP Guardian | Brak — działa na lokalnym kodzie |
| API HTTP | Niski — API też ma stary obraz, ale endpointy SMTP nie są krytyczne dla sync |
| Dane / migracje | Brak — zmiana wyłącznie w kodzie aplikacji |
| Rollback | Niski ryzyko — rebuild poprzedniego obrazu lub `git checkout` + rebuild |

---

## G. Plan deployu (Guardian — kontrolowany)

**Warunek wejścia:** commit zmian journal + testów regresyjnych (jeśli jeszcze nie na `production`).

### Krok 1 — Preflight

```bash
python3 scripts/guardian.py ifg doctor
python3 scripts/guardian.py ifg release plan
python3 scripts/guardian.py ifg release evaluate
```

Upewnij się, że plan wymaga **Backend Build** i **Worker Build** (zmiana `app/integrations/email/smtp_client.py` musi być w `backend_changes`).

### Krok 2 — Deploy z buildem obrazu

```bash
python3 scripts/guardian.py ifg deploy run --yes
# Jeśli dirty tree: --allow-dirty-build (świadomy override)
```

**Krytyczne:** pipeline musi wykonać:

- `docker compose build api` (lub równoważny krok Guardian)
- `docker compose build worker` / restart worker z nowym obrazem
- `docker compose up -d api worker`

**Nie wystarczy:** sam `ifg env reload` — to tylko restart z tym samym obrazem.

### Krok 3 — Weryfikacja post-deploy

```bash
# Na DS723+ — oba serwisy muszą mieć parse_smtp_from=True
docker compose -f docker/docker-compose.prod.yml exec worker python -c \
  "import inspect; print('parse_smtp_from' in open(inspect.getsourcefile(__import__('app.integrations.email.smtp_client',fromlist=['x']))).read())"

python3 scripts/guardian.py ifg smtp check
python3 scripts/guardian.py ifg smtp test --yes
```

### Krok 4 — Weryfikacja funkcjonalna

- Poczekaj na kolejną sesję auto purchase sync **lub** wymuś retry istniejącego wpisu `PENDING`/`FAILED` w kolejce powiadomień.
- W Monitorze KSeF: zdarzenie `PURCHASE_SYNC_EMAIL` → status `email_sent`.
- Brak błędu `554 ... <IFG>`.

---

## H. Plan rollbacku

1. Na DS723+: `git log -1` — zapisz SHA sprzed deployu.
2. `git checkout <PREVIOUS_SHA>` w repo produkcyjnym.
3. `docker compose -f docker/docker-compose.prod.yml build api worker`
4. `docker compose -f docker/docker-compose.prod.yml up -d api worker`
5. `python3 scripts/guardian.py ifg env reload --yes` (jeśli zmieniono tylko env)
6. Weryfikacja: `/health` OK; worker wraca do poprzedniego zachowania SMTP.

**Czas rollbacku:** ~5–10 min (rebuild + restart). Brak migracji DB.

---

## I. Konfiguracja produkcyjna (bez sekretów)

```env
PURCHASE_SYNC_NOTIFY_RECIPIENTS=lukasz@ikonastudio.pl
SMTP_HOST=smtp.zenbox.pl
SMTP_PORT=587
SMTP_USER=ds723@ikonastudio.pl
SMTP_FROM="IFG [DS 723+] <ds723@ikonastudio.pl>"
SMTP_USE_TLS=true
```

Worker i API odczytują tę samą konfigurację przez mount `.env.production` → `/app/.env`.

---

## Decyzje dla ChatGPT

1. Czy po deployu z rebuildem obrazu wymusić jednorazowy retry wszystkich wpisów `FAILED` w `purchase_sync_notifications`, czy poczekać na naturalny backoff?
2. Czy dodać do Guardiana twardą regułę: po zmianie `app/**` w deploy — **zawsze** wymuszaj `docker build`, nawet gdy `origin/production` jest „clean” (ochrona przed scenariuszem NOTIFY-0003)?

---

## Wygenerowane raporty

- `docs/reports/2026-07-12_GWO-IFG_SMTP_ENVELOPE_SENDER_FIX.md` (ten dokument)
- Powiązany: `docs/reports/2026-07-12_GWO-IFG-NOTIFY-0003_SMTP_FROM_ENVELOPE_FIX.md`

---

## Technical Debt

**MEDIUM — Guardian deploy bez rebuild obrazu przy fixie backendu**  
Deploy NOTIFY-0003 oznaczył backend build jako SKIP, mimo że worker nie montuje kodu z hosta. Wartościowa poprawka: gate „backend file changed in pulled commits → force docker build”.

**LOW — UI pole „Próby” dla zdarzeń KSeF vs e-mail**  
Dla `PURCHASE_SYNC_EMAIL` użytkownik może oczekiwać `metadata.attempt` w gridzie technicznym; fix journal `attempt_no` to adresuje dla nowych zdarzeń, stare wpisy w DB nadal mają `attempt_no=1`.
