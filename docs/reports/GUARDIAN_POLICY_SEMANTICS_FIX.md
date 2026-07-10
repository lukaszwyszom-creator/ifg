# GUARDIAN POLICY SEMANTICS FIX

## CEL

Poprawa semantyki Policy Engine:
- `PRODUCTION_BLOCKED` tylko dla realnych blockerów bezpieczeństwa/deployu,
- zmiany typu backend/frontend/rebuild/migration jako `ACTION_REQUIRED`, nie blocker.

## ZAKRES ZMIAN (MINIMALNY)

Bez dodawania workflow i bez dodawania nowych funkcji.

Zmodyfikowane miejsca:
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`

## CO ZMIENIONO

1. **Doctor FAIL/CRITICAL nie trafia automatycznie do listy blockerów**
- wcześniej każde `FAIL/CRITICAL` było wpisywane do `blockers`,
- teraz trafia do `warnings`, a o blokadzie decyduje policy.

2. **Policy Engine jest finalnym deciderem niezależnie od score**
- decyzja startuje od `READY_FOR_DEPLOY`,
- score pozostaje informacją pomocniczą,
- usunięto wpływ wcześniejszego score-based `make_decision` na finalną decyzję.

3. **Backend/frontend/rebuild/migration = ACTION_REQUIRED**
- `backend_change_requires_api_worker_rebuild` dodaje wymagane akcje, ale nie blokuje deployu,
- `alembic_changes_require_staging` i `critical_table_migration_requires_backup` ustawiają staging/backup requirements (nie `PRODUCTION_BLOCKED`).

4. **Realne blockery pozostają blockerami**
- `tests_must_pass`,
- `frontend_change_requires_passing_build` (gdy FE changed i build FAIL/CRITICAL),
- `suspicious_untracked_files_block`,
- `doctor_critical_fail_blocks_production`,
- twarde checki doctor (`repo.deploy_blockers`, `config.required_vars`, `docker.compose_config`, `docker.containers`, `health.endpoint`) przy `FAIL/CRITICAL`.

## WYNIK `guardian release evaluate` PO ZMIANIE

- Decyzja: `STAGING_ONLY`
- Release Score: `88/100`
- `Production Blocked`: `False`
- `Blockers`: `None`
- `Policy Rules Triggered`:
  - `alembic_changes_require_staging`
  - `critical_table_migration_requires_backup`
  - `backend_change_requires_api_worker_rebuild`
  - `untracked_files_warn`
  - `doctor_fail_requires_staging`

Interpretacja:
- Semantyka jest zgodna z celem: backend/build-required nie blokują już produkcji jako blocker.
- Stan projektu wymaga stagingu i listy działań (`ACTION_REQUIRED`) przed produkcją.

## STATUS

🩷 STATUS KOŃCOWY

✅ Co działa
- Poprawiona klasyfikacja decyzji Policy Engine zgodnie z definicją blocker vs action_required.
- `release evaluate` odzwierciedla realny stan projektu bez sztucznej blokady.

⚠️ Znane problemy
- Nadal są warningi środowiskowe (dirty repo, local alembic env), które nie są traktowane jako hard blocker.

❌ Co nie działa
- Brak.

A. Root cause
- Dotychczasowa klasyfikacja traktowała każde backend `FAIL` z doctor jako blocker.

B. Zmienione pliki
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`

C. Deploy
- Nie wykonywano deployu.

D. Testy
- `pytest tests/unit/test_guardian_ifg_release_evaluate_workflow.py -q` -> 6 passed
- `python scripts/guardian.py release evaluate --markdown` -> decyzja `STAGING_ONLY`

E. Następny krok
- Wykonać wymagane akcje ze staging checklisty i ponowić `release evaluate`.
