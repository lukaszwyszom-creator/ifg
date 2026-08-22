# Core Repository Reports

Commands: `repo graph`, `repo orphan`, `repo dead-code`

## Default behaviour

- Runs repository analysis and renders the full Markdown report to **stdout**.
- Does **not** create or modify files under `docs/reports/`.
- Does **not** change `git status`.

```bash
python3 -m scripts.guardian_platform repo graph
python3 -m scripts.guardian_platform repo orphan
python3 -m scripts.guardian_platform repo dead-code
```

Use `--format json` for a compact JSON summary instead of Markdown.

Use `--format terminal` for a compact terminal summary instead of Markdown.

## Explicit report file

Persist a report only when the output path is given explicitly:

```bash
python3 -m scripts.guardian_platform repo graph \
  --output docs/reports/repository_graph.md
```

Existing files are **not** overwritten unless `--force` is supplied:

```bash
python3 -m scripts.guardian_platform repo orphan \
  --output /tmp/orphans.md --force
```

When `--output` is used, stdout still contains the report (or JSON/terminal summary per `--format`), followed by a line such as `Graph report: docs/reports/repository_graph.md`.

## Flags

| Flag | Effect |
|------|--------|
| `--output PATH` | Write Markdown report to PATH |
| `--force` | Allow overwriting an existing output file |
| `--format terminal\|json\|markdown` | Stdout format (default: Markdown report) |

Programmatic helpers `write_repository_graph_report`, `write_orphans_report`, and `write_dead_code_report` remain available for conscious updates of canonical report paths (e.g. from tests or maintenance scripts).
