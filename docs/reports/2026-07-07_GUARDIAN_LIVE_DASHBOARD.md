# Raport implementacji: Guardian Live Dashboard (TUI)

**Data:** 2026-07-07  
**Zakres:** TUI nad Guardian Progress Protocol  
**Deploy IFG:** nie wykonywano

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Pełnoekranowy dashboard (`--dashboard`) oparty na **Rich Live** (odświeżanie 1 Hz)
- Przechwytywanie `[GWO_PROGRESS]` przez `ProgressStderrSink` — bez zmian `ProgressTracker` / `ExecutionEngine`
- Model `DashboardState`: pasek postępu, spinner, ETA, elapsed, fazy, heartbeat, historia 20 zdarzeń
- Tryby: `--progress` (dotychczasowy), `--dashboard` (TUI), `--no-progress` (cisza)
- Po zamknięciu dashboardu — standardowy raport Guardian na stdout
- Kolory Rich (status, fazy, panel)
- Testy jednostkowe modelu/parsera/renderera
- Dokumentacja: `docs/architecture/GUARDIAN_LIVE_DASHBOARD.md`

### ⚠️ Znane problemy

- Wymaga pakietu `rich` (`pip install rich` lub `.[guardian]`)
- ETA jest liniowa (step/total) — przy nierównych etapach może być niedokładna
- Fazy spoza `DEPLOY_PHASES` (np. doctor `environment`) nie pojawiają się na liście etapów deployu

### ❌ Co nie działa

- Brak w zakresie tego zadania

---

## A. Root cause

Surowe linie `[GWO_PROGRESS]` są czytelne, ale przy deployu 10+ minut użytkownik potrzebuje jednego ekranu ze stanem — jak btop/k9s.

## B. Zmienione / nowe pliki

**Nowe:**

- `scripts/ifg_guardian/core/dashboard/parser.py`
- `scripts/ifg_guardian/core/dashboard/model.py`
- `scripts/ifg_guardian/core/dashboard/eta.py`
- `scripts/ifg_guardian/core/dashboard/renderer.py`
- `scripts/ifg_guardian/core/dashboard/stderr_sink.py`
- `scripts/ifg_guardian/core/dashboard/session.py`
- `scripts/ifg_guardian/core/dashboard/__init__.py`
- `tests/unit/test_guardian_live_dashboard.py`
- `docs/architecture/GUARDIAN_LIVE_DASHBOARD.md`

**Zmodyfikowane:**

- `scripts/ifg_guardian/cli.py` — `--dashboard`, `_run_with_display()`
- `pyproject.toml` — opcjonalna zależność `rich` (grupy `dev`, `guardian`)

**Bez zmian (zgodnie z wymaganiem):**

- `ProgressTracker`, `ExecutionEngine`, logika workflow

## C. Deploy

Nie wykonywano.

## D. Testy

```bash
pip install 'rich>=13.7,<14.0'
pytest tests/unit/test_guardian_live_dashboard.py -q
pytest tests/unit/test_guardian_progress_protocol.py -q
```

## E. Następny krok

```bash
# TUI podczas dry-run deploy
python scripts/guardian.py ifg deploy run --dry-run --dashboard

# Klasyczne logi (bez TUI)
python scripts/guardian.py ifg deploy run --dry-run --progress
```

---

## Architektura (skrót)

```
ProgressTracker → stderr → ProgressStderrSink → DashboardState → Rich Live → Terminal
                                                                              ↓
                                                         (koniec) raport Guardian stdout
```

Wybrano **Rich** zamiast Textual — wystarczy `Live` + `Panel` bez pełnej aplikacji TUI; lepiej pasuje do warstwy „renderer nad istniejącym protokołem”.
