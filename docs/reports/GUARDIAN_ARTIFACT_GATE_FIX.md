# GUARDIAN_ARTIFACT_GATE_FIX

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Naprawiono błąd implementacyjny `artifact verify local` (`command not found`).
- Źródło komendy zostało przeniesione na jawny wrapper skryptowy w repo:
  - `python3 scripts/ifg_guardian_frontend_artifact_gate.py local`
  - `python3 scripts/ifg_guardian_frontend_artifact_gate.py remote`
- Wrapper istnieje w repo i działa:
  - local: zwraca `ARTIFACT_GATE_STATUS=GO`
  - remote: zwraca `ARTIFACT_GATE_STATUS=GO`
- Routing executorów Guardiana nadal poprawnie rozpoznaje artifact gate (lokalny i zdalny), także dla starej i nowej składni komendy.
- Testy jednostkowe dla artifact gate/executorów: `31 passed`.
- `guardian ifg deploy run --plan` przechodzi i pokazuje nową komendę wrappera w pipeline.

⚠️ ZNANE PROBLEMY
- `guardian ifg deploy run --yes` nadal zatrzymuje się (już nie na artifact gate).
- Aktualny fail dotyczy kroku `dist sync` (rsync/SSH auth), niezależnie od naprawionego artifact gate.

❌ CO NIE DZIAŁA
- LIVE deploy nie kończy się sukcesem z powodu błędu dostępu SSH podczas rsync.

A. ROOT CAUSE
- Poprzedni root cause (naprawiony):
  - pseudo-komenda `ifg_guardian_frontend_artifact_gate ...` zależała od PATH,
  - w LIVE środowisku kończyła się `exit 127` (`command not found`).
- Obecny root cause po naprawie (nowy, poza zakresem tej poprawki):
  - `rsync -av -e "ssh -p 32122" ...` zwraca:
    - `Permission denied, please try again.`
    - `rsync ... child ... exited with status 1`

B. ZMIENIONE PLIKI
- `scripts/ifg_guardian/core/frontend_artifacts.py`
- `scripts/ifg_guardian/core/workflow/executors/router.py`
- `scripts/ifg_guardian_frontend_artifact_gate.py`
- `tests/unit/test_guardian_frontend_artifacts.py`
- `tests/unit/test_guardian_deploy_executors.py`

C. DEPLOY
- Wykonano:
  - `python scripts/guardian.py ifg deploy run --plan` ✅
  - `python scripts/guardian.py ifg deploy run --yes` ❌
- LIVE fail:
  - stage: `simulate_execution`
  - message: `failed 1 step(s)`
  - reprodukcja komendy failing step:
    - `rsync -av -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/`
    - stderr: `Permission denied, please try again.`

D. TESTY
- `PYTHONPATH=scripts pytest tests/unit/test_guardian_frontend_artifacts.py tests/unit/test_guardian_deploy_executors.py`
- Wynik: `31 passed`
- Dodatkowa walidacja wrappera:
  - `python3 scripts/ifg_guardian_frontend_artifact_gate.py local` ✅
  - `python3 scripts/ifg_guardian_frontend_artifact_gate.py remote` ✅

E. NASTĘPNY KROK
- Uzupełnić/naprawić autoryzację SSH dla rsync (ten sam target/port jak w Guardian), następnie ponowić:
  1. `guardian ifg deploy run --yes`
  2. po sukcesie deploy: walidację Monitora KSeF i auto-sync.
