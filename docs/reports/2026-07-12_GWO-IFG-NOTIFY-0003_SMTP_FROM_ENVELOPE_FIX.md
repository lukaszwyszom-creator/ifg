# GWO-IFG-NOTIFY-0003 — Poprawne parsowanie SMTP_FROM i envelope sender

**Data:** 2026-07-12  
**Repo:** `~/projekty/ifg_standalone`  
**Branch:** `production` (docelowy)  
**Ticket:** NOTIFY-0003

---

🩷 STATUS KOŃCOWY

| Obszar | Status |
|--------|--------|
| Implementacja | ✅ Zakończona |
| Testy jednostkowe | ✅ 50 passed |
| Commit NOTIFY-0003 | ✅ `1f05f86` |
| Push `production` | ✅ `origin/production` zsynchronizowany |
| Deploy IFG (Guardian) | ✅ SUCCESS (`ifg deploy run --yes --allow-dirty-build`) |
| Env reload api/worker | ✅ SUCCESS (restart po deploy) |
| Health produkcji (DS723+) | ✅ OK |
| `guardian ifg smtp check` | ✅ READY (REMOTE) — post-deploy |
| `guardian ifg smtp test --yes` | ✅ PASS — mail wysłany post-deploy |
| Fix aktywny na DS723+ | ✅ `1f05f86` + `parse_smtp_from` na hoście |

✅ Co działa
- Parsowanie `SMTP_FROM` z display name i nawiasami kwadratowymi
- Envelope sender = czysty adres (`ds723@ikonastudio.pl`)
- Nagłówek `From`: `"IFG [DS 723+]" <ds723@ikonastudio.pl>`
- Walidacja błędnej konfiguracji przed połączeniem SMTP
- Kod na DS723+ (`1f05f86`) z `parse_smtp_from`
- Guardian SMTP check/test PASS po deploy i env reload
- Produkcja `/health` OK

⚠️ Znane problemy
- Deploy wykonany z `--allow-dirty-build` (lokalne niezacommitowane zmiany Guardiana poza zakresem NOTIFY-0003)
- `docker build` SKIP — kod z git pull + env reload (bind-mount), bez rebuild obrazu

❌ Co nie działa
- Brak

---

## Potwierdzony root cause

Produkcyjna wartość:

```env
SMTP_FROM="IFG [DS 723+] <ds723@ikonastudio.pl>"
```

Stary kod ustawiał:

```python
message["From"] = config.from_addr  # surowa wartość SMTP_FROM
smtp.send_message(message, to_addrs=recipients)  # bez jawnego from_addr
```

**Mechanizm błędu:**

1. `EmailMessage["From"] = 'IFG [DS 723+] <ds723@ikonastudio.pl>'` — nawiasy kwadratowe w display name bez cudzysłowów psują parser nagłówka.
2. Wewnętrzna reprezentacja nagłówka: `IFG, <>` (display name i pusty adres).
3. `email.utils.getaddresses()` zwraca `[('', 'IFG'), ('', '')]`.
4. `smtplib.send_message()` używa `IFG` jako envelope sender → serwer Zenbox odrzuca:

```
554 5.1.0 <IFG>: Sender address rejected: User unknown in local recipient table
```

DNS, TCP, STARTTLS i AUTH działały poprawnie — problem dotyczył wyłącznie `MAIL FROM`.

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/integrations/email/smtp_client.py` | `parse_smtp_from()`, jawny `from_addr` w `send_message()` |
| `tests/unit/test_smtp_client.py` | **nowy** — testy parsowania i envelope sender |
| `tests/unit/test_purchase_sync_email_notification.py` | testy notifiera z display name + invalid FROM |
| `tests/unit/test_guardian_smtp_workflow.py` | test envelope via Guardian SMTP test path |
| `scripts/ifg_guardian/plugins/ifg/smtp/config.py` | walidacja `SMTP_FROM` przez `parse_smtp_from()` |

**Bez zmian (zgodnie z zakresem):** kolejka powiadomień, retry, snapshot, Journal KSeF, harmonogram, odbiorcy, Zenbox.

---

## Opis rozwiązania

Centralna logika w `send_email()` — wspólna dla:

- produkcyjnego `PurchaseSyncEmailNotifier`
- diagnostycznego `guardian ifg smtp test`

Przepływ:

1. `parse_smtp_from(config.from_addr)` → `(from_header, envelope_from)`
2. Walidacja przed `smtplib.SMTP()` — błąd konfiguracji bez próby `MAIL FROM`
3. `message["From"] = from_header` — poprawnie sformatowany nagłówek RFC
4. `smtp.send_message(message, from_addr=envelope_from, to_addrs=recipients)` — jawny envelope sender

---

## Sposób parsowania SMTP_FROM

Funkcja: `parse_smtp_from(raw: str) -> tuple[str, str]`

Kolejność:

1. Strip whitespace i opcjonalnych cudzysłowów zewnętrznych (`"..."` / `'...'`)
2. Regex `^(.+?)\s*<([^<>@\s]+@[^<>@\s]+)\s*>$` — forma `Display Name <addr@domain>`
   - obsługuje nawiasy kwadratowe w display name (`IFG [DS 723+]`)
3. Fallback `email.utils.parseaddr()` — proste formy
4. Fallback plain email — `addr@domain`
5. Odrzucenie: pusta wartość, sam display name bez `@`, niepoprawny adres

Przykłady:

| SMTP_FROM | From header | Envelope |
|-----------|-------------|----------|
| `ds723@ikonastudio.pl` | `ds723@ikonastudio.pl` | `ds723@ikonastudio.pl` |
| `IFG [DS 723+] <ds723@ikonastudio.pl>` | `"IFG [DS 723+]" <ds723@ikonastudio.pl>` | `ds723@ikonastudio.pl` |
| `IFG` | — | `SmtpFromParseError` |
| `` (pusta) | — | `SmtpFromParseError` |

---

## Sposób ustawiania SMTP envelope sender

```python
from_header, envelope_from = parse_smtp_from(config.from_addr)
message["From"] = from_header
smtp.send_message(message, from_addr=envelope_from, to_addrs=recipients)
```

- **Nagłówek wiadomości (`From`):** pełna wartość z display name (RFC 5322, `formataddr`)
- **Envelope sender (`MAIL FROM`):** wyłącznie czysty adres e-mail, bez display name

Dla produkcji:

```
From:     "IFG [DS 723+]" <ds723@ikonastudio.pl>
MAIL FROM:<ds723@ikonastudio.pl>
```

---

## Wyniki testów

```bash
python3 -m pytest \
  tests/unit/test_smtp_client.py \
  tests/unit/test_purchase_sync_email_notification.py \
  tests/unit/test_guardian_smtp_workflow.py -q
```

**Wynik:** `50 passed, 1 warning` (PytestCollectionWarning: `TestMailResult` — istniejący warning Guardiana)

Pokrycie scenariuszy:

| # | Scenariusz | Wynik |
|---|------------|-------|
| 1 | `SMTP_FROM=ds723@ikonastudio.pl` | ✅ envelope = bare address |
| 2 | `SMTP_FROM="IFG [DS 723+] <ds723@ikonastudio.pl>"` | ✅ envelope = `ds723@ikonastudio.pl`, From z display name |
| 3 | `SMTP_FROM=IFG` | ✅ błąd konfiguracji, brak SMTP |
| 4 | pusta wartość | ✅ błąd konfiguracji |
| 5 | wielu odbiorców | ✅ bez regresji |
| 6 | Guardian `ifg smtp test` | ✅ envelope via `send_email` |
| 7 | `PurchaseSyncEmailNotifier` | ✅ ten sam `send_email()` |

---

## Wynik `guardian ifg smtp check`

```bash
python3 scripts/guardian.py ifg smtp check
```

| Pole | Wartość |
|------|---------|
| **Status** | `READY` |
| **Environment** | `REMOTE` |
| **Env file** | `/volume1/docker/ifg_v2/ifg_standalone/.env.production` |
| **Remote host** | `zdalny_admin@ds723` |
| **SMTP_FROM** | PASS — `envelope sender: ds***@ikonastudio.pl` |
| **connectivity:AUTH** | PASS — login accepted |
| **Exit code** | `0` |
| **Czas** | ~1038 ms (post-deploy) |

Raport auto: `docs/guardian/IFG_SMTP_CHECK_2026_07_11.md`

---

## Wynik `guardian ifg smtp test --yes`

```bash
python3 scripts/guardian.py ifg smtp test --yes
```

| Pole | Wartość |
|------|---------|
| **Status** | `READY` |
| **Test Mail** | PASS |
| **Sent** | `True` |
| **Subject** | `IFG SMTP Test` |
| **Recipients** | `lukasz@ikonastudio.pl` |
| **Message** | `test mail sent to 1 recipient(s)` |
| **Exit code** | `0` |
| **Czas** | ~1881 ms (post-deploy) |

Potwierdzone po deploy + env reload. Brak błędu 554 Zenbox.

Raport auto: `docs/guardian/IFG_SMTP_TEST_2026_07_11.md`

---

## Commit i hash

| Pole | Wartość |
|------|---------|
| **Commit NOTIFY-0003** | `1f05f8674053b4dd3771979010c4219f3b67e90e` |
| **Short hash** | `1f05f86` |
| **Message** | `fix(notify): parse SMTP_FROM display name for envelope sender` |
| **Branch** | `production` |
| **Push** | ✅ `1926228..1f05f86 production -> production` |
| **Remote HEAD** | `1f05f8674053b4dd3771979010c4219f3b67e90e` |
| **DS723+ HEAD** | `1f05f86` (zweryfikowany SSH) |

---

## Deploy wykonany przez Guardiana

```bash
python3 scripts/guardian.py ifg deploy run --yes --allow-dirty-build
```

| Pole | Wartość |
|------|---------|
| **Workflow** | `2026-07-11T225655Z_ifg_deploy_run` |
| **Status** | ✅ SUCCESS — LIVE COMPLETE |
| **Duration** | 36909 ms |
| **Release decision** | `READY_WITH_OVERRIDE` (dirty tree override) |
| **Rollback commit** | `1f05f86` |

Wykonane kroki:

| # | Krok | Status |
|---|------|--------|
| 1 | `git pull origin production` | ✅ → `1f05f86` |
| 2 | `npm run build` + artifact gate | ✅ |
| 3 | rsync frontend dist | ✅ |
| 4 | `docker build` | SKIP (bind-mount) |
| 5 | `alembic upgrade` | SKIP (at head) |
| 6 | `compose up -d` | ✅ api/worker Running |
| 7 | health check | ✅ 200 OK |
| 8 | log verification | ✅ |

Dodatkowo po deploy:

```bash
python3 scripts/guardian.py ifg env reload --yes
```

Restart `api` + `worker` w celu załadowania nowego `smtp_client.py` (workflow `2026-07-11T225740Z_ifg_env_reload`, READY).

Raport deploy: `docs/guardian/IFG_DEPLOY_RUN_2026_07_11.md`

---

## Wynik health

### Produkcja (DS723+) — post-deploy

```bash
curl http://127.0.0.1:8000/health  # via SSH / deploy pipeline
```

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

**Status:** ✅ OK (po deploy NOTIFY-0003)

---

## Potwierdzenie pola „Od”

Dla `SMTP_FROM="IFG [DS 723+] <ds723@ikonastudio.pl>"`:

| Warstwa | Wartość |
|---------|---------|
| **Nagłówek From (RFC)** | `"IFG [DS 723+]" <ds723@ikonastudio.pl>` |
| **Widoczne „Od” w kliencie mail** | `IFG [DS 723+] <ds723@ikonastudio.pl>` |
| **Envelope sender (MAIL FROM)** | `ds723@ikonastudio.pl` |

Cudzysłowy wokół display name są wymagane przez RFC 5322 (nawiasy kwadratowe w nazwie). Klient pocztowy wyświetla pole **Od** jako:

> **IFG [DS 723+]** `<ds723@ikonastudio.pl>`

Potwierdzone testem jednostkowym, deployem na DS723+ (`1f05f86`) i wysyłką Guardian `ifg smtp test --yes` post-deploy (exit 0, Sent: True).

---

## Pozostały technical debt

| Priorytet | Opis |
|-----------|------|
| **LOW** | Deploy z `--allow-dirty-build` — lokalne niezacommitowane zmiany Guardiana (poza NOTIFY-0003) |
| **LOW** | Guardian maskuje `SMTP_FROM` jako `IF***@ikonastudio.pl>` (artefakt maskowania) |
| **LOW** | `docker build` SKIP — architektura bind-mount; wymaga env reload po zmianach Python |
| **LOW** | Brak testu E2E wysyłki z kontenera worker (tylko Guardian test + unit tests) |

---

## Rollback plan

1. **Przed deployem:** nie commitować / nie deployować — brak wpływu na produkcję.
2. **Po deployu NOTIFY-0003:**
   - `git revert <commit-hash-notify-0003>`
   - Deploy przez Guardiana: `python3 scripts/guardian.py ifg deploy run --yes`
   - Weryfikacja: `python3 scripts/guardian.py ifg smtp check`
3. **Bez rebuildu obrazu:** rollback wymaga deploy z poprzednim commitem (stary `smtp_client.py`).
4. **Konfiguracja `.env`:** bez zmian — rollback dotyczy wyłącznie kodu Python.
5. **Kolejka powiadomień:** bez zmian — failed items retry wg istniejącej polityki; brak migracji DB.

---

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-07-12_GWO-IFG-NOTIFY-0003_SMTP_FROM_ENVELOPE_FIX.md` (ten dokument)
- `/Users/lukasz/projekty/ifg_standalone/docs/guardian/IFG_DEPLOY_RUN_2026_07_11.md`
- `/Users/lukasz/projekty/ifg_standalone/docs/guardian/IFG_SMTP_CHECK_2026_07_11.md`
- `/Users/lukasz/projekty/ifg_standalone/docs/guardian/IFG_SMTP_TEST_2026_07_11.md`
- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-07-11_GWO-GUARDIAN-0079_ENV_RELOAD.md`

## Wygenerowane handoffy

Brak.

## Status operatora

| Akcja | Status |
|-------|--------|
| Commit NOTIFY-0003 | ✅ `1f05f86` |
| Push `production` | ✅ Zsynchronizowany z `origin/production` |
| Deploy Guardian | ✅ SUCCESS (36.9s, LIVE COMPLETE) |
| Env reload api/worker | ✅ SUCCESS |
| Health DS723+ | ✅ OK |
| SMTP check post-deploy | ✅ READY |
| SMTP test post-deploy | ✅ PASS (Sent: True) |
| Weryfikacja skrzynki | Sprawdź `lukasz@ikonastudio.pl` — mail testowy post-deploy |
| Kolejny auto-sync KSeF | Oczekiwany brak błędu 554 przy wysyłce powiadomień |
