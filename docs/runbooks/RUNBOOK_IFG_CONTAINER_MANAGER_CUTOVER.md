# RUNBOOK — IFG Container Manager Cutover (projekt `ifg`)

**GWO:** GWO-IFG-002A  
**Host:** Synology DS723+ (`ds723`)  
**Repo prod:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Branch:** `production`  
**Compose:** `docker/docker-compose.prod.yml` (`name: ifg`, external volume/network)  
**Data zatwierdzenia:** 2026-07-06  

---

## RUNBOOK STATUS:

**APPROVED**

---

## Cel

Migracja stacku IFG z projektu Compose **`docker`** na projekt **`ifg`** (Synology Container Manager), z **zachowaniem** produkcyjnej bazy `docker_postgres_data` i sieci `docker_ifg_prod`.

**Mechanizm cutover:** recreate kontenerów (B) — **nie** adoptacja istniejących. Patrz [GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md](../reports/GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md).

---

## Zasady bezpieczeństwa (nie negocjowalne)

| Zasada | Opis |
|--------|------|
| **Zakaz `down -v`** | Nigdy `docker compose down -v` |
| **Zakaz `volume rm`** | Nigdy `docker volume rm docker_postgres_data` |
| **Zakaz `-p docker` po cutover** | Po migracji używaj wyłącznie compose z `name: ifg` |
| **Jeden Running DB** | Nigdy dwa kontenery DB jednocześnie na `docker_postgres_data` |
| **Stare kontenery = rollback** | **Nie** `docker rm docker-*` przed pełną walidacją |

---

## Wymagania wstępne

| # | Wymaganie | Jak sprawdzić |
|---|-----------|---------------|
| P1 | Dostęp SSH do DS723+ (`ds723`) | `ssh ds723 echo ok` |
| P2 | Stack IFG **zatrzymany** (Exited) lub okno maintenance zaakceptowane | `sudo docker ps -a --filter name=docker-` |
| P3 | Wolumen `docker_postgres_data` istnieje | `sudo docker volume inspect docker_postgres_data` |
| P4 | Commit compose prep na `production` (**≥ `9505adc`**) wdrożony na DS723+ | `git log -1 --oneline` |
| P5 | Operator ma ~30 min + numer commitu **przed** migracją (rollback) | zapisz: `git rev-parse HEAD` przed pull |
| P6 | Katalog backupów istnieje | `mkdir -p /volume1/docker/ifg_v2/backups` |
| P7 | Mac mini: repo zsynchronizowane (Guardian verify) | opcjonalnie przed cutover |

**NO-GO** jeśli `docker-api-1` jest **Running** (konflikt portu 8000) — najpierw zatrzymaj stary stack.

---

## Kolejność operacji (skrót)

```
1. Backup
2. git pull
3. compose config (gate)
4. Preflight (Exited, nie rm)
5. Start projektu ifg
6. Health
7. Guardian verify
8. Test funkcjonalny IFG
9. docker rm docker-*  ← DOPIERO TUTAJ
10. Container Manager UI check
```

---

## Krok 1 — Backup (GO gate)

**Wykonaj na DS723+.** Cutover **nie startuje** bez potwierdzonego backupu.

### Wariant A — stack Exited (typowy stan IFG 2026-07)

Tymczasowo podnieś **tylko DB** starym projektem, zrób dump, zatrzymaj:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Zapisz commit przed migracją
git rev-parse HEAD | tee backups/pre_cutover_commit.txt

# Tymczasowy start tylko db (stary projekt docker)
sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d db

# Poczekaj na healthy
sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  pg_isready -U postgres -d ksef_backend

# Backup
sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_dump -U postgres ksef_backend \
  > backups/pre_ifg_project_$(date +%Y%m%d_%H%M).sql

# Zatrzymaj db (przywróć Exited przed cutover)
sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production stop db
```

### Wariant B — db już Running

Pomiń start, wykonaj tylko `pg_dump` (jak wyżej, bez `up`/`stop`).

### Weryfikacja backupu

```bash
ls -lh backups/pre_ifg_project_*.sql
# Plik > 0 bajtów; opcjonalnie: head -5 pliku — powinien zawierać PostgreSQL dump
```

**NO-GO** jeśli plik backupu pusty lub brak.

---

## Krok 2 — git pull

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git fetch origin production
git pull origin production
git log -1 --oneline
```

Oczekiwany commit: zawiera `name: ifg` + external pins w `docker/docker-compose.prod.yml`.

---

## Krok 3 — compose config (gate)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config \
  | grep -E '^name:|docker_postgres_data|docker_ifg_prod|external'
```

### Oczekiwany wynik (MUSI być)

```
name: ifg
    name: docker_ifg_prod
    external: true
    name: docker_postgres_data
    external: true
```

### NO-GO jeśli

- Pojawia się `ifg_postgres_data` (brak pinu → pusta baza)
- Brak `external: true` przy wolumenie DB
- `name:` ≠ `ifg`

**STOP. Nie przechodź do Kroku 5.**

---

## Krok 4 — Preflight

```bash
# Stare kontenery — MUSZĄ istnieć i być Exited
sudo docker ps -a --filter name=docker- --format 'table {{.Names}}\t{{.Status}}'

# Wolumen prod
sudo docker volume inspect docker_postgres_data --format 'Name={{.Name}}'

# Sieć prod
sudo docker network inspect docker_ifg_prod --format '{{.Name}}' 2>/dev/null || echo "CHECK NETWORK"
```

| Check | Oczekiwane |
|-------|------------|
| `docker-api-1`, `docker-worker-1`, `docker-db-1` | **Exited** (mogą istnieć) |
| `docker_postgres_data` | istnieje |
| `docker_ifg_prod` | istnieje |

**Nie wykonuj:** `docker rm docker-api-1 docker-worker-1 docker-db-1` — to **rollback asset**.

**NO-GO** jeśli `docker-api-1` **Running** (zatrzymaj przed Start).

---

## Krok 5 — Start projektu `ifg`

**Working directory:** zawsze **repo root** (nie `docker/`).

### Wariant CLI (preferowany)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

Z rebuild obrazu (jeśli równoległy deploy kodu):

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

### Wariant Container Manager (UI)

1. Container Manager → **Project** → **Create**
2. Nazwa: `ifg`
3. Ścieżka: repo root lub `docker/` — wybierz plik `docker-compose.prod.yml`
4. **Odznacz** „Start the project once it is created” (opcjonalnie — weryfikacja przed Start)
5. **Start** projektu z UI

Efekt = `docker compose up` — nowe kontenery `ifg-api-1`, `ifg-worker-1`, `ifg-db-1`.

---

## Krok 6 — Health (DS723+)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Status serwisów
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps

# API health
curl -fsS http://127.0.0.1:8000/health

# PostgreSQL
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  pg_isready -U postgres -d ksef_backend

# Sanity danych
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  psql -U postgres -d ksef_backend -c "SELECT COUNT(*) FROM invoices;"

# Wolumen — nadal ten sam fizyczny
sudo docker volume inspect docker_postgres_data --format '{{.Name}}'

# Etykieta projektu na nowym DB
sudo docker inspect ifg-db-1 --format '{{index .Config.Labels "com.docker.compose.project"}}'
# Oczekiwane: ifg

# Worker (ostatnie logi)
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs worker --tail=30
```

| Check | PASS |
|-------|------|
| `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` | Up (healthy) |
| `curl .../health` | `"status":"ok"` |
| `pg_isready` | accepting connections |
| `COUNT(*) FROM invoices` | > 0 (prod) |
| Wolumen | `docker_postgres_data` |
| Stary stack | `docker-*` **Exited** (OK) |

**NO-GO** → sekcja Rollback.

---

## Krok 7 — Guardian verify (Mac mini, read-only)

Z Mac mini (repo `ifg_standalone`):

```bash
cd /Users/lukasz/projekty/ifg_standalone
python3 scripts/guardian.py deploy check
```

Sprawdź:

- SSH OK
- Branch/commit zgodne (lub świadoma różnica)
- Kontenery na DS723+ healthy (`api`, `worker`, `db`)
- Werdykt końcowy: **POTWIERDZONE** / brak krytycznych ❌

**NO-GO** jeśli kontenery unhealthy lub SSH fail.

---

## Krok 8 — Test funkcjonalny IFG

Wykonaj ręcznie (przeglądarka / API):

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| F1 | Logowanie do IFG (UI prod) | sukces |
| F2 | Lista faktur | dane widoczne, brak pustej bazy |
| F3 | Szczegóły faktury (1 rekord) | poprawne dane |
| F4 | Status KSeF / połączenie (jeśli dotyczy) | brak błędu krytycznego |
| F5 | Worker — brak crash loop w logach | stabilny |

**NO-GO** jeśli UI puste, błędy DB, brak danych produkcyjnych.

---

## Krok 9 — Usunięcie starych kontenerów (tylko po GO kroków 6–8)

**Warunek:** Health PASS + Guardian verify PASS + test funkcjonalny PASS.

```bash
sudo docker rm docker-api-1 docker-worker-1 docker-db-1
```

**Nigdy wcześniej.** **Nie** używać `-v`.

Po usunięciu:

```bash
sudo docker ps -a --filter name=docker-
# Brak docker-api-1, docker-worker-1, docker-db-1
```

---

## Krok 10 — Container Manager (UI)

1. Container Manager → **Project**
2. Projekt **`ifg`** z usługami: `api`, `worker`, `db`
3. Wszystkie **Running** / healthy
4. `cloudflared-ifg` — poza projektem (oczekiwane)

---

## Rollback

### Kiedy

- Gate compose config FAIL
- Health FAIL po 5 min
- COUNT invoices = 0 / brak tabel
- Guardian verify FAIL (kontenery unhealthy)
- Test funkcjonalny FAIL

### Kroki (szybki rollback — wykorzystuje zachowane `docker-*`)

1. **Zatrzymaj projekt `ifg`:**

   ```bash
   cd /volume1/docker/ifg_v2/ifg_standalone
   sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop
   ```

2. **Przywróć compose sprzed migracji** (commit zapisany w `backups/pre_cutover_commit.txt`):

   ```bash
   COMMIT=$(cat backups/pre_cutover_commit.txt)
   git checkout "$COMMIT" -- docker/docker-compose.prod.yml
   ```

3. **Uruchom stary projekt `docker`:**

   ```bash
   sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d
   ```

4. **Weryfikacja:**

   ```bash
   curl -fsS http://127.0.0.1:8000/health
   sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production exec db \
     psql -U postgres -d ksef_backend -c "SELECT COUNT(*) FROM invoices;"
   ```

5. **Nigdy** `docker volume rm docker_postgres_data`.

6. Przywróć compose prep z git gdy problem zdiagnozowany:

   ```bash
   git checkout production -- docker/docker-compose.prod.yml
   ```

### Rollback z backupu SQL (ostateczność)

Tylko jeśli wolumen uszkodzony — **nie** standardowy scenariusz:

```bash
# STOP wszystkich kontenerów DB
# restore z backups/pre_ifg_project_*.sql — procedura DBA
```

---

## Checklist operatora

Wydrukuj / odhaczaj podczas cutover:

```
[ ] P1–P7 wymagania wstępne OK
[ ] Commit przed migracją zapisany (pre_cutover_commit.txt)
[ ] Krok 1: Backup SQL OK (plik > 0)
[ ] Krok 2: git pull OK
[ ] Krok 3: compose config gate PASS (docker_postgres_data external)
[ ] Krok 4: docker-* Exited, NIE usunięte
[ ] Krok 5: compose up -d OK, ifg-* Running
[ ] Krok 6: health + pg_isready + COUNT invoices OK
[ ] Krok 7: guardian deploy check OK
[ ] Krok 8: test funkcjonalny IFG OK
[ ] Krok 9: docker rm docker-* wykonane
[ ] Krok 10: CM Project ifg widoczny
[ ] GO — migracja zakończona
```

**Jeśli którykolwiek krok 3–8 FAIL → Rollback, bez Kroku 9.**

---

## Guardian workflow (preferowane)

Zamiast ręcznych kroków SSH użyj workflow `ifg.container.cutover`:

```bash
# Symulacja (bez mutacji)
python3 scripts/guardian.py ifg cutover run --dry-run

# Cutover LIVE: backup → pull → gates → up → health → guardian verify
python3 scripts/guardian.py ifg cutover run --yes

# Po testach funkcjonalnych: cleanup legacy docker-*
python3 scripts/guardian.py ifg cutover run --yes --confirm-functional --cleanup

# Rollback
python3 scripts/guardian.py ifg cutover rollback --yes
```

Szczegóły: [GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md](../reports/GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md)

---

## Powiązane dokumenty

| Dokument | Rola |
|----------|------|
| [GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md](../reports/GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md) | Guardian workflow — komendy i GO/NO-GO |
| [GWO_IFG_002A_COMPOSE_PROJECT_PREP.md](../reports/GWO_IFG_002A_COMPOSE_PROJECT_PREP.md) | Prep compose w repo |
| [GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md](../reports/GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md) | Analiza CM (scenariusz B) |
| [IFG_CONTAINER_MANAGER_MIGRATION.md](../reports/IFG_CONTAINER_MANAGER_MIGRATION.md) | Raport techniczny pełny |
| [GUARDIAN2_DEPLOY.md](../GUARDIAN2_DEPLOY.md) | Guardian deploy (read-only check) |

---

*Runbook zatwierdzony 2026-07-06. Migracja nie wykonana w ramach przygotowania dokumentacji.*
