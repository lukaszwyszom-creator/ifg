# KSEF_MONITOR_GUARDIAN_PRE_DEPLOY_AUDIT

Data: 2026-07-07  
Tryb: pre-deploy audit (read-only), bez zmian runtime i bez deployu.

## 1) Uruchomienie workflow przez Guardiana

Uruchomiono:

```bash
python3 scripts/guardian.py ifg doctor --dry-run --markdown --report docs/reports/KSEF_MONITOR_GUARDIAN_PRE_DEPLOY_AUDIT_DOCTOR.md
```

Wynik workflow: **BLOCKED** (3 FAIL, 9 WARN, 14 PASS).  
Główne blokery z Guardiana:
- `backend changes` (18 backend/alembic change(s)),
- `build required`,
- `compose config` (lokalnie brak `.env.production`).

To jest oczekiwane dla lokalnego audytu przed deployem.

## 2) Git status --short

Wykonano `git status --short`.  
W drzewie roboczym są zmiany tracked + liczne pliki untracked.

Najważniejsze pliki związane z KSeF Monitor (tracked/untracked):
- `alembic/versions/a9b1c2d3e4f5_ksef_monitor_transmissions_unified.py`
- `app/persistence/models/transmission.py`
- `app/domain/enums.py`
- `app/services/ksef_transmission_journal_service.py`
- `app/services/transmission_service.py`
- `app/services/ksef_session_service.py`
- `app/worker/job_handlers/submit_invoice.py`
- `app/worker/job_handlers/poll_ksef_status.py`
- `app/api/routers/transmissions.py`
- `app/schemas/transmission.py`
- `app/core/config.py`
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
- `frontend-react/src/components/dashboard/TransmissionTable.module.css`
- `frontend-react/src/components/common/StatusBadge.jsx`
- `frontend-react/src/pages/advanced/AdvancedDashboard.jsx`
- `frontend-react/src/api/transmissions.js`

## 3) git diff --stat

Wykonano `git diff --stat`.  
Dla całości working tree: **25 files changed, 3087 insertions(+), 2668 deletions(-)**.

## 4) Lista zmienionych plików

Wykonano `git diff --name-only`.  
Wynik zawiera 25 plików tracked (pełna lista z polecenia), z czego rdzeń KSeF Monitor wskazany w sekcji 2.

## 5) Kontrola migracji Alembic dla transmissions

Sprawdzono plik:
- `alembic/versions/a9b1c2d3e4f5_ksef_monitor_transmissions_unified.py`

Potwierdzone:
- dodane kolumny: `severity`, `correlation_id` (UUID), `job_id` (UUID), `metadata_json` (JSONB),
- backfill `operation_type` do `SALE_SEND` dla legacy (`submit`, `invoice_submit`, null/empty),
- backfill `severity` z mapowaniem po statusie,
- backfill `correlation_id = COALESCE(invoice_id, id)`,
- `invoice_id` ustawione na nullable,
- `idempotency_key` ustawione na nullable,
- indeksy dla `correlation_id`, `job_id`, `severity`, oraz `(correlation_id, created_at)`.

## 6) Weryfikacja modelu transmissions

Sprawdzono `app/persistence/models/transmission.py`.

Potwierdzone:
- `invoice_id: UUID | None` (nullable),
- `operation_type` obecne,
- `severity` obecne,
- `correlation_id` jako `UUID(as_uuid=True)`,
- `job_id` jako `UUID(as_uuid=True), nullable=True`,
- `metadata_json` jako `JSONB, nullable=True`,
- `idempotency_key` jako nullable.

## 7) Kontrola operation_type

Sprawdzono `app/domain/enums.py`.

Potwierdzone typy:
- `SALE_SEND`
- `SALE_STATUS`
- `UPO_DOWNLOAD`
- `SESSION_OPEN`
- `SESSION_CLOSE`
- `SESSION_REFRESH`
- `SESSION_EXPIRED`
- `SESSION_RENEWED`
- `PURCHASE_SYNC_MANUAL`
- `PURCHASE_SYNC_AUTO`
- `PURCHASE_METADATA_FETCH`
- `PURCHASE_INVOICE_FETCH`
- `PURCHASE_IMPORT_SUMMARY`
- `RETRY`
- `RESUME`
- `ERROR`

## 8) Kontrola zmian UI „Monitor KSeF”

Sprawdzono frontend:
- `frontend-react/src/pages/advanced/AdvancedDashboard.jsx`
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
- `frontend-react/src/components/dashboard/TransmissionTable.module.css`
- `frontend-react/src/components/common/StatusBadge.jsx`
- `frontend-react/src/api/transmissions.js`

Potwierdzone:
- nazwa zakładki: **Monitor KSeF**,
- tabela dziennika operacji (`operation_type`, `severity`, `job_id`, `correlation_id`, `metadata_json`),
- filtr **„Tylko błędy i ostrzeżenia”**,
- liczniki (`Sukcesy/Ostrzeżenia/Błędy/W toku`),
- rozwijane szczegóły `metadata_json`,
- kompatybilność z wpisami sprzedażowymi zachowana.

## 9) Testy backendu

Uruchomiono:

```bash
python3 -m pytest tests/unit/test_transmission_service.py tests/unit/test_transmission_api.py tests/unit/test_submit_invoice_handler.py tests/unit/test_poll_ksef_status_handler.py tests/unit/test_ksef_purchase_sync_resume.py -q
```

Wynik: **84 passed**.

## 10) Build frontendu

Uruchomiono:

```bash
cd frontend-react && npm run build
```

Wynik: **SUCCESS** (vite build zakończony poprawnie).  
Uwaga: ostrzeżenie o dużym chunku (`>500 kB`) — nie blokuje builda.

## 11) Ocena ryzyka deployu

### Ocena ogólna: **MEDIUM**

Powody:
- zmiana schematu DB (`transmissions`) + backfill (ryzyko migracyjne),
- zmiana semantyki tabeli (z czysto sprzedażowej na unified journal),
- ingerencja w ścieżki krytyczne KSeF (submit/poll/session/sync).

### Czynniki obniżające ryzyko
- brak nowej tabeli i zachowanie kompatybilności istniejącego flow sprzedaży,
- testy backendowe dla kluczowych handlerów i API: PASS,
- frontend build: PASS,
- migracja ma logiczny backfill i indeksy pod query.

### Rekomendacje przed deployem
1. Wykonać migrację na stagingu z kopią produkcyjnych danych.
2. Zweryfikować czas migracji i lockowanie tabeli `transmissions`.
3. Sprawdzić endpointy `/transmissions` i dashboard Monitor KSeF na danych historycznych.
4. Przygotować rollback plan dla migracji (downgrade i/lub snapshot DB).

---

Wniosek: implementacja KSeF Monitor jest technicznie gotowa do etapu staging/pre-prod, ale zgodnie z wynikiem workflow Guardiana i charakterem zmian DB nie należy wykonywać produkcyjnego deployu bez pełnego okna wdrożeniowego i walidacji migracji.

