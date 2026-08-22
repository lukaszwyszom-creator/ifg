# IFG Repository Audit

Command: `python3 -m scripts.guardian_platform ifg repo audit`

## Default behaviour

- Runs the IFG repo audit workflow against the repository selected by CLI context (`ctx.root`).
- Prints the report to **stdout** (Markdown by default for `--format markdown`, terminal summary for `--format terminal`, JSON for `--format json`).
- Does **not** create or modify files under `docs/guardian/`.
- Does **not** change `git status`.

```bash
python3 -m scripts.guardian_platform ifg repo audit
python3 -m scripts.guardian_platform --format json ifg repo audit
python3 -m scripts.guardian_platform --format terminal ifg repo audit
```

The audit always uses the repository root from CLI context. There is **no** fallback to the canonical IFG checkout when another root is selected.

## Explicit report file

Persist a report only when the output path is given explicitly:

```bash
python3 -m scripts.guardian_platform ifg repo audit \
  --output docs/guardian/REPO_AUDIT_2026_08_22.md
```

Relative `--output` paths are resolved against the selected repository root. Absolute paths are written exactly as given.

Existing files are **not** overwritten unless `--force` is supplied:

```bash
python3 -m scripts.guardian_platform ifg repo audit \
  --output /tmp/repo_audit.md --force
```

When `--output` is used, stdout still contains the selected format, followed by a line such as `Audit report: docs/guardian/REPO_AUDIT_2026_08_22.md`.

## Flags

| Flag | Effect |
|------|--------|
| `--output PATH` | Write report to PATH (Markdown unless `--format json`) |
| `--force` | Allow overwriting an existing output file |
| `--format terminal\|json\|markdown` | Stdout format |
| `--dry-run` | Workflow dry-run mode (audit remains read-only) |

## Exit codes

Audit result exit codes (PASS/WARN/FAIL semantics) are unchanged. Output path conflicts return exit code **2** without overwriting an existing file.
