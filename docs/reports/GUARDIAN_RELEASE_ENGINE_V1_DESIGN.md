# GUARDIAN RELEASE ENGINE V1 DESIGN

## CEL

Wprowadzenie warstwy decyzyjnej `guardian release evaluate`, która:
- nie wykonuje deployu,
- nie wykonuje migracji,
- nie modyfikuje środowiska,
- agreguje wyniki istniejących mechanizmów Guardiana,
- wydaje decyzję Release Managera.

## NOWY WORKFLOW

- Komenda CLI: `guardian release evaluate`
- Workflow ID: `ifg.release.evaluate`
- Tryb: tylko read-only (`mutating=False`)
- Zależność: `ifg.doctor` (reuse, bez duplikacji logiki)

Pipeline V1:
1. `init`
2. `doctor_dependency`
3. `git_changes`
4. `deploy_check`
5. `test_discovery`
6. `decision`
7. `summary`

## WYKORZYSTANE ISTNIEJĄCE MECHANIZMY

Release Engine V1 nie replikuje checkerów, tylko konsumuje:
- `ifg.doctor` (w tym: repo audit, frontend build check, docker checks, alembic checks, git/config checks),
- `deploy check` (`run_deploy_check`),
- `pytest --collect-only` jako test discovery,
- `git status --porcelain` do analizy zakresu zmian i impact mapy.

## MODEL DECYZJI

Dostępne statusy:
- `READY_FOR_DEPLOY`
- `READY_WITH_WARNINGS`
- `STAGING_ONLY`
- `PRODUCTION_BLOCKED`

Każda decyzja zawiera:
- status,
- uzasadnienie,
- blockery,
- warningi,
- pozytywne sygnały,
- następny krok,
- deployment recommendation.

## RELEASE SCORE (0-100)

Składowe i wagi:
- repo: 15
- testy: 15
- build: 15
- migracje: 12
- docker: 10
- konfiguracja: 10
- rollback readiness: 13
- dokumentacja: 10

Zasada:
- Każda część ma score 0-100.
- Wynik końcowy = suma ważona.
- Przy FAIL/CRITICAL w checkerach score komponentu spada agresywnie.

## ANALIZA WPŁYWU ZMIAN

Mapowane obszary:
- Backend
- Frontend
- Mobile
- Docker
- DB
- Alembic
- Worker
- KSeF
- Warehouse
- Payments

Poziomy:
- `LOW`
- `MEDIUM`
- `HIGH`

Heurystyka V1:
- analiza ścieżek z `git status --porcelain`,
- podbicie wpływu wg prefixów (`app/`, `frontend-react/`, `alembic/`, `docker/`) i słów kluczowych (`ksef`, `warehouse`, `payment`, `worker`).

## DEPLOYMENT RECOMMENDATION

Przykładowe rekomendacje zwracane przez V1:
- "Deploy możliwy"
- "Deploy możliwy z ostrzeżeniami"
- "Wymagany staging"
- "Deploy zablokowany"

## KOMPATYBILNOŚĆ Z OBECNYM GUARDIANEM

V1 zachowuje kompatybilność:
- nie usuwa `ifg.doctor`,
- nie modyfikuje `ifg.deploy.run`,
- nie modyfikuje `ifg.cutover`,
- działa jako dodatkowy workflow i dodatkowa komenda CLI.

## ROZSZERZALNOŚĆ (V2+)

W CLI dodano placeholdery:
- `guardian release stage`
- `guardian release approve`
- `guardian release production`

Nie są jeszcze zaimplementowane wykonawczo, ale mają przygotowaną ścieżkę rozwoju:
- wspólny model decyzji i scoringu,
- wspólne renderowanie raportu,
- możliwość podpięcia gate approval i policy checks.

## FORMAT RAPORTU (RELEASE MANAGER STYLE)

Raport markdown z `summary` workflow zawiera:
- decyzję i Release Score,
- rationale biznesowo-operacyjne,
- blockery / warningi / positive signals,
- score breakdown per komponent,
- impact matrix,
- deployment recommendation,
- next step.

To celowo raport decyzyjny, a nie surowy log techniczny.

## STATUS

🩷 STATUS KOŃCOWY

✅ Co działa
- Dostępna komenda `guardian release evaluate`.
- Workflow `ifg.release.evaluate` działa read-only i opiera się o istniejące checki.
- Decyzja, score i impact analysis są generowane i renderowane do raportu markdown/json/terminal.
- Architektura jest gotowa pod kolejne kroki `stage/approve/production`.

⚠️ Znane problemy
- `deploy check` może zwrócić warning przy niedostępnym SSH/host, co obniża pewność decyzji.
- Impact analysis V1 jest heurystyczny (na bazie ścieżek), nie semantyczny.

❌ Co nie działa
- Brak implementacji workflow wykonawczych: `release stage/approve/production` (świadomie poza zakresem V1).

A. Root cause
- Brakowało dedykowanej warstwy decyzyjnej; decyzja o deploy była rozproszona między ad-hoc checkami i raportami.

B. Zmienione pliki
- `scripts/ifg_guardian/cli.py`
- `scripts/ifg_guardian/modules/ifg_release_evaluate.py`
- `scripts/ifg_guardian/plugins/ifg/plugin.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/*`
- `scripts/ifg_guardian/core/workflow/transaction.py`
- `tests/unit/test_guardian_ifg_release_evaluate_workflow.py`

C. Deploy
- Nie wykonywano deployu.

D. Testy
- Uruchamiane po implementacji (sekcja wyniku w odpowiedzi końcowej).

E. Następny krok
- Dodać policy gates dla `release stage/approve/production` oraz reguły ręcznej akceptacji dla statusu `READY_WITH_WARNINGS`.
