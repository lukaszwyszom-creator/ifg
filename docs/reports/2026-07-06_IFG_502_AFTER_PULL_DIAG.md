# IFG 502 po synchronizacji DS723+ — diagnostyka

**Data:** 2026-07-06 23:02 CET  
**Host:** DS723+ (`ds723:32122`)  
**Repo:** `/volume1/docker/ifg_v2/ifg_standalone`  
**HEAD:** `0cbaebab2d26854a93eaaed0d77796b508f17ecc` (`0cbaeba`)  
**Wykonawca:** Guardian / SSH (read-only)  
**Zakres:** diagnostyka — **bez naprawy, bez restartu, bez LIVE cutover, bez rollback**

---

## 1. Podsumowanie wykonawcze

| Obszar | Wynik |
|--------|--------|
| `git pull` | ✅ zakończony wcześniej (HEAD `0cbaeba`) |
| LIVE cutover | ❌ nie wykonywany |
| Stack IFG (api/worker/db) | ❌ **zatrzymany** |
| Port `127.0.0.1:8000` | ❌ **brak listenera** |
| `curl /health` | ❌ connection refused |
| `cloudflared-ifg` | ✅ działa — origin `http://127.0.0.1:8000` **niedostępny** |
| Osobny nginx / reverse proxy | ❌ brak (architektura: Cloudflare Tunnel → API :8000) |
| Cloudflare 502 | ✅ **wyjaśnione** — tunel OK, origin down |

**Korelacja z `git pull`:** pull **nie zatrzymał** kontenerów. Stack był już wyłączony **~45 godzin** przed diagnostyką (od ~2026-07-05 02:10 CET). Pull zaktualizował tylko pliki na dysku.

---

## 2. Stan kontenerów

### 2.1 `docker ps` (wszystkie kontenery IFG)

| Kontener | Obraz | Status | Porty |
|----------|-------|--------|-------|
| `docker-api-1` | `ifg-api:latest` | **Exited (137)** | `127.0.0.1:8000->8000/tcp` (nieaktywny) |
| `docker-worker-1` | `ifg-api:latest` | **Exited (137)** | — |
| `docker-db-1` | `postgres:17` | **Exited (0)** | `5432/tcp` |
| `cloudflared-ifg` | `cloudflare/cloudflared:latest` | **Up** 45 h | — |

Brak osobnego kontenera **frontend** — SPA montowane do API (`frontend-react/dist` → `/app/frontend-react/dist`).

### 2.2 `docker compose ps -a`

**Projekt `ifg`** (nowy `name: ifg` w pliku po pull):

```
(pusty — brak kontenerów pod projektem ifg)
```

**Projekt `docker`** (legacy, faktyczne kontenery):

```
docker-api-1     Exited (137) 45 hours ago   127.0.0.1:8000->8000/tcp
docker-db-1      Exited (0)   45 hours ago   5432/tcp
docker-worker-1  Exited (137) 45 hours ago
```

### 2.3 Czasy zatrzymania (`docker inspect`)

| Kontener | FinishedAt (UTC) | CET | Exit | OOMKilled |
|----------|------------------|-----|------|-----------|
| `docker-db-1` | 2026-07-05T00:09:56Z | ~02:09 | 0 (graceful) | false |
| `docker-worker-1` | 2026-07-05T00:10:00Z | ~02:10 | 137 (SIGKILL) | false |
| `docker-api-1` | 2026-07-05T00:10:00Z | ~02:10 | 137 (SIGKILL) | false |

`cloudflared-ifg` **StartedAt:** `2026-07-05T00:10:34Z` — restart tunelu w tej samej minucie co zatrzymanie stacku (prawdopodobny restart Docker/DSM lub ręczna operacja operatora).

---

## 3. Health i porty

### 3.1 `curl http://127.0.0.1:8000/health`

```
Failed to connect to 127.0.0.1 port 8000 after 0 ms: Error
HTTP_CODE=000
```

### 3.2 Port 8000

```
NO LISTENER ON 8000
```

### 3.3 Guardian `prod health`

```
❌ container problems: api/worker/db brak w docker compose ps (projekt ifg)
❌ Health check failed: curl connection refused
Remote HEAD: 0cbaeba
Status: ERROR
```

---

## 4. Logi

### 4.1 API (`docker-api-1`, tail)

Ostatnie wpisy przed shutdown — cykliczne `GET /health 200 OK`, następnie:

```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [1]
```

Brak crash loop / traceback przy zamknięciu — **graceful shutdown**, nie błąd aplikacji jako przyczyna bieżącego 502.

### 4.2 Worker (`docker-worker-1`, tail)

Ostatnia aktywność: **2026-07-03 20:41 CET** — job KSeF zakończony błędem biznesowym (`Sesja KSeF wygasła`), potem shutdown wraz ze stackiem. Worker **nie działa** od zatrzymania stacku.

### 4.3 Frontend

Osobny kontener **nie istnieje**. Mount hosta:

```
/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist → /app/frontend-react/dist
```

Stan po pull + unblock:

```
frontend-react/dist/
  assets/          (pliki z 2026-07-03)
  index.html       MISSING
```

Backup z unblock: `backups/pull_unblock_20260706_224806/index.html.bak` (494 B, z 2026-07-03).

**Uwaga:** brak `index.html` uniemożliwi poprawne serwowanie UI po restarcie API, ale **nie jest przyczyną 502** — 502 wynika z braku procesu na :8000.

### 4.4 Reverse proxy / Cloudflare (`cloudflared-ifg`)

- **Brak nginx** na hoście (żaden kontener proxy/reverse).
- Tunel: `originService=http://127.0.0.1:8000` — **poprawna konfiguracja** (bezpośrednio do API).
- Błędy (ostatnie 2 h, 2026-07-06 ~22:59–23:00 CET):

```
ERR Unable to reach the origin service: dial tcp 127.0.0.1:8000: connect: connection refused
dest=https://ifg.ikonastudio.pl/ui/login
dest=https://ifg.ikonastudio.pl/
```

Cloudflare zwraca **502 Host Error**, bo cloudflared nie może połączyć się z originem — **nie** z powodu błędu samego tunelu (tunel Up, połączenia QUIC zarejestrowane).

---

## 5. Wpływ `git pull` na `docker-compose.prod.yml`

Zmiany w pull (`a405646` → `0cbaeba`):

```diff
+ name: ifg
  volumes:
    postgres_data:
+     name: docker_postgres_data
+     external: true
  networks:
    ifg_prod:
-     driver: bridge
+     name: docker_ifg_prod
+     external: true
```

| Aspekt | Ocena |
|--------|--------|
| Czy pull sam restartuje kontenery? | **Nie** — `git pull` nie wywołuje `docker compose up` |
| Czy zmiana wymaga recreate? | **Tak, przy migracji** na projekt `ifg` — to jest cel cutover prep, nie wykonany LIVE |
| Czy running stack używa nowego pliku? | **Nie** — kontenery nadal należą do projektu `docker` (legacy) i są **Exited** |
| Czy `docker compose ps` (domyślny `ifg`) widzi stack? | **Nie** — pusty; realne kontenery pod `-p docker` |

**Wniosek:** zmiana compose **nie spowodowała** bieżącego 502. Stack był już zatrzymany. Po restarcie operator musi świadomie wybrać: **legacy `-p docker up`** (szybki recovery) vs **cutover LIVE na projekt `ifg`** (planowany).

---

## 6. Zgodność obrazu z kodem

| Element | Data / stan |
|---------|-------------|
| Obraz `ifg-api:latest` | zbudowany **2026-07-03 20:35 CET** |
| HEAD repo | **2026-07-06 22:41 CET** (`0cbaeba`) |
| Kontenery | **nie działają** — obraz nieużywany od ~45 h |

Kod na dysku (HEAD `0cbaeba`) jest **nowszy** niż obraz Docker. Sam restart bez `--build` uruchomiłby **stary** kod z 2026-07-03. Pełne wdrożenie HEAD wymaga rebuild + ewentualnie migracji Alembic.

---

## 7. Klasyfikacja przyczyny 502

| Hipoteza | Werdykt |
|----------|---------|
| Zatrzymany kontener | ✅ **TAK** — api/worker/db Exited |
| Błąd aplikacji (crash) | ❌ NIE — ostatni shutdown graceful; brak działającego procesu |
| Reverse proxy (nginx) | ❌ NIE — brak nginx; cloudflared → :8000 |
| Cloudflare / tunel | ❌ NIE jako root cause — tunel działa, origin down |
| Brak restartu po pull | ⚠️ **Częściowo** — pull nie restartuje, ale stack był down **przed** pull; pull nie przywrócił usługi |
| Zmiana compose po pull | ❌ NIE jako bezpośrednia przyczyna 502 — stack już był zatrzymany |

### Uwaga o dry-run cutover

`ifg cutover run --dry-run` zgłosił **Health OK** i **Safety Gate GO**, ponieważ etapy `post_health` / `git_pull` były **symulowane** (`[dry-run]`). **Nie odzwierciedlały** faktycznego stanu produkcji w momencie 502. Guardian `prod health` (read-only) poprawnie zwraca **ERROR**.

---

## 8. ROOT CAUSE

**Cały stack IFG (api, worker, db) jest zatrzymany od ~2026-07-05 02:10 CET.** Na hoście nie nasłuchuje proces na `127.0.0.1:8000`. `cloudflared-ifg` działa i przekierowuje ruch na `http://127.0.0.1:8000`, co daje `connection refused` → Cloudflare **502 Host Error**.

`git pull` (2026-07-06 ~22:48) **nie jest przyczyną** zatrzymania — synchronizacja kodu nie uruchomiła ani nie zatrzymała kontenerów. 502 jest skorelowany czasowo z odkryciem problemu po pull, ale **root cause = wyłączony stack sprzed pull**.

Dodatkowe ryzyko po restarcie (nie przyczyna bieżącego 502):
- brak `frontend-react/dist/index.html` (SPA),
- obraz Docker sprzed 3 commitów cutover prep na HEAD,
- rozdział projektów Compose `docker` (legacy) vs `ifg` (nowy plik).

---

## 9. RECOMMENDED FIX

**Wymaga potwierdzenia operatora przed wykonaniem.**

### Krok A — natychmiastowy recovery (bez LIVE cutover)

Przywrócić działający stack pod **legacy projektem `docker`** (kontenery już istnieją):

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH"

# 1. Przywrócić frontend index.html (przed startem API)
cp backups/pull_unblock_20260706_224806/index.html.bak frontend-react/dist/index.html

# 2. Uruchomić stack legacy (NIE projekt ifg — bez cutover)
docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d

# 3. Weryfikacja
curl -fsS http://127.0.0.1:8000/health
docker compose -p docker -f docker/docker-compose.prod.yml ps
```

### Krok B — jeśli celem jest kod z HEAD `0cbaeba`

Po potwierdzeniu operatora:

```bash
docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d --build
# + npm run build frontend-react (na hoście lub w pipeline)
# + alembic upgrade head (jeśli wymagane)
```

### Krok C — cutover na projekt `ifg` (osobna decyzja)

Zgodnie z runbookiem — **nie** jako pierwszy krok recovery 502:

```bash
PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --yes --confirm-functional
```

### Krok D — dochodzenie uboczne

Ustalić **kto/co zatrzymało** stack 2026-07-05 ~02:10 CET (DSM update, Container Manager, ręczny `docker compose down`, reboot NAS). Logi Synology / historia Container Manager poza zakresem tej diagnostyki.

---

## 10. Checklist diagnostyczna (wykonana)

| # | Punkt | Wynik |
|---|-------|--------|
| 1 | `docker compose ps` | Legacy `docker`: Exited; projekt `ifg`: pusty |
| 2 | Status kontenerów IFG | api/worker/db **Exited**; cloudflared **Up** |
| 3 | Logi api/worker/frontend/proxy | api graceful shutdown; worker idle+KSeF err; brak frontend container; cloudflared origin refused |
| 4 | `curl 127.0.0.1:8000/health` | **FAIL** — connection refused |
| 5 | Reverse proxy → backend | cloudflared → `127.0.0.1:8000` (poprawne; backend down) |
| 6 | Zmiana compose po pull | Tak (`name: ifg`, external vol/net) — wymaga recreate przy cutover, **nie** przyczyna 502 |
| 7 | Obraz vs kod | Obraz 2026-07-03; HEAD 2026-07-06; kontenery nie działają |
| 8 | Klasyfikacja | **Zatrzymany kontener** + **brak restartu**; nie app crash / nie Cloudflare / nie nginx |

---

*Raport read-only. Żadna naprawa, restart, deploy ani LIVE cutover nie zostały wykonane.*
