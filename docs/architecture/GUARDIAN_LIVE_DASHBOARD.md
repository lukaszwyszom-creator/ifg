# Guardian Live Dashboard (TUI)

## Cel

Pełnoekranowy podgląd postępu długich operacji Guardian w terminalu — bez zmiany logiki workflow, `ProgressTracker` ani `ExecutionEngine`.

Inspiracje: lazygit, btop, k9s.

## Warstwy

```
ProgressTracker  →  [GWO_PROGRESS] na stderr
        ↓
ProgressStderrSink  →  parse_progress_line()
        ↓
DashboardState  →  model (fazy, ETA, historia)
        ↓
Rich Live (1 Hz)  →  terminal
        ↓
(po zakończeniu) standardowy raport Guardian na stdout
```

Dashboard **nie** posiada własnej logiki deploy — wyłącznie prezentuje linie protokołu postępu.

## Tryby CLI

| Flaga | Zachowanie |
|-------|------------|
| *(domyślnie)* | `--progress` dla długich workflow — surowe linie `[GWO_PROGRESS]` na stderr |
| `--progress` | Wymuszenie logów postępu |
| `--no-progress` | Cisza (brak `[GWO_PROGRESS]`) |
| `--dashboard` | Pełnoekranowy TUI (wymaga `rich`, implikuje `--progress`) |

`--dashboard` i `--no-progress` są wzajemnie wykluczające.

## Układ ekranu

- Nagłówek **Guardian**
- Workflow, status (`RUNNING` / `SUCCESS` / `FAILED`)
- Pasek postępu + spinner (10 znaków, odświeżany 1 Hz)
- Etap, krok X/Y, czas, ETA
- Ostatnia akcja
- Lista 10 faz deployu z ikonami: `✔` `▶` `○` `✗` `⊘`
- Sekcja heartbeat (alive / 30 s)
- Ostatnie 20 zdarzeń (bez spamu heartbeat)

## Moduły

```
scripts/ifg_guardian/core/dashboard/
├── parser.py       # parse_progress_line, parse_elapsed_seconds
├── model.py        # DashboardState.apply_event()
├── eta.py          # estimate_eta_seconds, format_duration
├── renderer.py     # render_dashboard_plain (testy), render_dashboard_rich (Rich)
├── stderr_sink.py  # ProgressStderrSink — przechwyt stderr
└── session.py      # run_with_live_dashboard() — wątek workflow + Rich Live
```

## Integracja (bez zmian engine/tracker)

1. CLI: `_run_with_display()` przed uruchomieniem workflow
2. Podmiana `sys.stderr` na `ProgressStderrSink` (suppress `[GWO_PROGRESS]`)
3. `ProgressTracker` nadal pisze na `sys.stderr` — linie trafiają do sinka
4. Workflow w wątku; główny wątek odświeża Rich Live co 1 s
5. Po zakończeniu: przywrócenie stderr, zamknięcie ekranu (`transient=True`)
6. `run_ifg_*` drukuje standardowy raport na stdout

## Zależność

```bash
pip install 'rich>=13.7,<14.0'
# lub
pip install -e ".[guardian]"
```

## Testy

```bash
pytest tests/unit/test_guardian_live_dashboard.py -q
```

Testują parser, model, ETA i renderer tekstowy — bez terminala.

## Przykład

```bash
python scripts/guardian.py ifg deploy run --dry-run --dashboard
python scripts/guardian.py ifg doctor --dashboard
```
