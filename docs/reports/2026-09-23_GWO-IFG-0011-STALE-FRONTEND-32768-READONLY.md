# GWO-IFG-0011 — READ-ONLY: stale `ifg-frontend` on :32768 (DS723)

**Date:** 2026-09-23  
**Scope:** Diagnose port 32768 / container `ifg-frontend-1` vs canonical UI on API `:8000/ui`  
**Mode:** READ-ONLY (no stop/rm)

## Verdict

| Question | Answer | Evidence |
|----------|--------|----------|
| CANONICAL UI | API `/ui` on `127.0.0.1:8000` | Compose project `ifg` → `ifg-api-1`; cloudflared → `:8000` |
| Is `:32768` unused legacy? | **YES** | Not in current prod compose; stale May-2026 assets; no proxy/cron refs |
| Safe to stop/remove? | **YES** (with restart-policy caveat) | Orphan compose project `docker`; traffic uses `:8000` |
| Repo compose change needed? | **NO** | `frontend` service already removed (commit `d70761a`); NAS `docker stop`/`rm` only |

## Investigation

### 1. Container

```
ifg-frontend-1  ifg-frontend:latest  Up 2 days
0.0.0.0:32768->80/tcp, :::32768->80/tcp
```

### 2. Inspect highlights

- **Image:** `ifg-frontend:latest` (`sha256:eb79115cb172…`), image Created **2026-05-06**
- **Container Created:** 2026-08-03; **StartedAt:** 2026-09-21 (daemon restart)
- **Cmd:** nginx; **Mounts:** none (static baked into image)
- **RestartPolicy:** `always`
- **PortBindings:** host port empty → Docker assigned **ephemeral** host port **32768**
- **Network:** default `bridge` (`172.17.0.2`) — **not** `ifg` compose network
- **Compose labels:** `com.docker.compose.project=docker`, `service=frontend`, compose **2.20.1**  
  (no `config_files` / `working_dir` labels — orphaned from old up)

Only container with project=`docker`: `ifg-frontend-1`.

### 3. Compose file search

- Active compose: `/volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml` project **`ifg`** — services **api / worker / db only**
- Frontend in prod: **volume mount** `../frontend-react/dist` → API serves `/ui`
- Grep for `32768` under `/volume1/docker` compose/env: **no hits**
- Leftovers still on disk (unused by running stack): `Dockerfile.frontend`, `nginx.frontend.conf`
- Git: `frontend:` service removed from `docker-compose.prod.yml` in `d70761a` (was `127.0.0.1:3000:80`); replaced by API `/ui` mount

### 4. Reverse proxy / tunnel

- Synology `ReverseProxy.json`: only unrelated `:8081` cert entry — **no 32768 / ifg-frontend / 8000**
- **cloudflared-ifg** ingress: `ifg.ikonastudio.pl` and `api.ifg.ikonastudio.pl` → `http://172.17.0.1:8000` only — **not 32768**

### 5. systemd / cron / watchdog

- User crontab: empty; `/etc/crontab`: no `32768` / `ifg-frontend`
- No systemd unit hits in targeted paths
- Scripts under `ifg_standalone/scripts` + `docker/`: no start refs to `ifg-frontend` / `:32768`

### 6. Asset hash comparison

| Surface | Server | Last-Modified | JS | CSS |
|---------|--------|---------------|----|-----|
| `http://127.0.0.1:32768/` | nginx/1.27.5 | **2026-05-06** | `index-CvGj8pqP.js` | `index-BnFxgggD.css` |
| `http://127.0.0.1:8000/ui/` | uvicorn | **2026-09-23** | `index-CaH0FOv4.js` | `index-0Q_2nEL1.css` |

Hashes **differ** → `:32768` is stale SPA; `/ui` is current production UI.

### 7. Listeners

- `docker port ifg-frontend-1` → `80/tcp -> 0.0.0.0:32768` (also `::`)
- `ss`: `0.0.0.0:32768` LISTEN; API `127.0.0.1:8000` LISTEN

**Note:** stale frontend is published on **all interfaces**; canonical API is **localhost-only** (+ tunnel).

## IFG health (quick)

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production",...}
```

| Service | Status |
|---------|--------|
| ifg-api-1 | Up 9h (healthy) `127.0.0.1:8000->8000` |
| ifg-worker-1 | Up 9h (healthy) |
| ifg-db-1 | Up 2d (healthy) |

## Recommendation (do not execute yet)

1. **Canonical:** always verify UI via tunnel / `http://127.0.0.1:8000/ui/` — never `:32768`.
2. **Retire orphan on NAS** (no repo compose change):
   - `docker update --restart=no ifg-frontend-1`
   - `docker stop ifg-frontend-1 && docker rm ifg-frontend-1`
   - optional: `docker rmi ifg-frontend:latest` (and unused `amd64` tag)
3. Keep `Dockerfile.frontend` / `nginx.frontend.conf` in repo only if still useful for local experiments; they are **not** part of current prod path.
4. After rm: confirm `docker ps -a | grep frontend` empty and `/health` + `/ui/` still OK.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED (ops decision to stop/rm — not executed)
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Approve NAS-only `update --restart=no` + `stop` + `rm` of `ifg-frontend-1` (and optional `rmi`)?
2. Leave `Dockerfile.frontend` in repo as dead code, or delete in a follow-up docs/cleanup GWO?

