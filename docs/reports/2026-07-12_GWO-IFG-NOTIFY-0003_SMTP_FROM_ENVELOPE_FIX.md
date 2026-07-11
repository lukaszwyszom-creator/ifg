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
| `guardian ifg smtp check` | ✅ READY (REMOTE) |
| `guardian ifg smtp test --yes` | ✅ PASS — mail wysłany |
| Commit NOTIFY-0003 | ❌ Brak (zmiany niezacommitowane) |
| Deploy IFG (Guardian) | ❌ Nie wykonany |
| Health produkcji (DS723+) | ✅ OK |
| Fix aktywny w workerze prod | ⚠️ Po deploy |

✅ Co działa
- Parsowanie `SMTP_FROM` z display name i nawiasami kwadratowymi
- Envelope sender = czysty adres (`ds723@ikonastudio.pl`)
- Nagłówek `From` z poprawnie cytowaną nazwą wyświetlaną
- Walidacja błędnej konfiguracji przed połączeniem SMTP
- Guardian SMTP check/test z konfiguracją REMOTE (DS723+)
- Test mail wysłany pomyślnie po fixie (lokalny kod na Mac mini)

⚠️ Znane problemy
- Fix nie jest jeszcze na produkcji (brak commit + deploy)
- Worker `PurchaseSyncEmailNotifier` na DS723+ nadal używa starego kodu do czasu deploy

❌ Co nie działa
- Wysyłka z kontenera produkcyjnego przed deployem — nadal może używać błędnego envelope sender

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
| **Czas** | ~1131 ms |

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
| **Czas** | ~1772 ms |

**Uwaga:** Test wykonany z Mac mini z lokalnym kodem (po fixie), konfiguracja odczytana z DS723+ (REMOTE). To potwierdza poprawność envelope sender po fixie, ale **nie oznacza**, że worker produkcyjny ma już nowy kod.

Raport auto: `docs/guardian/IFG_SMTP_TEST_2026_07_11.md`

---

## Commit i hash

| Pole | Wartość |
|------|---------|
| **Commit NOTIFY-0003** | Brak — zmiany w working tree |
| **HEAD (repo)** | `1926228` — `docs(notify): post-deploy verification report for NOTIFY-0002` |
| **Stan** | `app/integrations/email/smtp_client.py` i testy — modified/untracked |

**Następny krok operatora:** commit na `production` z message np. `fix(notify): parse SMTP_FROM display name for envelope sender`.

---

## Deploy wykonany przez Guardiana

| Operacja | Status |
|----------|--------|
| `guardian ifg deploy run` | ❌ Nie wykonany dla NOTIFY-0003 |
| `guardian ifg env reload` | ❌ Nie wymagany (zmiana kodu Python, nie `.env`) |
| Deploy wymagany | ✅ Tak — `api` + `worker` (zmiana `smtp_client.py`) |

Fix jest zweryfikowany diagnostycznie (Guardian SMTP test z Mac mini). Aby produkcyjny worker wysyłał powiadomienia KSeF z poprawnym envelope sender, wymagany jest standardowy deploy IFG przez Guardiana po commicie.

---

## Wynik health

### Produkcja (DS723+)

```bash
curl http://127.0.0.1:8000/health  # via SSH
```

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production",...}
```

**Status:** ✅ OK (przed deployem NOTIFY-0003 — bez regresji)

### Lokalnie (dev)

```json
{"status":"ok","app_name":"Imperium Faktur G","version":"1.0.0","environment":"local",...}
```

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

Potwierdzone testem jednostkowym i wysyłką Guardian `ifg smtp test --yes` (exit 0, Sent: True).

---

## Pozostały technical debt

| Priorytet | Opis |
|-----------|------|
| **HIGH** | Deploy NOTIFY-0003 na produkcję — worker nadal bez fixu |
| **LOW** | Guardian maskuje `SMTP_FROM` jako `IF***@ikonastudio.pl>` (artefakt maskowania, trailing `>`) |
| **LOW** | `TestMailResult` powoduje PytestCollectionWarning w `test_guardian_smtp_workflow.py` |
| **LOW** | Brak dedykowanego testu E2E na DS723+ po deploy (tylko Guardian test z orchestration host) |

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
- `/Users/lukasz/projekty/ifg_standalone/docs/guardian/IFG_SMTP_CHECK_2026_07_11.md`
- `/Users/lukasz/projekty/ifg_standalone/docs/guardian/IFG_SMTP_TEST_2026_07_11.md`

## Wygenerowane handoffy

Brak.

## Status operatora

| Akcja | Rekomendacja |
|-------|--------------|
| Commit NOTIFY-0003 | **Wymagany** — zmiany niezacommitowane |
| Deploy IFG (`api` + `worker`) | **Wymagany** — aby worker produkcyjny używał fixu |
| `guardian ifg smtp test --yes` | ✅ Wykonany — PASS (diagnostyka z Mac mini) |
| Weryfikacja skrzynki | Sprawdź dostarczenie maila testowego na `lukasz@ikonastudio.pl` |
| Po deploy | Uruchom sync testowy lub poczekaj na kolejny auto-sync KSeF i potwierdź brak błędu 554 |
