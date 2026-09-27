# GWO-IFG-PURCHASE-INVOICE-NOTIFICATION-INCIDENT-2026-09-12

**Tryb:** DIAGNOSE_PRODUCTION_ONLY (read-only)  
**Repo lokalne:** `/Users/lukasz/projekty/ifg_standalone`  
**Prod:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone` @ `42b77fa`  
**Data audytu:** 2026-09-12  
**NIP:** 9670402857  

---

## STATUS:
DIAGNOSED

## VERDICT:
FALSE_SYNC_INCOMPLETE_BLOCKS_EMAIL

Slot 08:00 Europe/Warsaw **wystartował i zapisał 1 nową fakturę zakupową**, ale audit oznaczył sync jako `incomplete=True` przez fałszywy `metadata_not_in_db` (rozjazd `issue_date` vs okno metadanych KSeF).  
`PurchaseSyncEmailNotifier.maybe_enqueue_after_sync` **nie został wywołany** — brak wiersza w `purchase_sync_notifications`, brak próby SMTP.

## FAILED_LAYER:
SESSION_AGGREGATION

*(wtórnie: EMAIL_DECISION = skip z powodu `is_sync_incomplete()`; KSeF fetch, scheduler i SMTP runtime OK)*

## EXPECTED_SLOT:
`2026-09-12T08:00` Europe/Warsaw (`0 8,14,20 * * *`)

## JOB_STATUS:
`done` — `background_jobs.id=98c7cdcf-cba7-483f-8161-f9538fc300fc`  
`job_type=sync_purchase_invoices`, `attempts=1`, `scheduler_slot=2026-09-12T08:00`  
result: `saved=1`, `received=15`, `skipped_existing=14`, `skipped_parse=0`, `rate_limited=false`  
Worker log: `status=incomplete` / `SYNC_INCOMPLETE`

## NEW_PURCHASE_INVOICES:
**1** — `9512120077-20260912-0805490004A8-9F`  
- seller: P4 sp. z o. o.  
- number: `F/20224261/09/26`  
- issue_date: `2026-09-12`  
- invoice id: `da577a32-e106-4a22-90cc-a7baaa63c5f7`  
- created_at: `2026-09-12 08:00:01` Europe/Warsaw  
- przypisanie do sesji/joba: **tak** (`scheduler_slot` + worker job claim/done)

## EMAIL_DECISION:
**SKIPPED_DUE_TO_SYNC_INCOMPLETE**  
Nie: `MAIL_SENT` / `NO_NEW_INVOICES` / SMTP error.  
Gate w kodzie: `if not audit.is_sync_incomplete() and report["status"] == "ok": maybe_enqueue_after_sync(...)`.

## EMAIL_SEND_ATTEMPTED:
**NO**

## EMAIL_SEND_RESULT:
**N/A** (brak enqueue → brak SENT/FAILED w `purchase_sync_notifications` dla slotu 12.09)

## ROOT_CAUSE:
Porównanie kompletności sync używa `list_ksef_purchase_refs_in_issue_range(date_from, date_to)` (filtr **issue_date**), podczas gdy KSeF zwraca metadane po **PermanentStorage / Invoicing / Issue**.

Faktura `5223027866-20260831-65EA58C00109-02` (Alior Leasing):
- **jest w DB** (`exists_by_ksef_number` → poprawnie `skipped_existing`),
- ma `issue_date=2026-08-29`,
- okno sync 12.09: `date_from=2026-08-30` … `date_to=2026-09-12`,
- więc **wypada poza zakres issue_date** → `metadata_not_in_db_count=1` → `incomplete=True` → **blokada maila mimo `saved=1`**.

To **nie** jest regresja „faktury poza sesją / count=0”. Sesja zapisała fakturę; mail nie wystartował przez fałszywy incomplete.

**Regresja chroniczna od 2026-09-01 14:00:** ten sam sample ref blokuje kolejne sloty; **11 faktur zakupowych** zapisanych po ostatnim mailu **bez** powiadomienia.

---

## EVIDENCE:

### 1. Kontenery / health
| Kontener | Status |
|----------|--------|
| `ifg-db-1` | Up 2 days (**healthy**) |
| `ifg-api-1` | Up 2 days (**healthy**) |
| `ifg-worker-1` | Up 2 days (**healthy**) |
| `ifg-frontend-1` | Up 2 days (brak healthcheck) |

API `/health`: `status=ok`, `environment=production`, `db_timezone=Europe/Warsaw`.

### 2. Harmonogram / TZ
| Pole | Wartość |
|------|---------|
| Cron (worker ENV) | `0 8,14,20 * * *` |
| Auto sync enabled | `true` |
| Worker `TZ` | `Europe/Warsaw` |
| Host / process now | 2026-09-12 ~09:48 CEST |
| `last_executed_slot` | **`2026-09-12T08:00`** |
| `last_skip_logged_slot` | `2026-09-12T08:00` (późniejsze ticki pomijają ten slot) |
| `last_enqueued_job_id` | `98c7cdcf-…` |
| Ostatni pominięty (po execute) | ten sam slot 08:00 (SKIP already executed) |
| Następny oczekiwany | `2026-09-12T14:00` |

`purchase_invoices.last_success_at` = **2026-09-01 08:00** (incomplete nie aktualizuje success); `last_error` = *KSeF purchase sync incomplete…*.

### 3–5. Slot 08:00 — lifecycle
| Krok | Wynik |
|------|-------|
| Scheduler enqueue | TAK (`created_at` 08:00:01, payload `scheduler_slot`) |
| Job start | 08:00:02 claim |
| Auth | token refresh 200 |
| Metadata | 15 unique refs |
| XML download | 1 (nowa P4) |
| Saved | **1** |
| Job end | 08:00:17 `done` |
| `incomplete` | **True** (`metadata_not_in_db` = Alior ref) |
| Notify enqueue | **BRAK** |

### 6. Sesja vs faktury
Wszystkie 15 refów z metadanych **istnieją w DB** po `ksef_reference_number`.  
Jedyny „missing” w audycie to ref z `issue_date` poza oknem.

### 7–8. SMTP runtime (bez wartości sekretów)
| Zmienna | Stan |
|---------|------|
| `PURCHASE_SYNC_NOTIFY_ENABLED` | PRESENT (`true`) |
| `PURCHASE_SYNC_NOTIFY_RECIPIENTS` | PRESENT |
| `PURCHASE_SYNC_NOTIFY_EMAIL` | MISSING (OK — recipients wystarczają) |
| `SMTP_HOST` | PRESENT |
| `SMTP_PORT` | PRESENT (`587`) |
| `SMTP_USER` | PRESENT |
| `SMTP_PASSWORD` | PRESENT |
| `SMTP_FROM` | PRESENT |
| `SMTP_TLS` | MISSING (nie blokowało wysyłki 01.09) |

### 9. Regresja „poza sesją / zero”
**Wykluczona** jako przyczyna dzisiejszego braku maila.  
`saved=1` w job result; brak maila = gate incomplete, nie zero nowych.

### 10. Porównanie z ostatnim udanym mailem
| | **2026-09-01 08:00 (OK)** | **2026-09-12 08:00 (FAIL mail)** |
|--|---------------------------|----------------------------------|
| Job | `6a362fce-…` done | `98c7cdcf-…` done |
| Window | `2026-08-29`→`2026-09-01` | `2026-08-30`→`2026-09-12` |
| saved | 1 | 1 |
| incomplete | **False** | **True** |
| Notify | ENQUEUED + SENT (`1eebb4cc-…`) | **brak wiersza** |
| Uwaga | okno jeszcze obejmuje Alior `issue_date=2026-08-29` | Alior poza `issue_date>=08-30` |

Od **2026-09-01 14:00** ten sam pattern `metadata_not_in_db_sample=5223027866-20260831-65EA58C00109-02` powtarza się w logach; **brak SENT** w `purchase_sync_notifications` po 01.09 08:00.

Faktury zakupowe bez maila (created_at > ostatni SENT): **11** (LOCUM, AMSK IT, Orange, OSCAR, TAR-CYL, GENERON, STACJA, COMMON RAIL, BD Firma, OIO, **P4**).

---

## SAFE_NEXT_ACTION:
1. **Osobne GWO fix (kod):** zmiana audytu kompletności — nie porównywać metadanych KSeF wyłącznie do `issue_date` window (np. lookup po `ksef_reference_number` dla refs z metadanych / rozszerzyć okno o daty PermanentStorage).  
2. **Backfill operacyjny (po fix lub ręczny notify):** powiadomienie o 11 fakturach bez maila od 01.09 — tylko po jawnej zgodzie (poza tym zadaniem).  
3. **Nie** restartować kontenerów / nie wysyłać testowego SMTP w ramach diagnostyki.  
4. Slot 14:00 dziś prawdopodobnie znów będzie `incomplete` z tym samym Alior ref — oczekiwane do czasu fixu.

---

## Bezpieczeństwo operacyjne tego zadania
| Akcja | Wynik |
|-------|-------|
| Zmiany kodu / config / DB | **NIE** |
| Restart / deploy / push | **NIE** |
| Testowy mail | **NIE** |
| DS723+ | tylko odczyt (SSH + docker logs/psql SELECT) |

---

## RELEASE STATE
- [x] LOCAL_REVIEW_REQUIRED *(diagnostyka; brak wdrożenia)*
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

---

## Decyzje dla ChatGPT
1. Czy otworzyć GWO naprawcze na audit `issue_date` vs metadata dates?  
2. Czy po fixie robić backfill maila dla 11 faktur (01.09–12.09)?

---

## FILES_CHANGED:
Brak (diagnostyka read-only; raport tylko).

## GENERATED_REPORTS:
`/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-12_GWO-IFG-PURCHASE-INVOICE-NOTIFICATION-INCIDENT.md`
