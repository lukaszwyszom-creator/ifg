# Guardian Progress Protocol (GWO)

## Cel

Warstwa observability dla długich workflow Guardian (deploy, recovery, evaluate, cutover, doctor) bez zmiany logiki wykonania. Użytkownik widzi na stderr, na jakim etapie jest proces, czy nadal działa, oraz co aktualnie wykonuje.

## Format logu

Każda linia postępu ma stały format:

```
[GWO_PROGRESS] step=X/Y phase=<nazwa> status=<started|running|done|failed|skipped> elapsed=<czas> message=<opis>
```

| Pole | Opis |
|------|------|
| `step` | Numer bieżącego etapu (1-based) |
| `Y` | Liczba kanonicznych faz deployu (domyślnie 10) |
| `phase` | Nazwa fazy (patrz poniżej) |
| `status` | `started`, `running`, `done`, `failed`, `skipped` |
| `elapsed` | Czas od startu etapu lub workflow (`45s`, `2m5s`, `1h1m1s`) |
| `message` | Krótki opis akcji (sanityzowany, max 240 znaków) |

Przykład:

```
[GWO_PROGRESS] step=5/10 phase=remote_pull status=started elapsed=0s message=git pull origin production
[GWO_PROGRESS] step=5/10 phase=remote_pull status=running elapsed=30s message=alive; last_action=git pull origin production
[GWO_PROGRESS] step=5/10 phase=remote_pull status=done elapsed=42s message=ok
```

## Kanoniczne fazy deployu

1. `repo_status`
2. `tests`
3. `commit`
4. `push`
5. `remote_pull`
6. `remote_build`
7. `restart_services`
8. `health_check`
9. `post_deploy_verification`
10. `report_write`

Mapowanie faz na stage workflow i komendy shell jest w `scripts/ifg_guardian/core/progress/mapping.py`.

## Zdarzenia emitowane przez workflow

| Zdarzenie | Status | Kiedy |
|-----------|--------|-------|
| Start workflow | `started` | Początek `ExecutionEngine.run()` |
| Start etapu | `started` | Każdy stage workflow (poza `simulate_execution` na poziomie stage) |
| Heartbeat | `running` | Co 30 s podczas trwającego etapu |
| Koniec etapu | `done` / `failed` / `skipped` | Po zakończeniu stage lub intentu deploy |
| Błąd | `failed` | Stage `simulate_execution` z błędem (bez duplikacji stage-level) |
| Koniec workflow | `done` / `failed` | Faza `report_write` |

### Heartbeat

Podczas długiego etapu co 30 sekund:

```
message=alive; last_action=<ostatnia komenda lub akcja>
```

Wątek heartbeat jest daemonem; zatrzymuje się przy zakończeniu etapu.

## Architektura modułów

```
scripts/ifg_guardian/core/progress/
├── protocol.py    # format_progress_line, ProgressStatus
├── timeline.py    # ProgressTimeline, TimelineEntry
├── mapping.py     # fazy deploy, LONG_WORKFLOW_IDS
├── tracker.py     # ProgressTracker (emit + heartbeat)
└── report.py      # render_timeline_section() → Markdown
```

Integracja:

- `ExecutionEngine` — tworzy `ProgressTracker`, zapisuje `progress_timeline` w `transaction.audit`
- `IntentExecutor` — progress per intent w `simulate_execution` (git pull, docker build, rsync, …)
- Raporty markdown — sekcja **Timeline wykonania**

## CLI

Długie workflow domyślnie emitują progress (`LONG_WORKFLOW_IDS`):

- `ifg deploy run`
- `ifg cutover run`
- `ifg release plan`
- `ifg release evaluate` / `release evaluate`
- `ifg doctor`
- `workflow run <id>` (gdy workflow jest w `LONG_WORKFLOW_IDS` lub jawne `--progress`)

```bash
# Domyślnie progress ON dla deploy
python scripts/guardian.py ifg deploy run --dry-run

# Wyłączenie
python scripts/guardian.py ifg deploy run --dry-run --no-progress

# Wymuszenie dla krótkiego workflow
python scripts/guardian.py workflow run core.repo.audit --progress
```

## Timeline w raporcie końcowym

Po zakończeniu workflow `transaction.audit["progress_timeline"]` zawiera wpisy z `started_at`, `ended_at`, `duration_ms`. Raport markdown dodaje tabelę:

```markdown
## Timeline wykonania

| # | Faza | Status | Start | Koniec | Czas | Opis |
```

## Ograniczenia (MVP)

- `prod recover` nadal deleguje do `guardian2.py` — poza zakresem tego modułu
- Progress nie zmienia kolejności ani warunków deployu
- Output idzie na **stderr** (stdout pozostaje dla raportu terminalowego)

## Testy

```bash
pytest tests/unit/test_guardian_progress_protocol.py -q
```
