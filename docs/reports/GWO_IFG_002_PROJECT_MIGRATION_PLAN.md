# GWO-IFG-002 — Plan migracji IFG → Synology Container Manager Projekt

**Data:** 2026-07-06  
**Środowisko:** DS723+ (produkcja), Mac mini (Guardian / dev)  
**Repo prod:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Branch docelowy:** `production`  
**Architektura Guardiana:** [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md](../guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md) — Etap 1 (`ComposeBackend`)  
**Status:** **plan i procedura — migracja NIE wykonana**

Powiązane raporty:
- [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md) — diagnoza DS723+ (2026-07-05)
- [IFG_DS723_CONTAINER_MANAGER_PROJECT.md](./IFG_DS723_CONTAINER_MANAGER_PROJECT.md)
- [GWO_G003_IMPLEMENTATION_STAGE1.md](./GWO_G003_IMPLEMENTATION_STAGE1.md) — Execution Layer Etap 1

---

## Streszczenie wykonawcze

| Aspekt | Werdykt |
|--------|---------|
| Cel migracji | Projekt Compose **`ifg`** widoczny w Container Manager zamiast luźnych kontenerów `docker-*-1` |
| Dane PostgreSQL | Wolumen **`docker_postgres_data`** — **nie ruszać, nie usuwać** |
| Mechanizm bezpieczeństwa | `name: ifg` **+** `external: true` na wolumenie (i zalecenie: sieci) |
| Guardian | **`ComposeBackend` działa po migracji bez zmian kodu** — używa nazw **serwisów**, nie kontenerów |
| SynologyProjectBackend | **Nie w scope** — nadal SSH + `docker compose` |
| Blokada wykonania | **Brak zmian compose w repo** + brak backupu na DS723+ |

---

## 1. Analiza techniczna

### 1.1 Obecny `docker compose config` (stan repo, symulacja lokalna)

Plik: `docker/docker-compose.prod.yml` — **bez** top-level `name:`.

Uruchomienie z **repo root** (zgodnie z Guardianem i runbookiem):

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config
```

**Efekt (symulacja lokalna 2026-07-06, Compose v2):**

| Pole | Wartość |
|------|---------|
| `name:` (projekt) | **`docker`** — z katalogu pliku compose (`docker/`) |
| Wolumen DB (resolved) | **`docker_postgres_data`** |
| Sieć (resolved) | **`docker_ifg_prod`** |

> **Uwaga:** Przy uruchomieniu z repo root projekt nadal nazywa się `docker`, ponieważ Compose v2 bierze nazwę z katalogu **zawierającego plik compose** (`docker/`), nie z cwd.

### 1.2 Nazwy zasobów — stan produkcyjny (diagnoza 2026-07-05)

#### Kontenery

| Kontener | Status (2026-07-05) | Obraz | Projekt Compose |
|----------|---------------------|-------|-----------------|
| `docker-api-1` | Exited (137) | `ifg-api:latest` | `docker` |
| `docker-worker-1` | Exited (137) | `ifg-api:latest` | `docker` |
| `docker-db-1` | Exited (0) | `postgres:17` | `docker` |

Poza stackiem IFG: `cloudflared-ifg` (Up) — **nie** w `docker-compose.prod.yml`.

#### Sieci

| Nazwa Docker | Rola |
|--------------|------|
| `docker_ifg_prod` | Sieć bridge stacku IFG |

#### Wolumeny

| Nazwa Docker | Rola | Mountpoint (typowo) |
|--------------|------|---------------------|
| **`docker_postgres_data`** | **Produkcyzna baza PostgreSQL** | `/volume1/@docker/volumes/docker_postgres_data/_data` |
| `docker_ksef_keys` | Legacy — nie w obecnym compose prod | — |

#### Bind mounty (niezależne od nazwy projektu)

| Usługa | Mount | Ścieżka hosta (względem `docker/`) |
|--------|-------|--------------------------------------|
| api | frontend | `../frontend-react/dist` → `/app/frontend-react/dist:ro` |
| api | env | `../.env.production` → `/app/.env:ro` |
| worker | env | `../.env.production` → `/app/.env:ro` |

### 1.3 `name:` vs `COMPOSE_PROJECT_NAME`

| Mechanizm | Stan w repo |
|-----------|-------------|
| `name:` w `docker-compose.prod.yml` | **brak** |
| `COMPOSE_PROJECT_NAME` w `.env.production` | **brak** (plik poza repo) |
| Efektywna nazwa projektu | **`docker`** |

**Rekomendacja:** dodać `name: ifg` **w pliku compose** (widoczne w git, stabilne, niezależne od cwd).

### 1.4 Wpływ dodania `name: ifg` — symulacja

#### Wariant NIEBEZPIECZNY — samo `name: ifg` (bez pinu wolumenu)

```
name: ifg
    name: ifg_ifg_prod          ← NOWA sieć
    name: ifg_postgres_data     ← NOWY PUSTY WOLUMEN ⚠️
```

| Zasób | Dziś (`docker`) | Po samym `name: ifg` |
|-------|-----------------|----------------------|
| Wolumen DB | `docker_postgres_data` | **`ifg_postgres_data` (pusty)** |
| Sieć | `docker_ifg_prod` | `ifg_ifg_prod` |
| Kontenery | `docker-*-1` | `ifg-*-1` |

**Skutek:** aplikacja startuje na **pustej bazie**. Stare dane zostają w `docker_postgres_data`, ale IFG ich **nie widzi** — to de facto utrata produkcji.

#### Wariant BEZPIECZNY — `name: ifg` + external pin (symulacja lokalna)

```
name: ifg
    name: docker_ifg_prod       ← istniejąca sieć (external)
    name: docker_postgres_data  ← istniejący wolumen (external) ✓
```

| Zasób | Fizyczna nazwa | Zmiana danych |
|-------|----------------|---------------|
| Wolumen DB | `docker_postgres_data` | **Brak** |
| Sieć | `docker_ifg_prod` | **Brak** (pin) lub nowa sieć (patrz §1.6) |
| Kontenery | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` | **Nowe nazwy**, ten sam wolumen |

### 1.5 Czy `postgres_data` musi być `external: true`?

**Tak — obowiązkowo** przy zmianie projektu z `docker` na `ifg`.

```yaml
volumes:
  postgres_data:
    name: docker_postgres_data
    external: true
```

Bez tego Compose utworzy `ifg_postgres_data` — **krytyczne ryzyko utraty danych z perspektywy aplikacji**.

### 1.6 Sieć — czy potrzebne `network aliases`?

**Nie.** Stack używa domyślnego DNS Compose na sieci bridge:

- Worker/API łączą się z bazą przez hostname **`db`** (nazwa serwisu), nie `docker-db-1`.
- Brak custom `aliases:` w obecnym compose.
- Po migracji serwisy nadal: `api`, `worker`, `db` na sieci `ifg_prod`.

**Pin sieci (zalecany):**

```yaml
networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

| Opcja | Wpływ na DB | Wpływ na DNS wewnętrzny |
|-------|-------------|-------------------------|
| Pin `docker_ifg_prod` | Brak | Stabilna sieć; kontenery startują na istniejącej sieci |
| Nowa sieć `ifg_ifg_prod` | Brak (przy pinie wolumenu) | OK przy cold start (kontenery zatrzymane); worker/api muszą wystartować razem z db |

Przy **zatrzymanym stacku** (stan 2026-07-05) obie opcje są akceptowalne dla danych DB. **Pin sieci** upraszcza rollback.

### 1.7 Frontend bind mount — zgodność po migracji

**Bez zmian.** Mounty są względem katalogu pliku compose (`docker/`):

```yaml
volumes:
  - ../frontend-react/dist:/app/frontend-react/dist:ro
```

Zmiana `name: ifg` **nie wpływa** na ścieżki bind mountów. Guardian rsync nadal celuje w `{remote_path}/frontend-react/dist/`.

### 1.8 KSeF i konfiguracja

| Element | Zależność od nazwy projektu | Uwagi |
|---------|----------------------------|-------|
| `.env.production` | **Nie** | Bind mount — bez zmian |
| Sekrety KSeF w DB | **Nie** | W `docker_postgres_data` — pin wolumenu chroni |
| Sesje KSeF | **Nie** (po restarcie wymagane ponowne logowanie) | Oczekiwane po downtime |
| `cloudflared-ifg` | **Nie** | Osobny kontener; origin `http://127.0.0.1:8000` — bez zmian |

---

## 2. Guardian — zgodność `ComposeBackend`

### 2.1 Jak Guardian woła compose dziś

Ścieżka Etap 1 (GWO-G-003):

```
IntentExecutor → DeploymentEngine.deploy() → OperationEngine → ComposeBackend → ComposeExecutor
```

Komendy SSH (repo root na DS723+):

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
docker compose -f "docker/docker-compose.prod.yml" --env-file ".env.production" up -d --remove-orphans api worker
docker compose -f "docker/docker-compose.prod.yml" --env-file ".env.production" ps
docker compose -f "docker/docker-compose.prod.yml" --env-file ".env.production" logs --tail=50 api worker
```

**Brak flagi `-p docker` / `-p ifg`** — po dodaniu `name: ifg` w pliku compose projekt wynika z YAML.

### 2.2 Czy `ComposeBackend` zadziała po migracji `docker` → `ifg`?

**Tak — bez zmian kodu.**

| Mechanizm Guardian | Używa nazwy kontenera? | Po migracji |
|--------------------|------------------------|-------------|
| `ComposeExecutor.execute_up` | **Nie** — serwisy `api worker` | OK |
| `compose ps` parser | **Nie** — kolumna `Service` (`api`, `worker`, `db`) | OK |
| Doctor / recover | **Nie** — `REQUIRED_COMPOSE_SERVICES` | OK |
| `alembic` via compose exec | **Nie** — `exec -T api` | OK |
| Health check | **Nie** — `curl :8000/health` | OK |
| Rollback snapshot | **Nie** — compose exec api | OK |

**Jedyna widoczna zmiana:** w output `docker compose ps` nazwy kontenerów będą `ifg-api-1` zamiast `docker-api-1` — parser Guardiana tego nie wymaga.

### 2.3 Potencjalne pułapki (nie blokują, ale uwaga operatora)

| Pułapka | Skutek | Mitygacja |
|---------|--------|-----------|
| Uruchomienie compose z katalogu `docker/` zamiast repo root | Możliwa inna nazwa projektu | Runbook: **zawsze repo root**; Guardian robi `cd repo` |
| Ręczne `-p docker` po migracji | Równoległy stack / zły wolumen | **Zakaz** `-p docker` po merge `name: ifg` |
| Dokumenty wspominające `docker-api-1` | Myli operatora | Kosmetyka docs — nie wpływa na deploy |

### 2.4 Minimalne poprawki Guardiana

**Wymagane przed migracją: brak.**

Opcjonalne (osobne GWO, nie blokuje migracji):

| Poprawka | Priorytet | Opis |
|----------|-----------|------|
| Gate `compose config \| grep docker_postgres_data` przed `up` | Średni | Pre-flight w deploy pipeline |
| Stała dokumentacyjna `COMPOSE_PROJECT_NAME = "ifg"` w config | Niski | Tylko docs |
| Aktualizacja przykładów w runbookach (`ifg-*-1`) | Niski | Kosmetyka |

---

## 3. Proponowana zmiana compose (Wariant A — jedyny akceptowalny)

**Plik:** `docker/docker-compose.prod.yml`

```yaml
name: ifg

# ... services: api, worker, db — BEZ ZMIAN MERYTORYCZNYCH ...

volumes:
  postgres_data:
    name: docker_postgres_data
    external: true

networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

**Efekt docelowy:**

| Element | Wartość |
|---------|---------|
| Projekt Compose / Container Manager | **`ifg`** |
| Kontenery | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` |
| Wolumen DB (fizyczny) | **`docker_postgres_data`** (bez zmian) |
| Sieć (fizyczna) | **`docker_ifg_prod`** (przy pinie) |

> **Status repo (2026-07-06):** powyższy diff **NIE jest jeszcze w `production`**. To prerequisite migracji.

---

## 4. Procedura migracji — Container Manager

### Faza 0 — Przygotowanie (Mac mini / git)

| Krok | Opis |
|------|------|
| 0.1 | Zatwierdzić diff compose (Wariant A) |
| 0.2 | Zaktualizować komentarz nagłówka w `docker-compose.prod.yml` |
| 0.3 | Merge / push na `production` |
| 0.4 | **Nie** wykonywać `up` na DS723+ przed Fazą 1 |

### Faza 1 — Backup (DS723+) — **OBOWIĄZKOWY**

#### 1A. Backup wolumenu PostgreSQL (rekomendowany — stack zatrzymany)

```bash
# Katalog backupu — dostosuj datę
BACKUP_DIR="/volume1/docker/ifg_v2/backups/pre-ifg-migration-$(date +%Y%m%d)"
sudo mkdir -p "$BACKUP_DIR"

# Archiwum surowych plików PG (bez uruchamiania Postgres)
sudo tar czf "$BACKUP_DIR/docker_postgres_data.tgz" \
  -C /volume1/@docker/volumes/docker_postgres_data _data

# Weryfikacja rozmiaru (musi być > 0, typowo dziesiątki MB+)
ls -lh "$BACKUP_DIR/docker_postgres_data.tgz"
```

#### 1B. Backup logiczny SQL (opcjonalny, wymaga chwilowego startu DB)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Tymczasowo uruchom TYLKO db ze STARYM projektem (przed pull z name: ifg)
sudo docker compose -p docker -f docker/docker-compose.prod.yml \
  --env-file .env.production up -d db

# Poczekaj na healthy
sudo docker compose -p docker -f docker/docker-compose.prod.yml \
  --env-file .env.production exec db pg_isready -U postgres -d ksef_backend

# Dump
sudo docker compose -p docker -f docker/docker-compose.prod.yml \
  --env-file .env.production exec -T db \
  pg_dump -U postgres -d ksef_backend -Fc \
  > "$BACKUP_DIR/ksef_backend.dump"

# Zatrzymaj db przed migracją nazwy
sudo docker compose -p docker -f docker/docker-compose.prod.yml \
  --env-file .env.production stop db api worker
```

#### 1C. Backup konfiguracji

```bash
sudo cp /volume1/docker/ifg_v2/ifg_standalone/.env.production \
  "$BACKUP_DIR/.env.production.backup"

sudo cp /volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml \
  "$BACKUP_DIR/docker-compose.prod.yml.before-migration"
```

#### 1D. Backup frontendu (jeśli dist istnieje na NAS)

```bash
sudo tar czf "$BACKUP_DIR/frontend-dist.tgz" \
  -C /volume1/docker/ifg_v2/ifg_standalone frontend-react/dist 2>/dev/null || true
```

### Faza 2 — Verify (read-only, przed `up`)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Stan repo
git fetch origin && git checkout production && git pull origin production
git rev-parse --short HEAD

# GATE — obowiązkowy po pull
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config \
  | grep -E '^name:|postgres_data|ifg_prod'
```

**Oczekiwany output (MUSI):**

```
name: ifg
name: docker_ifg_prod
name: docker_postgres_data
```

**STOP jeśli widzisz:** `ifg_postgres_data` bez `external: true`.

```bash
# Potwierdzenie wolumenu
sudo docker volume inspect docker_postgres_data \
  --format 'Name={{.Name}} Mountpoint={{.Mountpoint}}'

# Potwierdzenie — brak działającego równoległego stacku
sudo docker ps -a --filter "name=ifg-" --format '{{.Names}} {{.Status}}'
sudo docker ps -a --filter "name=docker-" --format '{{.Names}} {{.Status}}'
```

### Faza 3 — Utworzenie projektu / pierwszy start

> **Nie tworzymy projektu ręcznie w UI przed compose.**  
> Projekt **`ifg`** powstaje automatycznie po `compose up` z polem `name: ifg`.

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Pierwszy start (stack obecnie zatrzymany — bezpieczne okno)
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d

# Jeśli równolegle deploy kodu:
# sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api
# sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

**Container Manager (UI) — po `up`:**

1. Otwórz **Container Manager → Projekt**.
2. Odśwież widok — powinien pojawić się projekt **`ifg`**.
3. W projekcie: 3 usługi — `api`, `worker`, `db`.
4. Jeśli projekt nie widoczny: sprawdź logi DSM / zrestartuj widok CM; **nie** twórz duplikatu projektu z UI bez weryfikacji compose.

### Faza 4 — Health check

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Kontenery
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps

# Etykieta projektu
sudo docker inspect ifg-db-1 \
  --format '{{index .Config.Labels "com.docker.compose.project"}}'
# Oczekiwane: ifg

# Mount DB — MUSI wskazywać docker_postgres_data
sudo docker inspect ifg-db-1 \
  --format '{{range .Mounts}}{{.Type}} {{.Name}} -> {{.Destination}}{{"\n"}}{{end}}'

# Health API
curl -fsS http://127.0.0.1:8000/health

# PostgreSQL
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  pg_isready -U postgres -d ksef_backend

# Sanity danych
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  psql -U postgres -d ksef_backend -c "SELECT COUNT(*) FROM invoices;"

# Worker (brak crash loop)
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs --tail=30 worker

# Frontend (plik w kontenerze)
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec api \
  ls -la /app/frontend-react/dist/ | head -5

# KSeF (po zalogowaniu operatora — manual)
# UI → KSeF Connect → sesja aktywna
```

### Faza 5 — Sprzątanie (tylko po pełnym OK)

```bash
# Usuń WYŁĄCZNIE stare zatrzymane kontenery — NIE wolumeny
sudo docker rm docker-api-1 docker-worker-1 docker-db-1 2>/dev/null || true

# Weryfikacja — brak osieroconych kontenerów projektu docker
sudo docker ps -a --filter "label=com.docker.compose.project=docker" --format '{{.Names}}'
```

**Zakazane komendy:**

```bash
# NIGDY:
docker compose down -v
docker volume rm docker_postgres_data
docker volume rm ifg_postgres_data   # jeśli przypadkowo powstał — najpierw STOP, analiza
```

### Faza 6 — Weryfikacja deploy Guardiana (Mac mini)

```bash
# Dry-run (bez mutacji)
python3 -m ifg_guardian deploy run --dry-run

# Po akceptacji — deploy testowy lub standardowy
# python3 -m ifg_guardian deploy run --yes
```

Potwierdź w raporcie deploy: `compose ps` pokazuje projekt **ifg**, health OK.

---

## 5. Rollback — w dowolnym momencie, bez utraty danych

### Kiedy rollback

- Gate `compose config` wskazuje zły wolumen po `git pull`
- DB startuje bez oczekiwanych tabel / `COUNT(*)=0`
- API health fail > 5 min po `up`
- Podejrzenie utworzenia `ifg_postgres_data`

### Procedura rollback

**Dane produkcyjne są w `docker_postgres_data`. Rollback dotyczy projektu Compose i kontenerów, nie wolumenu.**

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# 1. Zatrzymaj nowy stack (projekt ifg)
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop

# 2. Przywróć poprzedni compose (bez name: ifg / bez external)
git checkout <commit_przed_migracja> -- docker/docker-compose.prod.yml

# 3. Uruchom stary projekt docker
sudo docker compose -p docker -f docker/docker-compose.prod.yml \
  --env-file .env.production up -d

# 4. Weryfikacja
curl -fsS http://127.0.0.1:8000/health
sudo docker compose -p docker -f docker/docker-compose.prod.yml \
  --env-file .env.production exec db \
  psql -U postgres -d ksef_backend -c "SELECT COUNT(*) FROM invoices;"

# 5. Usuń kontenery ifg-* (opcjonalnie, po weryfikacji)
sudo docker rm ifg-api-1 ifg-worker-1 ifg-db-1 2>/dev/null || true
```

**Jeśli przypadkowo utworzono `ifg_postgres_data`:**

1. **STOP** — nie uruchamiaj aplikacji na tym wolumenie.
2. Sprawdź: `sudo docker volume inspect ifg_postgres_data` — jeśli pusty/nowy, usuń **tylko ten wolumen** po potwierdzeniu, że `docker_postgres_data` jest nienaruszony.
3. Przywróć compose z pinem `external: true`.

**Przywrócenie z backupu wolumenu (ostateczność):**

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop db
sudo tar xzf "$BACKUP_DIR/docker_postgres_data.tgz" \
  -C /volume1/@docker/volumes/docker_postgres_data
# następnie up -d db
```

---

## 6. Ryzyka

| # | Ryzyko | Poważność | Opis | Mitygacja |
|---|--------|-----------|------|-----------|
| R1 | Nowy pusty wolumen `ifg_postgres_data` | **Krytyczne** | Aplikacja na pustej bazie; stare dane „orphaned” | `external: true` + gate §4 Faza 2 |
| R2 | `docker compose down -v` | **Krytyczne** | Kasuje wolumen projektu | Zakaz; checklist operatora |
| R3 | Równoległy stack (`-p docker` + `ifg`) | Wysokie | Dwa stacki, chaos operacyjny | Jeden projekt; zakaz `-p docker` po migracji |
| R4 | Uruchomienie `up` przed backupem | Wysokie | Brak punktu przywrócenia | Faza 1 przed Fazą 3 |
| R5 | Zła ścieżka cwd (`docker/` vs repo root) | Średnie | Inna nazwa projektu | Zawsze repo root; Guardian `cd repo` |
| R6 | Zmiana nazw kontenerów | Niskie | `docker-*` → `ifg-*` | Guardian używa serwisów; docs do aktualizacji |
| R7 | Sieć bez pinu | Niskie | Nowa `ifg_ifg_prod` | Akceptowalne przy cold start; pin zalecany |
| R8 | `cloudflared-ifg` poza projektem | Niskie | Tunel osobno | Świadomie; origin :8000 bez zmian |
| R9 | KSeF sesja wygasa po restarcie | Niskie | Wymaga ponownego logowania | Oczekiwane; nie utrata danych |
| R10 | DSM UI „Utwórz projekt” bez compose pin | Wysokie | UI może utworzyć zły wolumen | Compose-first; gate przed up |
| R11 | Guardian deploy bez gate wolumenu | Średnie | Deploy na złym projekcie | Gate w Fazie 2; opcjonalny pre-flight w GWO |
| R12 | Stan DS723+ nieaktualny od 2026-07-05 | Średnie | Stack mógł się zmienić | Odświeżyć diagnostykę w Fazie 2 |

---

## 7. Checklista operatora

### Przed migracją

- [ ] Zaakceptowano Wariant A (compose diff)
- [ ] Diff `name: ifg` + `external` zmergowany na `production`
- [ ] Zaplanowano okno maintenance (stack obecnie zatrzymany — preferowany moment)
- [ ] Wykonano backup wolumenu `docker_postgres_data` (§4 Faza 1A)
- [ ] Wykonano backup `.env.production` (§4 Faza 1C)
- [ ] Opcjonalnie: pg_dump (§4 Faza 1B)
- [ ] Potwierdzono rozmiar backupu > 0
- [ ] `git pull` na DS723+ — commit z compose diff obecny

### Gate przed startem

- [ ] `compose config | grep` → `name: ifg`
- [ ] `compose config | grep` → `docker_postgres_data` (NIE `ifg_postgres_data`)
- [ ] `docker volume inspect docker_postgres_data` — wolumen istnieje
- [ ] Brak działających kontenerów `ifg-*` (brak równoległego stacku)

### Migracja

- [ ] `compose up -d` wykonane z repo root
- [ ] Kontenery `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` — Up
- [ ] Etykieta `com.docker.compose.project=ifg`
- [ ] Mount DB → wolumen `docker_postgres_data`

### Weryfikacja

- [ ] `curl http://127.0.0.1:8000/health` → OK
- [ ] `pg_isready` → accepting connections
- [ ] `SELECT COUNT(*) FROM invoices` > 0
- [ ] Worker bez crash loop
- [ ] Frontend dist widoczny w kontenerze api
- [ ] Container Manager → Projekt **`ifg`** widoczny (3 usługi)
- [ ] `cloudflared-ifg` nadal Up (jeśli wymagany)

### Po migracji

- [ ] Usunięto stare kontenery `docker-*-1` (tylko kontenery)
- [ ] Guardian dry-run deploy OK
- [ ] Guardian deploy run (opcjonalny test) OK
- [ ] KSeF Connect — sesja aktywna (manual)
- [ ] Backupy przechowane w bezpiecznym miejscu

### Rollback (jeśli potrzebny)

- [ ] Stack `ifg` zatrzymany
- [ ] Przywrócono poprzedni compose
- [ ] Stack `docker` uruchomiony z `-p docker`
- [ ] Health + COUNT invoices OK
- [ ] **Nie** usunięto `docker_postgres_data`

---

## 8. Definition of Done

Migrację uznajemy za zakończoną dopiero gdy:

- [ ] Projekt IFG jest widoczny w Container Manager
- [ ] API działa
- [ ] Worker działa
- [ ] PostgreSQL działa
- [ ] Health = OK
- [ ] Guardian ComposeBackend nadal działa
- [ ] Można wykonać deploy

---

## 9. Go / No-Go

### Werdykt: **NO-GO** (migracja **nie** może być wykonana natychmiast)

Migracja jest **technicznie przygotowana i wykonalna**, ale **warunki wstępne nie są spełnione**.

### Co blokuje wykonanie teraz

| # | Bloker | Status |
|---|--------|--------|
| 1 | **Diff compose nie jest w repo `production`** — brak `name: ifg` i `external: true` w `docker/docker-compose.prod.yml` | **Niespełnione** |
| 2 | **Backup produkcyjny** wolumenu DB i `.env.production` na DS723+ | **Niewykonany** |
| 3 | **Odświeżona diagnostyka** DS723+ (stan stacku mógł się zmienić od 2026-07-05) | **Wymagana** |

### Co jest gotowe

| # | Element | Status |
|---|---------|--------|
| 1 | Plan migracji (Wariant A) | ✓ |
| 2 | Guardian `ComposeBackend` — zgodność bez zmian kodu | ✓ |
| 3 | Stack zatrzymany (2026-07-05) — korzystne okno | ✓ (do potwierdzenia) |
| 4 | Procedura rollback bez utraty wolumenu | ✓ |
| 5 | SynologyProjectBackend | Nie wymagany (Etap 2+) |

### Warunki przejścia na **GO**

1. Merge diff compose (§3) na `production` i `git pull` na DS723+
2. Wykonanie backupu (§4 Faza 1) z weryfikacją rozmiaru
3. Gate `compose config` (§4 Faza 2) — **musi** pokazać `docker_postgres_data`
4. Akceptacja operatora / okno maintenance
5. Odświeżona diagnostyka DS723+ potwierdza: wolumen `docker_postgres_data` istnieje, brak równoległego stacku `ifg`

### Po spełnieniu warunków

**GO** — migracja może być wykonana według §4 (Fazy 1–6) w szacowanym czasie **15–30 minut** (przy zatrzymanym stacku, bez rebuild obrazów).

---

**Koniec raportu.**  
Operacje wykonawcze nie zostały uruchomione. Następny krok: commit compose (Wariant A) → backup na DS723+ → GO → Faza 2–6.
