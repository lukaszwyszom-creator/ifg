# GWO-IFG-0033 — Deploy Ready (final polish GWO-IFG-0032)

**Data:** 2026-07-07  
**Status:** polish zakończony — deploy **nie wykonano**

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Fail-fast workera przy `KSEF_AUTO_SYNC_ENABLED=true` bez `KSEF_AUTH_TOKEN`.
- `refresh_valid_until` zachowywane przy refresh bez daty w odpowiedzi API.
- **193 testów** KSeF-related — wszystkie przechodzą.
- Guardian `ksef check` — **GREEN** (exit 0).

### ⚠️ Znane problemy

- Guardian `doctor` — **BLOCKED** (dirty working tree, `backend.changes` FAIL, `build required` FAIL) — stan oczekiwany przed commitem i rebuildem obrazów.
- SSH `/health` na DS723+ niedostępny z lokalnego środowiska (WARN).

### ❌ Co nie działa

- Brak regresji w testach KSeF po zmianach GWO-IFG-0033.

---

## Wykonane zmiany

### 1. Fail-fast `KSEF_AUTH_TOKEN` (worker)

W `app/worker/__main__.py::main()` przed pętlą workera:

```python
if settings.ksef_auto_sync_enabled and not (settings.ksef_auth_token or "").strip():
    raise SystemExit(
        "KSEF_AUTO_SYNC_ENABLED=true wymaga KSEF_AUTH_TOKEN w ENV workera."
    )
```

- Minimalna zmiana (4 linie).
- Nie blokuje dev (`KSEF_AUTO_SYNC_ENABLED` domyślnie `false`).
- Worker kończy się z `SystemExit` i jednoznacznym komunikatem.

### 2. Zachowanie `refresh_valid_until`

W `app/services/ksef_token_store.py::build_token_metadata()`:

- Gdy `refresh_valid_until is not None` → zapis nowej daty (bez zmian).
- Gdy `refresh_valid_until is None` i `existing` podane → **zachowanie** wartości z `existing`.
- Gdy brak `existing` → `null` (jak dotąd przy pełnej autoryzacji).

Logika access tokenów **niezmieniona**.

---

## Zmodyfikowane / nowe pliki

| Plik | Zmiana |
|------|--------|
| `app/worker/__main__.py` | Fail-fast ENV |
| `app/services/ksef_token_store.py` | Preserve `refresh_valid_until` |
| `tests/unit/test_ksef_token_store.py` | **NOWY** — 3 testy metadata |
| `tests/unit/test_worker_startup_validation.py` | **NOWY** — 2 testy startu workera |

---

## Wynik testów

```bash
python -m pytest \
  tests/unit/test_ksef_purchase_auth_service.py \
  tests/unit/test_ksef_session_service.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_ksef_poll_session_lookup.py \
  tests/unit/test_ksef_session_worker.py \
  tests/unit/test_ksef_auto_sync_scheduler.py \
  tests/unit/test_ksef_token_store.py \
  tests/unit/test_worker_startup_validation.py \
  tests/unit/test_background_job_claim.py \
  tests/unit/test_ksef_auth_redeem_timeout.py \
  tests/unit/test_ksef_domain_improvements.py \
  tests/unit/test_ksef_hardening.py -q
```

**Wynik: 193 passed in 0.60s**

Nowe testy:

- `test_build_token_metadata_preserves_refresh_valid_until_on_refresh`
- `test_main_exits_when_auto_sync_enabled_without_auth_token`
- `test_main_does_not_exit_when_auto_sync_disabled_without_token`

---

## Wynik Guardian

| Gate | Komenda | Status | Exit |
|------|---------|--------|------|
| **KSeF check** | `python scripts/guardian.py ksef check` | **GREEN** | 0 |
| **IFG Doctor** | `python scripts/guardian.py doctor` | **BLOCKED** | 1 |

### KSeF check (GREEN)

Wszystkie 11 punktów OK (frontend sync API, dist, openapi endpoint).

### IFG Doctor (BLOCKED — proces deploy, nie kod)

Przyczyny BLOCKED:

| Check | Status | Uzasadnienie |
|-------|--------|--------------|
| `backend.changes` | FAIL | Niezcommitowane zmiany backend (GWO-IFG-0032/0033) |
| `backend.build_required` | FAIL | Wymagany rebuild api/worker przed deployem |
| `env.git_status` | WARN | Dirty working tree |
| `/health` | WARN | Brak SSH do DS723+ lokalnie |

**Nie wynika to z regresji GWO-IFG-0033** — doctor blokuje deploy przy niezcommitowanych zmianach backendu (zamierzone zachowanie gate).

---

## Ocena ryzyka

| Ryzyko | Poziom | Komentarz |
|--------|--------|-----------|
| Brak `KSEF_AUTH_TOKEN` przy auto-sync | **Niskie** | Fail-fast przy starcie workera |
| Utrata `refresh_valid_until` | **Niskie** | Naprawione w `build_token_metadata` |
| Regresja sprzedaży KSeF | **Niskie** | Testy session/worker/poll bez zmian semantycznych |
| Deploy bez rebuild | **Średnie** | Doctor wymaga rebuild — standardowy krok przed prod |

---

## Decyzja

# **READY FOR DEPLOY**

**Uzasadnienie:**

1. Wszystkie poprawki z Final Review (GWO-IFG-0033) zaimplementowane.
2. 193 testów KSeF — green, brak regresji.
3. Guardian KSeF check — green.
4. Architektura GWO-IFG-0032 bez zmian.

**Warunki operacyjne przed faktycznym deployem:**

1. Commit zmian GWO-IFG-0032 + GWO-IFG-0033.
2. Rebuild i deploy obrazów `api` + `worker`.
3. Potwierdzenie `KSEF_AUTH_TOKEN` w ENV workera produkcyjnego.
4. Ponowne uruchomienie `guardian.py doctor` po commit — oczekiwany status `READY` lub `READY_WITH_WARNINGS`.

---

## A. Root cause (polish)

Final Review wskazał late-failure ENV oraz zerowanie `refresh_valid_until` — oba usunięte minimalnymi zmianami.

## B. Deploy

**Nie wykonano.**

## C. Testy

193 passed — dowód powyżej.

## D. Następny krok

Commit → rebuild api/worker → deploy DS723+ → obserwacja pierwszego slotu schedulera.

---

## Lista wykonanych analiz

1. Implementacja fail-fast w `app/worker/__main__.py`.
2. Analiza przepływu `build_token_metadata` w `_refresh_tokens` / `PurchaseAuthService`.
3. Uruchomienie pełnego zestawu testów KSeF (purchase auth, scheduler, worker, sync, session).
4. Guardian `ksef check`.
5. Guardian `ifg doctor` (gate deploy).
6. Weryfikacja braku zmian w logice access tokenów.

## Lista wykonanych raportów (sesja GWO-IFG-0032/0033)

| Raport | Ścieżka |
|--------|---------|
| Audyt session dependency | `docs/reports/2026-07-07_KSEF_AUTO_SYNC_SESSION_DEPENDENCY_AUDIT.md` |
| Design refaktoru | `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_REFACTOR_DESIGN.md` |
| Final review | `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_FINAL_REVIEW.md` |
| **Deploy ready (ten dokument)** | `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_DEPLOY_READY.md` |

Dokumentacja architektury: `docs/architecture/KSEF_PURCHASE_AUTH.md`, `docs/architecture/KSEF_SCHEDULER.md`.
