# GWO-IFG — Multi-recipient email reporting and 20:00 purchase sync session

**Data:** 2026-07-20  
**Repo:** `~/projekty/ifg_standalone`  
**Branch:** `production`  
**Status końcowy:** **PARTIAL** — kod i testy gotowe; produkcja wymaga aktualizacji `KSEF_AUTO_SYNC_CRON` + (opcjonalnie) CSV odbiorców, potem rebuild/env reload przez Guardiana

---

🩷 STATUS KOŃCOWY

| Obszar | Status |
|--------|--------|
| Audyt implementacji | ✅ |
| Sesja 20:00 w kodzie (default cron + slot label) | ✅ |
| Multi-recipient (CSV) | ✅ już istniało — potwierdzone / udokumentowane |
| Testy jednostkowe | ✅ 53 passed |
| Zmiana ENV na DS723+ | ⏸️ nie wykonana (wymaga potwierdzenia / listy odbiorców) |
| Deploy / rebuild worker | ⏸️ nie wykonany |

✅ Co działa (lokalnie)
- Default `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *`
- Etykieta sesji e-mail: `08:00` / `14:00` / `20:00` (Europe/Warsaw, CEST i CET)
- Jedna wiadomość SMTP do wszystkich adresów z `PURCHASE_SYNC_NOTIFY_RECIPIENTS` (CSV)
- Brak enqueue e-maila gdy `saved <= 0` (bez zmian)

⚠️ Znane problemy
- Produkcja nadal ma `KSEF_AUTO_SYNC_CRON=0 8,14 * * *` — sesja 20:00 **nie** wystartuje do zmiany ENV + restart workera
- Produkcja ma jednego odbiorcę: `lukasz@ikonastudio.pl` — multi-recipient wymaga uzupełnienia CSV
- Treść GWO urwała się w połowie („jeżeli istniejący może…”) — brak pełnej listy odbiorców w zapytaniu

❌ Co nie działa
- Sesja 20:00 na produkcji — do czasu aktualizacji ENV

---

## 1. Audyt obecnej implementacji

### Harmonogram synchronizacji

| Element | Wartość |
|---------|---------|
| Mechanizm | **Worker IFG** (kontener `worker`), tick w pętli głównej |
| Plik | `app/worker/ksef_auto_sync_scheduler.py` + `app/worker/__main__.py` (`_run_scheduler_tick`) |
| Nie jest | DSM cron / Guardian workflow / osobny daemon |
| ENV enable | `KSEF_AUTO_SYNC_ENABLED` |
| ENV cron | `KSEF_AUTO_SYNC_CRON` |
| Default (przed) | `0 8,14 * * *` |
| Default (po) | `0 8,14,20 * * *` |
| Strefa czasowa | **Europe/Warsaw** — `TZ=Europe/Warsaw` w `docker/docker-compose.prod.yml` dla `api`/`worker`/`db`; tick: `datetime.now().astimezone()` |
| Job | `BackgroundJob` `sync_purchase_invoices` (`incremental=true`) |
| Identyfikacja sesji | `slot_key = YYYY-MM-DDTHH:MM` w `ksef_sync_states` (`scope=ksef_purchase_auto_scheduler`, pole `last_executed_slot`) |
| 08:00 i 14:00 | **Jeden wspólny cron** z listą godzin (`8,14`), nie dwa oddzielne zadania |

### Powiadomienia e-mail

| Element | Wartość |
|---------|---------|
| Serwis | `PurchaseSyncEmailNotifier` |
| Warunek enqueue | tylko `PURCHASE_SYNC_AUTO`, sync complete, `saved > 0` |
| Odbiorcy | `PURCHASE_SYNC_NOTIFY_RECIPIENTS` (CSV) + legacy `PURCHASE_SYNC_NOTIFY_EMAIL` |
| Parser | `parse_notify_recipients()` — deduplikacja case-insensitive |
| Transport | wspólny `send_email()` → jeden mail, `To:` = lista odbiorców |
| Slot w treści | `infer_session_slot_label(finished_at)` — Europe/Warsaw |
| Inne powiadomienia | brak innych konsumentów tej samej listy (tylko purchase sync + Guardian SMTP test) |

### Produkcja DS723+ (odczyt 2026-07-20)

```
TZ=Europe/Warsaw
KSEF_AUTO_SYNC_ENABLED=true
KSEF_AUTO_SYNC_CRON=0 8,14 * * *
PURCHASE_SYNC_NOTIFY_ENABLED=true
PURCHASE_SYNC_NOTIFY_RECIPIENTS=lukasz@ikonastudio.pl
```

---

## 2. Zmiany w kodzie

| Plik | Zmiana |
|------|--------|
| `app/core/config.py` | default cron → `0 8,14,20 * * *` |
| `app/services/purchase_sync_notify_config.py` | slot `20:00` w `infer_session_slot_label` |
| `tests/unit/test_ksef_auto_sync_scheduler.py` | testy 20:00, recovery, parse hours |
| `tests/unit/test_purchase_sync_notify_config.py` | slot 20:00 (lato + zima) |
| `.env.example` | `KSEF_AUTO_SYNC_*` + dokumentacja CSV |
| `docs/architecture/KSEF_SCHEDULER.md` | sekcja harmonogramu 08/14/20 |

**Bez zmian:** logika KSeF sync, deduplikacja, SMTP envelope, retry e-mail.

---

## 3. Multi-recipient

Obsługa wielu odbiorców **już była** (GWO-IFG-NOTIFY-0002):

```env
PURCHASE_SYNC_NOTIFY_RECIPIENTS=ops@firma.pl,ksiegowosc@firma.pl
```

Zachowanie:
- jeden e-mail po sesji,
- wszyscy odbiorcy w nagłówku `To`,
- brak wysyłki przy 0 nowych fakturach,
- adresy nie wpływają na envelope sender (`SMTP_FROM`).

Aby włączyć na produkcji — uzupełnić CSV i `ifg env reload` (bez rebuild, o ile tylko ENV).

---

## 4. Testy

```bash
python3 -m pytest \
  tests/unit/test_ksef_auto_sync_scheduler.py \
  tests/unit/test_purchase_sync_notify_config.py \
  tests/unit/test_purchase_sync_email_notification.py \
  tests/unit/test_smtp_client.py -q
```

**Wynik:** `53 passed`

---

## 5. Plan wdrożenia (Guardian, po potwierdzeniu)

1. Commit zmian na `production` + push.
2. Na DS723+ w `.env.production`:
   ```
   KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *
   PURCHASE_SYNC_NOTIFY_RECIPIENTS=<lista CSV>
   ```
3. Deploy z **docker build** (zmiana kodu w `app/`) **albo** jeśli tylko ENV — `ifg env reload --yes` (sam cron w ENV działa po restarcie workera bez rebuild, ale nowy default w obrazie i slot label 20:00 wymagają rebuild).
4. Weryfikacja: po 20:00 local — journal `SCHEDULER_SLOT` / `PURCHASE_SYNC_AUTO`; przy nowych fakturach — `PURCHASE_SYNC_EMAIL` / `email_sent`.

**Rollback:** przywrócić `KSEF_AUTO_SYNC_CRON=0 8,14 * * *` + env reload.

---

## A. Root cause / decyzja produktowa

Trzecia sesja to rozszerzenie istniejącego crona workera (nie nowy scheduler). Multi-recipient był już w kontrakcie ENV CSV — brakowało tylko sesji 20:00 i etykiety w mailu.

## B. Zmienione pliki

Patrz sekcja 2.

## C. Deploy

Nie wykonany — czeka na potwierdzenie i listę odbiorców.

## D. Testy

53 passed (scheduler + notify config + email + smtp).

## E. Następny krok

1. Potwierdź listę `PURCHASE_SYNC_NOTIFY_RECIPIENTS`.
2. Zacommituj / deploy przez Guardiana z rebuild api/worker.
3. Ustaw `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *` na DS723+.

---

## Decyzje dla ChatGPT

1. Jaka dokładna lista CSV odbiorców ma trafić na produkcję?
2. Czy wdrażać teraz (commit + Guardian deploy + env), mimo że oryginalne GWO było ucięte?

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG_MULTI_RECIPIENT_AND_2000_SYNC_SESSION.md`
