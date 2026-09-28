# IFG local frontend — manual development (GWO-0010F)

`pl.ifg.dev-bootstrap` LaunchAgent is **DEMOTED**. Development is started
explicitly from the canonical SSD checkout — not via a permanent KeepAlive agent.

## Canonical repo

```text
/Volumes/WorkspaceSSD/projects/ifg_standalone
```

## Start (preferred)

```bash
cd /Volumes/WorkspaceSSD/projects/ifg_standalone/frontend-react
npm run dev
```

- Vite: `http://127.0.0.1:3000/ui/login` (host `0.0.0.0`, port `3000`)
- Optional API proxy target: `VITE_DEV_API_TARGET` (default health probe `http://127.0.0.1:8000/health`)

## Start with optional local docker warm-up

Same behaviour as the former LaunchAgent script (Vite + background
`docker compose … up -d db api worker` if local API health fails):

```bash
cd /Volumes/WorkspaceSSD/projects/ifg_standalone/frontend-react
npm run dev:bootstrap
# or: node ./scripts/dev-bootstrap.mjs
```

Force restart on a stuck port:

```bash
npm run dev:restart
# or: node ./scripts/dev-bootstrap.mjs --restart
```

## Stop

- Foreground: `Ctrl+C` in the terminal running Vite / bootstrap
- Or free the port:

```bash
lsof -ti :3000 | xargs kill
```

## Do not

- Do not re-enable `pl.ifg.dev-bootstrap` as a permanent LaunchAgent for everyday work
- Do not point developer tooling at `/Users/lukasz/projekty/ifg_standalone` (OLD checkout)
- Do not use this workflow against DS723+ production

## Optional re-enable (emergency only)

Rollback artefacts:

```text
~/Library/Application Support/Guardian/ifg-dev-bootstrap-0010f-rollback/
```

Tracked template (disabled by default — `RunAtLoad`/`KeepAlive` false):

```text
scripts/pl.ifg.dev-bootstrap.plist
```

Re-enable only consciously after updating paths; prefer manual `npm run dev`.
