# IFG Repository Cleanup Advisor

Command: `python3 -m scripts.guardian_platform ifg repo cleanup`

## Default behaviour (dry-run / audit)

- Builds and renders the cleanup plan.
- Prints Markdown to **stdout** (no tracked file is written).
- Does **not** modify `git status`.
- Does **not** execute cleanup operations without `--yes`.

```bash
python3 -m scripts.guardian_platform --dry-run ifg repo cleanup
```

Use `--format terminal` for a compact terminal summary instead of Markdown.

## Explicit report file

Persist the plan only when the output path is given explicitly:

```bash
python3 -m scripts.guardian_platform --dry-run ifg repo cleanup \
  --output docs/reports/repository_cleanup_plan.md
```

Existing files are **not** overwritten unless `--force` is supplied:

```bash
python3 -m scripts.guardian_platform --dry-run ifg repo cleanup \
  --output /tmp/cleanup_plan.md --force
```

`--output` alone does **not** run LIVE cleanup; `--yes` is still required for execution.

## Flags

| Flag | Effect |
|------|--------|
| `--dry-run` | Plan only; no filesystem mutations from cleanup operations |
| `--yes` | LIVE execution (requires clean worktree for archive phases) |
| `--phase N` | Limit to phase 0–3 |
| `--output PATH` | Write plan Markdown to PATH |
| `--force` | Allow overwriting an existing output file |
| `--format terminal\|markdown` | Stdout format (default audit: Markdown) |
