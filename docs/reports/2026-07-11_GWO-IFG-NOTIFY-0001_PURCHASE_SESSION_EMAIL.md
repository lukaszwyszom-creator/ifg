# GWO-IFG-NOTIFY-0001 — E-mail podsumowujący sesję pobierania faktur zakupowych KSeF

**Data:** 2026-07-11  
**Branch:** production  
**Zakres:** pierwszy kanał powiadomień IFG — wyłącznie e-mail po automatycznej synchronizacji zakupów KSeF

---

## 1. Architektura

```
KSeF auto-sync (08:00 / 14:00)
        │
        ▼
KSeFSessionService.sync_purchase_invoices()
  correlation_id = sesja
  PurchaseSyncAudit.saved_invoice_ids
        │
        ▼ (SUCCESS + new > 0 + AUTO)
PurchaseSyncEmailNotifier.maybe_enqueue_after_sync()
        │
        ▼
purchase_sync_notifications (PENDING)
        │
        ▼
Worker loop: _process_notification_queue()
        │
        ▼
SMTP (smtplib) → SENT / FAILED
        │
        ▼
KSeF Journal: PURCHASE_SYNC_EMAIL
        │
        ▼
Monitor KSeF (frontend summary)
```

**Świadome ograniczenie:** brak uniwersalnego Notification Engine. Jedna tabela kolejki, jeden typ powiadomienia, jeden szablon.

### Kluczowe komponenty

| Warstwa | Plik |
|---------|------|
| Model ORM | `app/persistence/models/purchase_sync_notification.py` |
| Migracja | `alembic/versions/o5p6q7r8s9t0_purchase_sync_notification_queue.py` |
| Repozytorium | `app/persistence/repositories/purchase_sync_notification_repository.py` |
| SMTP | `app/integrations/email/smtp_client.py` |
| Logika kolejki + szablon | `app/services/purchase_sync_email_notifier.py` |
| Hook po sync | `app/services/ksef_session_service.py` |
| Worker mailer | `app/worker/__main__.py` |
| Konfiguracja | `app/core/config.py` |
| Monitor UI | `frontend-react/.../transmissionUtils.js` |

---

## 2. Przebieg sesji

Każda synchronizacja zakupów ma `correlation_id` (UUID) tworzony w `sync_purchase_invoices()`.

`PurchaseSyncAudit` agreguje:

- `saved` / `saved_invoice_ids` — nowe faktury zapisane w bazie
- `skipped_existing` — duplikaty KSeF
- `skipped_invalid` + `skipped_error` — błędy parsowania/zapisu
- `is_sync_incomplete()` — przerwana / niekompletna sesja

Przy zapisie faktury `_process_purchase_invoice_xml()` wywołuje:

```python
audit.record_saved(ksef_reference_number, invoice_id=invoice.id)
```

Do kolejki trafiają wyłącznie ID faktur `direction=purchase` pobranych i zapisanych w tej sesji.

---

## 3. Notification Queue

Tabela `purchase_sync_notifications`:

| Pole | Znaczenie |
|------|-----------|
| `correlation_id` | UNIQUE — identyfikator sesji |
| `status` | `PENDING` → `SENT` / `FAILED` |
| `sync_status` | `SUCCESS` (sync pozostaje SUCCESS niezależnie od SMTP) |
| `new_invoice_ids` | JSONB lista UUID nowych faktur |
| `skipped_duplicates` | liczba duplikatów |
| `errors_count` | błędy parsowania/zapisu |
| `notification_sent_at` | timestamp wysyłki (deduplikacja) |
| `last_error` | ostatni błąd SMTP |

**Warunek enqueue:**

- `PURCHASE_SYNC_NOTIFY_ENABLED=true`
- `operation_type == PURCHASE_SYNC_AUTO`
- `audit.is_sync_incomplete() == False`
- `audit.saved > 0`
- brak wpisu dla `correlation_id`

Wysyłka **nie** następuje w kodzie synchronizacji — tylko `PENDING` w kolejce.

---

## 4. Deduplikacja

- `UNIQUE(correlation_id)` — jedna sesja = jeden wpis kolejki
- `maybe_enqueue_after_sync()` pomija ponowne wywołanie dla tego samego `correlation_id`
- `notification_sent_at` ustawiane przy `SENT` — ponowne `process_pending()` nie wysyła drugiego maila
- Retry dotyczy tylko `FAILED` bez `notification_sent_at` (bez ponownego pobierania faktur)

---

## 5. Konfiguracja SMTP

Zmienne środowiskowe (bez haseł w repo):

| Zmienna | Opis |
|---------|------|
| `PURCHASE_SYNC_NOTIFY_ENABLED` | włączenie/wyłączenie (domyślnie `false`) |
| `PURCHASE_SYNC_NOTIFY_EMAIL` | adres odbiorcy |
| `SMTP_HOST` | serwer SMTP |
| `SMTP_PORT` | port (domyślnie 587) |
| `SMTP_USER` | opcjonalny login |
| `SMTP_PASSWORD` | hasło (tylko ENV, nie w Git) |
| `SMTP_FROM` | nadawca |
| `SMTP_USE_TLS` | STARTTLS (domyślnie `true`) |

Przykład `.env.production` (operator uzupełnia wartości):

```env
PURCHASE_SYNC_NOTIFY_ENABLED=true
PURCHASE_SYNC_NOTIFY_EMAIL=operator@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=ifg-notify
SMTP_PASSWORD=<sekret>
SMTP_FROM=IFG <ifg-notify@example.com>
SMTP_USE_TLS=true
```

---

## 6. Szablon e-mail

**Temat:** `IFG — nowe faktury zakupowe z KSeF`

**Treść:** data sesji, status, liczba nowych faktur, lista (kontrahent | numer | data | kwota brutto), suma brutto, informacja o Monitorze KSeF. Bez załączników, XML, PDF.

---

## 7. Monitor KSeF

Po wysyłce (lub błędzie) journal loguje zdarzenie `PURCHASE_SYNC_EMAIL`:

- `email_sent` → „Powiadomienie e-mail wysłane.”
- `email_failed` → „Powiadomienie e-mail nie zostało wysłane.”

Frontend (`summarizeGroup` / `buildSummaryLines`) pokazuje status w rozwiniętym podsumowaniu grupy synchronizacji zakupów.

---

## 8. Testy

Plik: `tests/unit/test_purchase_sync_email_notification.py`

| Scenariusz | Wynik |
|----------|-------|
| 0 nowych faktur | brak enqueue |
| 1 nowa faktura | 1 wpis PENDING |
| 5 nowych faktur | 1 wpis, 5 ID |
| ponowienie tej samej sesji | brak drugiego wpisu |
| SMTP FAILED | status FAILED, journal email_failed |
| retry | SENT po drugim process_pending |
| same duplikaty | brak enqueue |
| sync incomplete | brak enqueue |
| sync manual | brak enqueue |
| udana wysyłka | 1 wywołanie send_email, SENT |

**Dowód:**

```bash
python3 -m pytest tests/unit/test_purchase_sync_email_notification.py -q
# 10 passed in 0.27s
```

---

## 9. Ograniczenia

- Tylko synchronizacja **automatyczna** (`PURCHASE_SYNC_AUTO`), nie manualna
- Tylko faktury **zakupowe** nowe w sesji
- Brak powiadomień sprzedaży, per-faktura, webhooków, WhatsApp
- Worker przetwarza max 5 wpisów na tick — przy dużym zaległości wysyłka jest stopniowa
- Wymaga migracji `o5p6q7r8s9t0` przed użyciem na produkcji
- **Deploy DS723+ nie wykonany** (zgodnie z zakazem GWO)

---

## Decyzje dla ChatGPT

1. Czy powiadomienia e-mail mają obejmować również **ręczną** synchronizację zakupów (`PURCHASE_SYNC_MANUAL`), czy pozostajemy przy wyłącznie auto 08:00/14:00?
2. Czy przy `FAILED` SMTP dodać **automatyczny backoff** (np. `available_at` + max prób), czy wystarczy ponowienie przy kolejnych tickach workera bez limitu?
3. Czy odbiorca ma być **pojedynczy** (`PURCHASE_SYNC_NOTIFY_EMAIL`), czy w kolejnym GWO lista rozdzielcza (CSV / wiele adresów)?

---

## Wygenerowane raporty

- `docs/reports/2026-07-11_GWO-IFG-NOTIFY-0001_PURCHASE_SESSION_EMAIL.md` (ten dokument)

## Wygenerowane handoffy

- Brak (GWO nie wymaga handoffu Guardian dla tej zmiany domenowej IFG).

## Kroki dla operatora

1. Uruchomić migrację na środowisku docelowym:
   ```bash
   alembic upgrade head
   ```
2. Ustawić zmienne ENV (patrz sekcja 5) w `.env.production` — **hasło SMTP poza repo**.
3. Upewnić się, że `KSEF_AUTO_SYNC_ENABLED=true` i worker działa (`python -m app.worker`).
4. Po pierwszej sesji auto z nowymi fakturami sprawdzić:
   - tabela `purchase_sync_notifications` — wpis `SENT`
   - Monitor KSeF — „Powiadomienie e-mail wysłane”
5. Przy błędzie SMTP: status `FAILED` w kolejce; sync KSeF pozostaje SUCCESS; worker ponowi przy następnym ticku.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Kolejka `purchase_sync_notifications` z deduplikacją po `correlation_id`
- Enqueue po SUCCESS auto-sync z `new_invoices > 0`
- Worker wysyła e-mail przez SMTP (osobna ścieżka od sync)
- Journal + Monitor KSeF pokazują status powiadomienia
- 10/10 testów jednostkowych PASS

⚠️ Znane problemy
- Guardian `ksef check`: lokalnie ERROR przez niezcommitowany frontend dist (oczekiwane w trakcie dev)
- Brak automatycznego limitu prób SMTP retry

❌ Co nie działa
- Brak weryfikacji end-to-end SMTP na produkcji (deploy zabroniony w tym GWO)

A. Root cause  
Brak wcześniejszego kanału powiadomień po sync zakupów — wymagany był minimalny, sesyjny pipeline e-mail bez Notification Engine.

B. Zmienione pliki  
Backend: model, migracja, repo, SMTP client, notifier, config, enums, audit, ksef_session_service, worker, journal metadata.  
Frontend: `transmissionUtils.js`.  
Testy: `test_purchase_sync_email_notification.py`.

C. Deploy  
Nie wykonano (zakaz DS723+ w GWO). Wymagana migracja `o5p6q7r8s9t0` przed włączeniem na produkcji.

D. Testy  
`python3 -m pytest tests/unit/test_purchase_sync_email_notification.py -q` → **10 passed**.

E. Następny krok  
Operator: migracja + konfiguracja SMTP na DS723+, obserwacja pierwszej sesji 08:00 lub 14:00 z nowymi fakturami.

## Technical Debt

- **MEDIUM — SMTP retry policy:** Brak jawnego `max_attempts` i backoff dla FAILED; worker ponawia przy każdym ticku bez ograniczenia. Warto dodać w osobnym GWO po stabilizacji produkcyjnej.

## Architecture Debt

- **LOW — Single-recipient config:** `PURCHASE_SYNC_NOTIFY_EMAIL` obsługuje jeden adres; rozszerzenie na listę wymaga osobnego GWO, nie uniwersalnego Notification Engine.
