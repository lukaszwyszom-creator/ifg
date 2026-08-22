# Audyt incydentu: synchronizacja zakupów KSeF — 2026-08-21

**Tryb:** READ-ONLY (bez zmian kodu, restartów, deployu, bez dodatkowej synchronizacji)  
**Host:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`  
**Zakres czasu:** 2026-08-21 00:00–23:59 Europe/Warsaw  
**Data audytu:** 2026-08-22  
**NIP:** 9670402857

---

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Scheduler uruchomił wszystkie 3 sloty 21.08 (08:00 / 14:00 / 20:00) — enqueue + claim joba OK.
- 22.08 08:00: pełne odtworzenie — auth OK, import 1 faktury z datą wystawienia 21.08, mail wysłany.
- Obecnie API / worker / DB healthy; ostatnia udana sync: 22.08 20:00 (`status=ok`, 0 nowych / 1 duplikat).

⚠️ ZNANE PROBLEMY
- 21.08 wszystkie 3 sloty zakończyły się błędem auth KSeF **przed** pobraniem metadanych (brak `PURCHASE_METADATA_FETCH` / XML).
- Retry redeem w IFG obsługuje status auth **450** (SENT), ale **nie** status **100** — przy 100 job pada natychmiast (bez poll/wait).

❌ CO NIE DZIAŁA
- Brak blokującego problemu w bieżącym runtime (po odtworzeniu 22.08).

---

## 1. PODSUMOWANIE SLOTÓW 2026-08-21

| Slot | Scheduler start | Sync start | Sync end | Status końcowy | Metadane | Nowe | Zapisane | Duplikaty | Błędy |
|------|-----------------|------------|----------|----------------|----------|------|----------|-----------|-------|
| **08:00** | 08:00:02 | 08:00:05 | 08:00:08 | **FAILED** (auth) | 0 | 0 | 0 | 0 | 1 (auth) |
| **14:00** | 14:00:04 | 14:00:04 | 14:00:05 | **FAILED** (auth) | 0 | 0 | 0 | 0 | 1 (auth) |
| **20:00** | 20:00:02 | 20:00:02 | 20:00:03 | **FAILED** (auth) | 0 | 0 | 0 | 0 | 1 (auth) |

Okno planowane (log audytu, wszystkie sloty): `date_from=2026-08-18` → `date_to=2026-08-21`, `incremental=True`, `overlap_days=2`, `last_date_to=2026-08-20`.

---

## 2. LIFECYCLE PER SLOT

### 2.1 Slot 08:00

| Element | Wartość |
|---------|---------|
| Scheduler corr | `ec7f0e4c-a836-5706-9245-d27d32c047d7` |
| Sync corr | `17c2735c-96d0-45d9-86fc-15ec180d6ebd` |
| Job | `021b19c7-2e07-47a5-be91-4296e1f2eca6` → **failed**, attempts=1 |
| Start→end | 08:00:05 → 08:00:08 (~2.3 s) |

**Monitor (sync corr):**
1. `PURCHASE_SYNC_AUTO` started / RUNNING  
2. `ERROR` failed / ERROR — redeem 400, exception **21301**, detail: *Status uwierzytelniania (100) nie pozwala na pobranie tokenów*

**Brak:** `SESSION_OPEN/CLOSE`, `PURCHASE_METADATA_FETCH`, `PURCHASE_INVOICE_FETCH`, `PURCHASE_IMPORT_SUMMARY`, `RETRY`, `RESUME`.

**HTTP (worker):** challenge 200 → certs 200 → `auth/ksef-token` 202 → **`auth/token/redeem` 400**.

### 2.2 Slot 14:00

| Element | Wartość |
|---------|---------|
| Scheduler corr | `0e4eaaea-ca77-5895-9aaf-5e4ca8fefc9a` |
| Sync corr | `effc4bb9-6ec3-495e-acbd-beb097d78c7e` |
| Job | `1519c448-f89c-4b2d-b995-19b12fe64492` → **failed**, attempts=1 |
| Start→end | 14:00:04 → 14:00:05 (~0.7 s) |

Identyczny wzorzec: `PURCHASE_SYNC_AUTO` → `ERROR` (21301 / status **100**). Brak fetch/import/resume.

### 2.3 Slot 20:00

| Element | Wartość |
|---------|---------|
| Scheduler corr | `323fba7a-c89b-5794-8ac8-231daf6b1a87` |
| Sync corr | `eb66491f-80ff-4772-8def-5ac981ab8fd1` |
| Job | `fa8955e0-20ca-44ef-afae-31346e08f494` → **failed**, attempts=1 |
| Start→end | 20:00:02 → 20:00:03 (~0.6 s) |

Identyczny wzorzec auth. Brak fetch/import/resume.

Po każdym slocie (~+1 min): `SCHEDULER_SKIP_ALREADY_EXECUTED` (slot oznaczony jako wykonany mimo fail sync — oczekiwane zachowanie schedulera; nie re-enqueue tego samego slotu).

---

## 3. CZEGO NIE BYŁO (wykluczenia)

| Hipoteza | Wynik |
|----------|--------|
| HTTP 429 / rate limit | **Nie** |
| 401/403 API IFG przy sync | **Nie** (auth fail po stronie KSeF redeem) |
| Timeout sieciowy | **Nie** |
| Błąd sesji po otwarciu / XML / FA(3) / DB | **Nie** — sync nie doszedł do tych etapów |
| Retry / defer / resume w obrębie dnia | **Nie** — brak wpisów `RETRY`/`RESUME`; joby `attempts=1` |
| Podwójny scheduler | **Nie** — 1 job na slot; brak `ifg-worker-active` |
| Restart DB | **Nie** |
| Restart workera w trakcie slotów | Worker start **02:26:23** (przed pierwszym slotem); potem bez kolejnych restartów w logach dnia |

API 21.08: typowe healthchecks + skanowanie botów (`/admin/.env`, `/auth/login` 404) — **bez związku** z KSeF sync.

---

## 4. ODTWORZENIE (22.08) — czy ERROR = utrata faktury?

**Nie.** ERROR = fail na bramce auth **przed** pobraniem listy faktur.

### 22.08 08:00 (recovery)

| Pole | Wartość |
|------|---------|
| Job | `cc10295d-e6bd-46f3-925f-57540c42d401` → **done** |
| Corr | `169399ef-6b52-4cfa-975b-2850a444a932` |
| Okno | 2026-08-18 → 2026-08-22 (nadal `last_date_to=2026-08-20` — overlap złapał lukę) |
| Auth redeem | **200 OK** |
| Metadane | unique_refs=**1** (daty page: **20260821**) |
| XML | pobrany 200 |
| Zapisane | **1** |
| Duplikaty / błędy | 0 / 0 |
| incomplete | False |
| Mail | enqueued + sent (recipients=2) |

Faktura w DB:
- `ksef_reference_number`: `8762469751-20260821-7081E8800004-C3`
- `number_local`: `FVF/13105/2026/7`
- `issue_date`: **2026-08-21**
- `created_at`: **2026-08-22 08:00:01 +02**
- Kontrahent (snapshot): GENERON Sp. z o.o. (NIP 8762469751)

### 22.08 14:00 / 20:00

Oba OK: `ksef_returned=1`, `created=0`, `skipped_existing=1` (ten sam numer KSeF) — potwierdza, że w oknie nie ma drugiej „zagubionej” faktury.

### Kontekst przed awarią

20.08 20:00: `PURCHASE_SYNC_AUTO ok`, metadata downloaded=0, saved=0 — czysty sukces przed dniem awarii.

---

## 5. MECHANIZM BŁĘDU (techniczny)

Sekwencja KSeF 2.0 (wszystkie 3 sloty 21.08):

1. `POST /auth/challenge` → 200  
2. `GET /security/public-key-certificates` → 200  
3. `POST /auth/ksef-token` → **202 Accepted**  
4. `POST /auth/token/redeem` → **400**, `exceptionCode=21301`, detail: **Status uwierzytelniania (100)**  

W `app/integrations/ksef/auth.py` `_redeem_tokens` ponawia tylko gdy 21301 **oraz** detail zawiera **„450”** (SENT). Status **100** nie wchodzi w pętlę wait — natychmiastowy `KSeFAuthError` → job failed.

22.08 ta sama ścieżka zakończyła się redeem **200** bez czekania — zjawisko przejściowe po stronie KSeF / race po 202, przy sztywnej obsłudze statusu 100 po stronie IFG.

**Resume:** brak checkpointu (auth fail przed metadata) → brak `RESUME`. Odtworzenie = **kolejny slot auto** z oknem incremental + overlap 2 dni.

---

## 6. STAN BIEŻĄCY (2026-08-22 ~22:40)

| Komponent | Stan |
|-----------|------|
| `ifg-api-1` | Up ~44h, healthy; health `environment=production` |
| `ifg-worker-1` | Up ~44h, healthy; `python -m app.worker` |
| `ifg-db-1` | healthy |
| Dual worker | brak |
| Auto-sync Settings | `True` / `0 8,14,20 * * *` |
| Image label | `e5784651e716…` |
| Scheduler | idle; `last_executed_slot=2026-08-22T20:00`; `last_success=2026-08-22 20:00:01` |
| purchase_invoices | success; last window 2026-08-20→22; counts ok (returned=1, created=0, skipped=1) |

---

## ROOT CAUSE

**Pierwotna:** KSeF `POST /auth/token/redeem` zwracał **400 / exceptionCode 21301** z komunikatem *Status uwierzytelniania (**100**) nie pozwala na pobranie tokenów* — we **wszystkich trzech** slotach 21.08.2026. Synchronizacja padała na bramce uwierzytelnienia, zanim pobrano metadane lub XML.

**Współczynnik IFG:** retry redeem obsługuje asynchroniczny status **450**, ale **nie** status **100**, więc przy 100 brak oczekiwania/poll — natychmiastowy fail joba (bez retry w ramach slotu).

**Nie było przyczyną:** 429, awaria DB, zombie worker w trakcie slotów, podwójny scheduler, błąd FA(3)/XML, ani utrata faktury w połowie importu.

---

## IMPACT

- **Utrata faktur:** **nie** (trwała). Jedyna faktura z okna (`8762469751-20260821-7081E8800004-C3`, issue 21.08) została zapisana **22.08 08:00**.
- **Opóźnienie:** ~12–24 h względem slotów 21.08; mail poszedł przy recovery 22.08 08:00.
- **Self-heal:** tak — następny udany slot auto (overlap od `last_date_to=2026-08-20`) bez ręcznej interwencji.
- **Interwencja teraz:** **nie wymagana** dla danych. Opcjonalny follow-up inżynierski: traktować status auth **100** jak **450** (wait/poll) — poza tym audytem READ-ONLY.

---

## CURRENT STATE

- KSeF purchase sync **działa poprawnie** (22.08: 08/14/20 OK).
- API / worker / DB healthy; jeden worker.
- Ostatnia udana synchronizacja: **2026-08-22 20:00:04** (`ok`, 1 meta, 0 new, 1 skipped).

---

## VERDICT

**DEGRADED_BUT_RECOVERED**

Cały dzień 21.08 był zdegradowany (3/3 sloty auth-fail), ale odtworzenie 22.08 08:00 domknęło lukę danych; brak trwałego DATA_GAP i brak ACTION_REQUIRED dla produkcji.

---

## A. ROOT CAUSE
Jak wyżej (KSeF redeem 21301/status 100 × 3 sloty; IFG nie retry’uje statusu 100).

## B. ZMIENIONE PLIKI
- `docs/reports/2026-08-22_KSEF_PURCHASE_SYNC_2026-08-21_INCIDENT_AUDIT.md` (ten raport)  
- Kod / produkcja: **bez zmian** (READ-ONLY).

## C. DEPLOY
Nie wykonywany.

## D. TESTY / DOWODY
- `transmissions` 21.08: 15 wpisów — wyłącznie SCHEDULER_* + PURCHASE_SYNC_AUTO + ERROR.  
- `background_jobs`: 3× failed 21.08, 3× done 22.08.  
- Worker logs: redeem 400 (21.08) → redeem 200 + saved=1 (22.08 08:00).  
- DB: 1 purchase created 22.08 z `ksef_reference_number` datowanym 20260821.

## E. NASTĘPNY KROK
Brak obowiązkowej interwencji. Opcjonalnie: GWO na hardening redeem (status 100 ≈ 450) — świadomy tech debt, nie blocker.

## TECHNICAL DEBT

- **MEDIUM** — Redeem nie czeka przy auth status **100** (tylko przy **450**). Wartość: mniej fałszywych faili slotów przy asynchronicznym KSeF. Odłożone: zakres audytu READ-ONLY; produkcja już recovered.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-08-22_KSEF_PURCHASE_SYNC_2026-08-21_INCIDENT_AUDIT.md`
