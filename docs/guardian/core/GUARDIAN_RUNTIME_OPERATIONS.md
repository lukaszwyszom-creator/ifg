# Guardian Runtime Operations (GWO-IFG-0072)

## Restart policy semantics

Production compose uses `restart: always` (not `unless-stopped`).

| Event | `always` behaviour |
|---|---|
| Container crash | Docker restarts container |
| Docker daemon restart | Stopped containers are started |
| Manual `docker stop` / `compose stop` | **No immediate restart** — restart policy is ignored until manual start or daemon restart |

`always` differs from `unless-stopped` mainly after Docker daemon restart: manually stopped containers stay stopped under `unless-stopped`, while `always` starts them when the daemon comes back.

Do **not** switch restart policy during maintenance. Maintenance is a Guardian workflow with an explicit marker.

## Runtime vs Release (GDD-0010)

| Layer | Statuses |
|---|---|
| Runtime | `PRODUCTION_RUNNING`, `PRODUCTION_STOPPED`, `PRODUCTION_DEGRADED`, `PRODUCTION_MAINTENANCE` |
| Release | `READY_FOR_DEPLOY`, `PRODUCTION_BLOCKED` — via `guardian release evaluate` |

`prod health` reports runtime only. `PRODUCTION_BLOCKED` does not cause stack shutdown.

## Maintenance mode

```bash
guardian prod maintenance start --yes --reason "planowana konserwacja"
guardian prod maintenance status
guardian prod maintenance end --yes
```

Flow:

1. Precheck runtime (`PRODUCTION_RUNNING` or safe `PRODUCTION_DEGRADED`)
2. Atomic maintenance marker in `.state/maintenance.json` (not in Git)
3. `compose stop` on DS723+
4. Verify stop → `PRODUCTION_MAINTENANCE`

`maintenance end` runs `prod recover`, waits for health, removes marker only on success.

## Audit trail

Append-only JSON Lines: `.state/runtime_audit.jsonl`

```bash
guardian prod audit --last 20
guardian prod audit --since 24h
```

Recorded workflows: maintenance start/end, prod recover, ifg deploy run. Operations outside Guardian (DSM, Container Manager, foreign SSH) are not attributed.

## Runtime monitor

```bash
guardian prod monitor check      # single iteration
guardian prod monitor install    # launchd every 5 min (Mac mini only)
guardian prod monitor status
guardian prod monitor uninstall
```

Alert rules:

- `PRODUCTION_RUNNING` / `PRODUCTION_MAINTENANCE` — no availability alarm
- Single failed read — no final alarm
- Alarm after ≥10 minutes in `PRODUCTION_STOPPED`, `PRODUCTION_DEGRADED`, or `UNREACHABLE`
- One alert per incident; recovery message when returning to `PRODUCTION_RUNNING`

Notifications: default sink `.state/runtime_notifications.log`. External channel requires operator configuration (not in repo).

## Recovery

```bash
guardian prod recover --yes
```

Safe recovery: precheck → backup → db healthy → api/worker → smoke. No `down -v`, no volume deletion.

## Limitations

- Guardian cannot identify actors for stops performed outside Guardian.
- Monitor and maintenance orchestration run from **Mac mini only**.
