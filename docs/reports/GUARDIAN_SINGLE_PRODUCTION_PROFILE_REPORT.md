# GUARDIAN SINGLE PRODUCTION PROFILE REPORT

## Nowy model polityki

Wprowadzono profile wdrożeniowe w Policy Engine:
- `single_production` (domyślny dla IFG),
- `enterprise`.

Konfiguracja:
- ENV: `GUARDIAN_DEPLOYMENT_PROFILE` (domyślnie `single_production`),
- policy file: `scripts/ifg_guardian/policies/ifg_production.yaml`.

## Różnice: enterprise vs single_production

### single_production (IFG)
- model: `Mac mini -> DS723+ (jedyna produkcja)`,
- brak wymuszania fikcyjnego stagingu,
- dla zmian migracyjnych:
  - `backup_required=true`,
  - `ACTION_REQUIRED` (backup/migration/rebuild),
  - bez automatycznego `STAGING_ONLY`.

### enterprise
- model: `Release Evaluate -> Staging -> Production`,
- zachowana logika wymuszania `STAGING_ONLY` gdy staging jest wymagany/dostępny.

## Zmiana semantyki reguły migracji

Dla `single_production`:
- zamiast `alembic_changes_require_staging` działa:
  - `critical_db_change_requires_verified_backup`.

Efekt:
- migracje i krytyczne tabele (`invoices`, `transmissions`, `warehouse_layers`, `payments`) ustawiają wymagany backup,
- nie wymuszają automatycznie etapu `STAGING_ONLY` w profilu IFG.

## Wynik `guardian release evaluate`

Uruchomienie:
- `GUARDIAN_DEPLOYMENT_PROFILE=single_production python scripts/guardian.py release evaluate --markdown`

Wynik:
- Decision: `READY_WITH_WARNINGS`
- Deployment Profile: `single_production`
- Backup Required: `True`
- Staging Required: `False`
- Production Blocked: `False`

Rules triggered:
- `migration_change_requires_controlled_deploy`
- `critical_db_change_requires_verified_backup`
- `backend_change_requires_api_worker_rebuild`
- `untracked_files_warn`
- `doctor_fail_warn_single_production`

ACTION_REQUIRED:
- backup DB,
- migracja w kontrolowanym deploy pipeline,
- rebuild api/worker,
- weryfikacja untracked files.

## Decyzja Policy Engine

Policy Engine dla IFG (single_production) zwraca decyzję zgodną z realnym modelem operacyjnym:
- brak fikcyjnego `STAGING_ONLY`,
- deploy możliwy z ostrzeżeniami i listą obowiązkowych akcji.

## Potwierdzenie dla IFG

IFG może być wdrażany bez nieistniejącego etapu staging, pod warunkiem:
- zweryfikowanego backupu,
- wykonania wymaganych akcji deploy pipeline (rebuild/migration),
- braku realnych blockerów bezpieczeństwa.
