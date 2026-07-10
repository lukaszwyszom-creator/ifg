# GWO-IFG-002A — Container Manager Cutover — CLOSED

| Pole | Wartość |
|------|---------|
| **ID** | GWO-IFG-002A |
| **Type** | Production Migration |
| **Risk** | HIGH |
| **Status końcowy** | **SUCCESS** |
| **Data zamknięcia** | 2026-07-07 |
| **Data wykonania cutover** | 2026-07-06 / 2026-07-07 (okno migracji) |
| **Operator** | Guardian (Mac mini) → SSH → DS723+ |
| **Commit prod (HEAD)** | `55810a4` — `feat(guardian): add frontend artifact gate for deploy and cutover` |
| **Branch** | `production` |
| **Host** | Synology DS723+ (`ds723`) |
| **Repo prod** | `/volume1/docker/ifg_v2/ifg_standalone` |

---

## Streszczenie wykonawcze

Migracja stacku IFG z projektu Compose **`docker`** na projekt **`ifg`** (Synology Container Manager) została **zakończona pomyślnie**.

| Aspekt | Wynik |
|--------|-------|
| Projekt Compose | **`ifg`** — aktywny |
| Kontenery produkcyjne | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` — **Running** |
| Wolumen bazy | `docker_postgres_data` — **zachowany** (external volume) |
| Sieć | `docker_ifg_prod` — **zachowana** (external network) |
| Stary stack `docker-*` | **usunięty** po walidacji |
| Health endpoint | **200 OK** |
| UI (frontend) | **działa** |
| Tunnel Cloudflare | `cloudflared-ifg` — **Up** (poza projektem Compose) |
| Backup przed migracją | `backups/pre_ifg_project_manual_20260706_2356.sql` |
| Decyzja GWO | **SUCCESS — CLOSED** |

> **Wniosek:** GWO-IFG-002A przeszedł z fazy PLANNING / NOT PRODUCTION PROVEN do **PRODUCTION PROVEN**. Produkcja IFG jest zarządzana wyłącznie przez projekt Compose **`ifg`**.

---

## Stan docelowy (po cutover)

### Compose / Container Manager

```
Container Manager → Projekt → ifg
Compose file:      docker/docker-compose.prod.yml
Project name:      ifg
```

### Kontenery

| Kontener | Rola | Status |
|----------|------|--------|
| `ifg-api-1` | FastAPI + serwowanie frontendu (`dist/` bind-mount) | Running |
| `ifg-worker-1` | Worker (zadania w tle) | Running |
| `ifg-db-1` | PostgreSQL 16 (`docker_postgres_data`) | Running |

### Usunięte (po pełnej walidacji)

| Kontener | Status |
|----------|--------|
| `docker-api-1` | **removed** |
| `docker-worker-1` | **removed** |
| `docker-db-1` | **removed** |

Zgodnie z runbookiem: `docker rm docker-*` wykonano **dopiero po** health PASS, Guardian verify PASS i teście funkcjonalnym.

### Infrastruktura poza projektem

| Komponent | Uwagi |
|-----------|-------|
| `cloudflared-ifg` | Działa **poza** projektem Compose `ifg`; tunel do `127.0.0.1:8000` bez zmian semantyki |
| `docker_postgres_data` | External volume — **nie** usuwany |
| `docker_ifg_prod` | External network — **nie** usuwana |

---

## Walidacja końcowa

| # | Check | Wynik |
|---|-------|-------|
| V1 | `curl http://127.0.0.1:8000/health` | **200 OK** |
| V2 | UI IFG (przeglądarka / tunnel) | **działa** |
| V3 | `docker compose -f docker/docker-compose.prod.yml ps` (projekt `ifg`) | api/worker/db **Up** |
| V4 | Brak kontenerów `docker-*-1` | **confirmed** |
| V5 | Backup SQL istnieje | `backups/pre_ifg_project_manual_20260706_2356.sql` |
| V6 | Commit na DS723+ | `55810a4` |

---

## Przebieg migracji (skrót)

```
1. Backup (ręczny)                    ✅ pre_ifg_project_manual_20260706_2356.sql
2. git pull (production)              ✅ HEAD 55810a4
3. compose config gate                ✅ name: ifg, external volume/network
4. Preflight                          ✅ GO
5. Frontend build                     ✅ (DS723+)
6. Artifact Verification Gate         ✅ index.html + assets
7. compose up (projekt ifg)           ✅ ifg-api-1, ifg-worker-1, ifg-db-1
8. Health                             ✅ 200 OK
9. Guardian verify                    ✅
10. Test funkcjonalny IFG             ✅
11. Cleanup legacy docker-*           ✅ usunięte
12. Container Manager UI              ✅ projekt ifg widoczny
```

Mechanizm cutover: **recreate kontenerów (scenariusz B)** — patrz [GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md](./GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md).

---

## Znane incydenty po drodze (rozwiązane / zaadresowane)

### 1. Brak `frontend-react/dist/index.html` na DS723+

| | |
|---|---|
| **Objaw** | Po `git pull` na NAS: `assets/` obecne, **`index.html` MISSING** — UI niedostępne lub niepełne |
| **Przyczyna** | `dist/` poza gitem; cutover/deploy bez jawnego buildu nie gwarantował `index.html` |
| **Rozwiązanie** | Frontend Artifact Gate (`55810a4`) — obowiązkowy `npm run build` + weryfikacja `index.html` przed `compose up` |
| **Raport** | [2026-07-06_IFG_INDEX_HTML_CUTOVER_DEPLOY_VERIFY.md](./2026-07-06_IFG_INDEX_HTML_CUTOVER_DEPLOY_VERIFY.md) |

### 2. Python 3.8 — `datetime.UTC` na DS723+

| | |
|---|---|
| **Objaw** | Guardian na NAS (Python 3.8): `ImportError: cannot import name 'UTC' from 'datetime'` |
| **Przyczyna** | `datetime.UTC` dostępne od Python 3.11 |
| **Rozwiązanie** | `time_compat.UTC` + kompatybilność w 10 modułach (`a755d31`, po HEAD cutover) |
| **Raport** | [2026-07-06_GUARDIAN_PYTHON38_FIX.md](./2026-07-06_GUARDIAN_PYTHON38_FIX.md) |

### 3. Execution Guard — uruchomienie LIVE na DS723+

| | |
|---|---|
| **Objaw** | `ifg cutover run --yes` uruchomione bezpośrednio na DS723+ → `backup failed: ssh exit 255` |
| **Przyczyna** | Guardian mutujący zawsze używa SSH do `ds723`; self-SSH z NAS kończy się exit 255 |
| **Rozwiązanie** | Execution Guard — LIVE mutating zablokowany na hoście docelowym; orchestration wyłącznie z Mac mini (`8427144`, po HEAD cutover) |
| **Raport** | [2026-07-06_GUARDIAN_EXECUTION_GUARD_MAC_ONLY.md](./2026-07-06_GUARDIAN_EXECUTION_GUARD_MAC_ONLY.md), [2026-07-06_GUARDIAN_LOCAL_REMOTE_EXECUTION.md](./2026-07-06_GUARDIAN_LOCAL_REMOTE_EXECUTION.md) |

### 4. Backup stage — problem z etapem workflow

| | |
|---|---|
| **Objaw** | Etap `backup` w workflow Guardian przy uruchomieniu z DS723+ padał na SSH zanim wykonał dump |
| **Przyczyna** | Ten sam model co §3 — brak local executor, wymuszony SSH nawet gdy proces już na NAS |
| **Rozwiązanie operacyjne** | Backup wykonany **ręcznie** na DS723+: `backups/pre_ifg_project_manual_20260706_2356.sql`; cutover LIVE uruchomiony z **Mac mini** |
| **Rozwiązanie trwałe** | Execution Guard (§3) + runbook: backup ręczny na DS723+, Guardian LIVE z Mac mini |

### 5. Stack zatrzymany po `git pull` (502)

| | |
|---|---|
| **Objaw** | Po pull bez restartu: `cloudflared-ifg` Up, API **connection refused** na `:8000` |
| **Przyczyna** | `git pull` nie restartuje kontenerów; stary stack był Exited |
| **Kontekst** | Stan wyjściowy przed cutover; rozwiązany przez pełny cutover do projektu `ifg` |
| **Raport** | [2026-07-06_IFG_502_AFTER_PULL_DIAG.md](./2026-07-06_IFG_502_AFTER_PULL_DIAG.md) |

---

## Model operacyjny (potwierdzony)

| Host | Rola | Dozwolone |
|------|------|-----------|
| **Mac mini** | Orchestration host | `ifg cutover run --yes`, `ifg deploy run --yes`, Guardian verify |
| **DS723+** | Execution target | Ręczne kroki shell (backup SQL), **nie** Guardian LIVE mutating |

---

## Rollback (nieużyty)

Rollback **nie był wymagany**. W razie potrzeby:

- Skrypt: `ifg cutover rollback --yes` (z Mac mini)
- Punkt przywrócenia: commit zapisany przed `git pull` + backup `pre_ifg_project_manual_20260706_2356.sql`

---

## Powiązane dokumenty

| Dokument | Rola |
|----------|------|
| [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md) | Procedura operacyjna |
| [GWO_IFG_002A_PRODUCTION_MIGRATION.md](./GWO_IFG_002A_PRODUCTION_MIGRATION.md) | Plan migracji (stan przed — PLANNING) |
| [GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md](./GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md) | Mapowanie runbook → workflow Guardian |
| [GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md](./GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md) | Scenariusz B — recreate |
| [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md) | Raport techniczny pełny |
| [2026-07-06_FRONTEND_ARTIFACT_GATE_IMPLEMENTATION.md](./2026-07-06_FRONTEND_ARTIFACT_GATE_IMPLEMENTATION.md) | Artifact Gate (`55810a4`) |

---

## Zamknięcie GWO

| Kryterium | Spełnione |
|-----------|-----------|
| Projekt `ifg` aktywny w Container Manager | ✅ |
| Kontenery `ifg-*` Running | ✅ |
| Stare `docker-*` usunięte po walidacji | ✅ |
| Baza `docker_postgres_data` zachowana | ✅ |
| Health 200 OK | ✅ |
| UI działa | ✅ |
| Backup przed migracją | ✅ |
| Test funkcjonalny PASS | ✅ |

**Status GWO-IFG-002A: SUCCESS — CLOSED**

Data zamknięcia: **2026-07-07**

---

*Raport zamknięcia migracji. Bez zmian w systemie, deployu i kodzie w ramach jego utworzenia.*
