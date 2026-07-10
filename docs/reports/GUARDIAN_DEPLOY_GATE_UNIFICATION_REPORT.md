# GUARDIAN DEPLOY GATE UNIFICATION REPORT

## Opis przyczyny

W Guardian v1 występowały dwa niezależne gate'y deploymentowe:

1. `guardian release evaluate` (Policy Engine) -> decyzja `READY_WITH_WARNINGS`
2. `guardian ifg deploy run` -> ponowna interpretacja `ifg.release.plan`/`doctor` -> blokada przez `doctor BLOCKED` i `risk CRITICAL`

To powodowało niespójność: deploy był formalnie dopuszczony przez Policy Engine, ale zatrzymywany przez drugi gate w deploy workflow.

## Zmienione miejsca

- `scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py`
  - dodana zależność `ifg.release.evaluate` obok `ifg.release.plan`,
  - dodany etap `ReleaseEvaluateStage`.

- `scripts/ifg_guardian/plugins/ifg/deploy_run/service.py`
  - dodane odczytywanie snapshotu dependency `ifg.release.evaluate`.

- `scripts/ifg_guardian/plugins/ifg/deploy_run/stages.py`
  - `BlockerStage` używa decyzji z `release evaluate` jako jedynego źródła gate,
  - `doctor/release_plan` służy tylko do faktów/pipeline, nie do ponownego gate decision,
  - `ACTION_REQUIRED` z Policy Engine trafia do warnings deploy planu.

- `scripts/ifg_guardian/plugins/ifg/deploy_run/models.py`
  - dodane pola `release_evaluate_workflow_id` i `release_decision`.

- `scripts/ifg_guardian/plugins/ifg/deploy_run/report.py`
  - raport deploy pokazuje workflow `release evaluate` i `release_decision`,
  - exit code deploy nie blokuje już wyłącznie na `deployment_risk=CRITICAL`; blokuje tylko przy realnych blockerach/fail step.

- `scripts/ifg_guardian/cli.py`
  - dodany `--plan` jako alias `--dry-run` dla `guardian ifg deploy run`.

- `tests/unit/test_guardian_ifg_deploy_run_workflow.py`
  - aktualizacja testów pod nowe dependency i nowe źródło gate decision.

## Nowy przepływ decyzji

Jedno źródło decyzji deploymentowej:

`release evaluate` -> `Policy Engine` -> decyzja (`READY_*` / `STAGING_ONLY` / `PRODUCTION_BLOCKED`) -> `ifg deploy run`

`ifg deploy run`:
- nie reinterpretuje już decyzji z doctora,
- respektuje `release_decision`,
- przechodzi do listy `ACTION_REQUIRED`, gdy decyzja jest dopuszczająca (`READY_FOR_DEPLOY` / `READY_WITH_WARNINGS`).

Doctor pozostaje źródłem faktów.

## Wynik `guardian release evaluate`

Uruchomienie:
- `python scripts/guardian.py release evaluate --markdown`

Wynik:
- `Decision: READY_WITH_WARNINGS`
- `Deployment Profile: single_production`
- `Blockers: None`
- `Production Blocked: False`

## Wynik `guardian ifg deploy run --plan`

Uruchomienie:
- `python scripts/guardian.py ifg deploy run --plan --markdown`

Wynik:
- plan zakończony sukcesem (`exit code 0`),
- `Release decision: READY_WITH_WARNINGS`,
- `blockers: 0`,
- pipeline przeszedł do listy `ACTION_REQUIRED` (backup/rebuild/migration/untracked review),
- brak ponownej blokady na `doctor BLOCKED`.

## Potwierdzenie jednego deployment gate

Potwierdzone:
- deployment gate jest jednolity i oparty o Policy Engine (`release evaluate`),
- deploy run korzysta z tej decyzji zamiast tworzyć drugi niezależny gate.
