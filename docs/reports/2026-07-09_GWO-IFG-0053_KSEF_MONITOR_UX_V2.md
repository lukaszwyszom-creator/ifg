# GWO-IFG-0053 — Monitor KSeF UX v2 (statusy, kontrahenci, daty, podsumowania)

**Data:** 2026-07-09  
**Status:** DONE (implementacja + testy; deploy nie wykonano w tym zadaniu)

---

## Root cause problemu statusów „W TOKU”

### Diagnostyka (kolejność)

1. **Analiza produkcyjna** — pobrano 85 rekordów z `GET /api/v1/transmissions/` na DS723+.
2. **Symulacja starej logiki** `aggregateGroupStatus()` na 40 grupach procesów.
3. **Analiza chronologiczna** grup oznaczonych jako „W TOKU”.

### Wynik diagnostyki

| Warstwa | Udział w problemie | Opis |
|---------|-------------------|------|
| **Frontend (główna przyczyna)** | ~70% | `aggregateGroupStatus()` traktował jako „W TOKU” **każdy** wiersz ze `status ∉ {success, failed_permanent}`. Journal KSeF używa statusów: `ok`, `summary`, `skipped`, `refreshed`, `enqueued`, `started`, `slot_due` itd. |
| **Dane / backend (wtórna przyczyna)** | ~30% | Journal zapisuje wiele wierszy na proces bez zamykania wcześniejszych wpisów RUNNING (np. `PURCHASE_SYNC_AUTO started RUNNING` pozostaje, gdy później pojawia się `ok SUCCESS`). |

### Dowód (produkcja, przed poprawką)

```
=== OLD aggregateGroupStatus on prod groups ===
20 SUKCES
11 BŁĄD
7 W TOKU      ← błędnie
2 OSTRZEŻENIE

=== SAMPLE PURCHASE GROUP (chronologiczny) ===
PURCHASE_SYNC_AUTO started RUNNING
PURCHASE_METADATA_FETCH success INFO
PURCHASE_IMPORT_SUMMARY summary INFO
PURCHASE_SYNC_AUTO ok SUCCESS
→ STARA LOGIKA: W TOKU
→ NOWA LOGIKA: success (✔ Sukces)
```

**Wniosek:** Problem nie leżał wyłącznie po stronie frontendu ani wyłącznie po stronie backendu — wymagał poprawki agregacji frontendowej z uwzględnieniem semantyki journal KSeF oraz ignorowania „starych” wpisów RUNNING, gdy proces ma już etapy SUCCESS.

---

## Opis zmian

### 1. Status procesu

- Przepisano `aggregateGroupStatus()`:
  - **W TOKU** tylko dla: `queued`, `processing`, `submitted`, `waiting_status` lub `severity=RUNNING` (z wyjątkiem „starych” `started`/`slot_due` gdy grupa ma już SUCCESS).
  - **SUKCES** dla: `success`, `ok`, `summary`, `refreshed`, `renewed`, `severity=SUCCESS`.
  - **OSTRZEŻENIE** / **BŁĄD** — bez zmian semantyki, poprawiona kolejność.
- Etykiety operatora: `✔ Sukces`, `⚠ Ostrzeżenia`, `✖ Błąd`, `◌ W toku`.

### 2. Tooltip faktury

- Backend: nowe pole `invoice_snapshot` w `TransmissionResponse` (bez dodatkowych requestów przy hover).
- Dane: numer, kontrahent (nabywca/sprzedawca), NIP, kwota brutto, data, numer KSeF, status, kierunek.
- Frontend: `buildInvoiceSnapshot()` preferuje `invoice_snapshot` z API.

### 3. Data i czas

- Nowa funkcja `formatDateTimeWithWeekday()` — format:
  ```
  08.07.2026 (środa)
  14:00
  ```
- Dzień tygodnia słownie po polsku.
- Kolumna „Czas” w widoku grup i etapy w szczegółach używają nowego formatu.

### 4. Podsumowanie procesu

- `buildProcessSummaryMeta()` — zwinięty wiersz pokazuje efekt (np. „12 nowych faktur”, numer FV, UPO, czas).
- `buildSummaryLines()` — rozwinięte podsumowanie z ikonami statusu i czasem trwania.
- `summarizeGroup()` — `purchaseSaved` z `metadata_json.saved`.

### 5. Rozwijany widok

- **Bez zmian** w zakresie diagnostyki technicznej: correlation, job, retry, severity, metadata, błędy — pełny `TransmissionDetails`.

---

## Zmodyfikowane pliki

### Frontend

| Plik | Zmiana |
|------|--------|
| `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js` | Agregacja statusów, daty, snapshot, podsumowania |
| `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js` | 15 testów (statusy prod., daty, snapshot, podsumowania) |
| `frontend-react/src/components/dashboard/transmissions/TransmissionGroup.jsx` | Status z ikoną, data, meta efektu |
| `frontend-react/src/components/dashboard/transmissions/TransmissionSummary.jsx` | `buildSummaryLines()` |
| `frontend-react/src/components/dashboard/transmissions/TransmissionInvoiceTooltip.jsx` | Pełniejszy tooltip |
| `frontend-react/src/components/dashboard/transmissions/TransmissionDetails.jsx` | Data w etapach |
| `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css` | Szersza kolumna czasu, `pre-line` |

### Backend

| Plik | Zmiana |
|------|--------|
| `app/schemas/transmission.py` | `TransmissionInvoiceSnapshot`, pole `invoice_snapshot` |
| `app/api/routers/transmissions.py` | `_build_invoice_snapshot()`, mapowanie w `_transmission_to_response()` |
| `tests/unit/test_transmission_api.py` | Test `invoice_snapshot` w liście transmisji |

---

## Zmiany backend/API

### Nowy model: `TransmissionInvoiceSnapshot`

```json
{
  "number": "FV/2026/001",
  "counterparty_name": "Nabywca SA",
  "counterparty_nip": "2222222222",
  "gross_total": "1230.00",
  "currency": "PLN",
  "issue_date": "2026-07-01",
  "ksef_reference_number": "KSeF-2026-001",
  "status": "accepted",
  "direction": "sale"
}
```

- Wypełniane z `joinedload(TransmissionORM.invoice)` — **zero dodatkowych zapytań** przy hover.
- `null` gdy `invoice_id` jest puste (wpisy journal bez faktury).
- Dla zakupów: kontrahent = `seller_snapshot` (sprzedawca).

**Kompatybilność wsteczna:** pole opcjonalne, istniejący kontrakt API rozszerzony (additive).

---

## Wyniki testów

```bash
node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js
# 15/15 PASS

.venv/bin/python -m pytest tests/unit/test_transmission_api.py::TestListTransmissions -q
# 2/2 PASS

cd frontend-react && npm run build
# SUCCESS
```

### Kluczowe przypadki testowe

| Scenariusz | Wynik |
|------------|-------|
| Sync zakupów ze `started RUNNING` + `ok SUCCESS` | `success` ✔ |
| Sesja KSeF `refreshed` | `success` ✔ |
| Scheduler `skipped` + `slot_due RUNNING` | nie `running` ✔ |
| Worker `waiting_status` | `running` ✔ |
| `invoice_snapshot` z API | tooltip kompletny ✔ |
| Data + dzień tygodnia PL | ✔ |

---

## Ograniczenia

| Ograniczenie | Opis |
|--------------|------|
| Tooltip bez `invoice_id` | Wpisy journal (sync zakupów bez powiązanej faktury) — tooltip nadal ograniczony do metadanych |
| Stare wpisy RUNNING w DB | Nie usuwane — frontend je ignoruje przy agregacji, backend nadal je zapisuje |
| Grupowanie per strona | 20 wpisów na stronę (bez zmian od GWO-0051) |
| Deploy | Zmiany lokalne — wymagany deploy Guardian dla produkcji |

---

## Propozycje dalszego rozwoju

1. **Backend:** zamykać wpis `started RUNNING` przez ustawienie `finished_at` przy zapisie `ok SUCCESS` (journal service).
2. **API:** opcjonalny `process_status` agregowany po stronie backendu dla spójności wszystkich klientów.
3. **Zakupy:** `invoice_snapshot` z metadanych importu dla faktur bez `invoice_id` w transmission.
4. **UI:** wskaźnik „dziś / wczoraj” obok daty dla szybszej orientacji czasowej.

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIAŁA

- Diagnostyka root cause udokumentowana (frontend + dane journal)
- Poprawiona agregacja statusów (prod. scenariusze: purchase/session/scheduler)
- Tooltip z `invoice_snapshot` (backend + frontend)
- Data z dniem tygodnia PL
- Bogatsze podsumowania procesu
- Pełna diagnostyka techniczna zachowana
- 15/15 testów frontend + 2/2 API + build PASS

### ⚠️ ZNANE PROBLEMY

- Wymaga deployu na produkcję (frontend + rebuild API dla `invoice_snapshot`)

### ❌ CO NIE DZIAŁA

- Brak (w zakresie implementacji lokalnej)

## A. ROOT CAUSE

Stara agregacja traktowała statusy journal (`summary`, `ok`, `skipped`) jako aktywne; dodatkowo nieaktualne wpisy RUNNING w danych wzmacniały błąd.

## B. ZMIENIONE PLIKI

Patrz sekcja „Zmodyfikowane pliki”.

## C. DEPLOY

Nie wykonano — do uruchomienia przez Guardian (`ifg deploy run`).

## D. TESTY

15/15 frontend, 2/2 API, build OK.

## E. NASTĘPNY KROK

Deploy produkcyjny GWO-IFG-0053; opcjonalnie backendowy fix zamykania wpisów RUNNING w journal.

---

## Lista wygenerowanych raportów `.md`

1. `docs/reports/2026-07-09_GWO-IFG-0053_KSEF_MONITOR_UX_V2.md`
