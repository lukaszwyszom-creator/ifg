# IFG DS723+ — Container Manager project (compose `name: ifg`)

**Data:** 2026-07-05  
**Host:** DS723+ (`ds723`)  
**Repo:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Branch / commit:** `production` @ `a405646`  
**Status operacji:** **diagnoza wykonana — migracja NIE wykonana** (wymaga potwierdzenia operatora)

---

## 1. Cel

Ujednolicić stack IFG (API, worker, PostgreSQL, frontend montowany w API) pod **jedną nazwą projektu Compose `ifg`**, widoczną w Synology Container Manager → **Projekt**, zamiast luźnych kontenerów `docker-api-1`, `docker-worker-1`, `docker-db-1` (projekt `docker`).

---

## 2. Obecny stan (diagnoza 2026-07-05)

### 2.1 Repozytorium

| Pole | Wartość |
|------|---------|
| `pwd` | `/volume1/docker/ifg_v2/ifg_standalone` |
| branch | `production` |
| commit | `a405646` — fix: KSeF purchase sync 429 resume for API and worker |

### 2.2 Plik Compose

- Plik: `docker/docker-compose.prod.yml`
- **`name:` w pliku:** **brak**
- **`COMPOSE_PROJECT_NAME` w `.env.production`:** **brak**
- Domyślna nazwa projektu Compose v2: **`docker`** (katalog pliku compose = `docker/`)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config | grep '^name:'
# name: docker
```

Rozwiązane nazwy zasobów (projekt `docker`):

| Zasób | Faktyczna nazwa Docker |
|-------|-------------------------|
| Sieć | `docker_ifg_prod` |
| Wolumen DB | `docker_postgres_data` |
| Kontener API | `docker-api-1` |
| Kontener worker | `docker-worker-1` |
| Kontener DB | `docker-db-1` |

### 2.3 Kontenery

| Nazwa | Status | Obraz | Projekt Compose |
|-------|--------|-------|-----------------|
| `docker-api-1` | **Exited (137)** ~20 h temu | `ifg-api:latest` | `docker` |
| `docker-worker-1` | **Exited (137)** ~20 h temu | `ifg-api:latest` | `docker` |
| `docker-db-1` | **Exited (0)** ~20 h temu | `postgres:17` | `docker` |
| `cloudflared-ifg` | **Up** | `cloudflare/cloudflared` | **poza compose IFG** |
| `syncthing-1` | Up | syncthing | projekt `syncthing` |

Etykieta `com.docker.compose.project.working_dir` na kontenerach IFG:  
`/volume1/docker/ifg_v2/ifg_standalone/docker`

Frontend produkcyjny **nie jest osobnym kontenerem** — montowany do API:

```yaml
../frontend-react/dist:/app/frontend-react/dist:ro
```

### 2.4 Sieci

```
docker_ifg_prod   bridge   (używana przez stack IFG)
```

### 2.5 Wolumeny (prod IFG)

| Wolumen | Utworzony | Etykieta projektu | Mountpoint |
|---------|-----------|-------------------|------------|
| **`docker_postgres_data`** | 2026-05-04 | `docker` / `postgres_data` | `/volume1/@docker/volumes/docker_postgres_data/_data` |
| `docker_ksef_keys` | 2026-04-16 | `docker` / `ksef_keys` | (legacy — **nie** w obecnym `docker-compose.prod.yml`) |

**Wolumen produkcyjny PostgreSQL:** `docker_postgres_data` — **nie dotykać, nie usuwać.**

---

## 3. Ryzyko dla bazy danych

### 3.1 Niebezpieczna operacja (❌ NIE WYKONYWAĆ)

```bash
sudo docker compose -p ifg -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

**Bez pinowania wolumenu** Compose utworzy **nowy** wolumen:

```
ifg_postgres_data   # PUSTY
```

Kontener DB wystartowałby na **świeżej** bazie. Stare dane pozostałyby w `docker_postgres_data`, ale aplikacja ich **nie zobaczyłaby**. To de facto utrata produkcji z perspektywy IFG.

Weryfikacja:

```bash
sudo docker compose -p ifg -f docker/docker-compose.prod.yml --env-file .env.production config | grep postgres_data
# name: ifg_postgres_data
```

### 3.2 Bezpieczna zasada

Przy zmianie nazwy projektu na `ifg`:

1. **Zachować** istniejący wolumen `docker_postgres_data` (`external: true` + `name:`).
2. Opcjonalnie **zachować** sieć `docker_ifg_prod` (`external: true`) lub pozwolić Compose utworzyć `ifg_ifg_prod` (nowa sieć — OK przy cold start, bez konfliktu z danymi).
3. **Nie** uruchamiać `docker volume rm`.
4. **Nie** uruchamiać `docker compose down -v`.

### 3.3 Stare kontenery `docker-*`

Po podniesieniu projektu `ifg` powstaną **nowe** nazwy (`ifg-api-1`, …). Stare zatrzymane `docker-*` można usunąć **dopiero po** weryfikacji health API i DB — usunięcie kontenerów **nie kasuje** wolumenu `docker_postgres_data`.

---

## 4. Czy trzeba dodać `name: ifg` do compose?

**Tak — zalecane.**

Synology Container Manager grupuje stacki według **nazwy projektu Compose**. Bez `name:` projekt bierze nazwę katalogu pliku compose → **`docker`**, co jest mylące (nie „IFG”).

Opcje (od najlepszej):

| Metoda | Efekt w Container Manager |
|--------|---------------------------|
| **`name: ifg` w `docker-compose.prod.yml`** | stabilna nazwa **ifg**, niezależna od cwd |
| `COMPOSE_PROJECT_NAME=ifg` w `.env.production` | działa, ale mniej widoczne w repo niż `name:` |
| `-p ifg` przy każdym wywołaniu | łatwo zapomnieć; Guardian/skrypty muszą pamiętać flagę |

**Rekomendacja:** dodać na górze `docker/docker-compose.prod.yml`:

```yaml
name: ifg
```

oraz **pin wolumenu DB** (patrz sekcja 5).

---

## 5. Proponowany bezpieczny plan

### Faza A — zmiana w repozytorium (bez restartu)

Edycja `docker/docker-compose.prod.yml`:

```yaml
name: ifg

# ... services bez zmian ...

volumes:
  postgres_data:
    name: docker_postgres_data
    external: true

networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

Uzasadnienie:

- Projekt w UI: **ifg**
- Kontenery: `ifg-api-1`, `ifg-worker-1`, `ifg-db-1`
- **Te same** dane Postgres co dziś
- **Ta sama** sieć (opcjonalnie — można pominąć pin sieci i utworzyć nową `ifg_ifg_prod`; bezpieczniejsze dla DNS wewnętrznego jest pin lub recreate całego stacku na nowej sieci przy zatrzymanych kontenerach)

Aktualizacja komentarza uruchomienia w nagłówku pliku:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

(bez `-p ifg` — nazwa z pola `name:`)

### Faza B — weryfikacja przed `up` (na DS723+)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull   # po merge zmian compose

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config \
  | grep -E '^name:|postgres_data|ifg_prod'
```

**Oczekiwane:**

```
name: ifg
name: docker_ifg_prod          # sieć (jeśli external)
name: docker_postgres_data     # wolumen — KRYTYCZNE
```

**Nie wolno zobaczyć:** `ifg_postgres_data` jako nowy nie-external volume.

### Faza C — podniesienie stacku (kontenery obecnie zatrzymane — **bezpieczne**)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

Bez `--build` przy samym renames — obraz `ifg-api:latest` już istnieje. Przy deploy kodu dodać `--build api`.

### Faza D — weryfikacja po `up`

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
curl -fsS http://127.0.0.1:8000/health

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  pg_isready -U postgres -d ksef_backend

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
  psql -U postgres -d ksef_backend -c "SELECT COUNT(*) FROM invoices;"
```

### Faza E — sprzątanie (po potwierdzeniu health)

```bash
# tylko zatrzymane stare kontenery — NIE usuwa wolumenu
sudo docker rm docker-api-1 docker-worker-1 docker-db-1
```

### Faza F — Container Manager (UI)

1. Otwórz **Container Manager → Projekt**.
2. Sprawdź projekt **`ifg`** z usługami: `api`, `worker`, `db`.
3. Stary projekt **`docker`** powinien zniknąć po usunięciu starych kontenerów (wolumen `docker_postgres_data` nadal istnieje jako external).

**Uwaga:** `cloudflared-ifg` pozostanie **poza** projektem IFG, dopóki nie zostanie dodany do compose lub osobnego projektu `ifg-tunnel`.

---

## 6. Dokładne komendy — wykonanie

| Krok | Wykonano? |
|------|-----------|
| Diagnoza stanu | **Tak** (2026-07-05) |
| Edycja `docker-compose.prod.yml` (`name: ifg`) | **Nie** — tylko propozycja w tym raporcie |
| `git pull` + `compose up` na DS723+ | **Nie** — oczekuje potwierdzenia operatora |
| Sprzątanie `docker-*` | **Nie** |

---

## 7. Wynik po operacji

**N/D** — migracja nie została wykonana w ramach tej sesji.

Ostatni znany stan (przed migracją):

| Check | Wynik |
|-------|--------|
| `docker compose ps` | api/worker/db **Exited** (projekt `docker`) |
| Health API | **niedostępny** (API zatrzymane) |
| DB | wolumen `docker_postgres_data` **istnieje**, dane zachowane |
| Container Manager → Projekt **ifg** | **nie** — obecnie widoczny jako projekt **`docker`** (lub luźne kontenery) |

---

## 8. Odpowiedzi na pytania kontrolne

| # | Pytanie | Odpowiedź |
|---|---------|-----------|
| 1 | Branch / commit | `production` / `a405646` |
| 2 | `compose config` | projekt **`docker`**, wolumen **`docker_postgres_data`**, sieć **`docker_ifg_prod`** |
| 3 | Nazwa projektu w compose | **brak** `name:` i `COMPOSE_PROJECT_NAME` |
| 4 | Kontenery / sieci / wolumeny | patrz sekcja 2; stack **zatrzymany**; `cloudflared-ifg` osobno |
| 5 | `up -d` z `-p ifg` bez pin wolumenu | **utworzy nowy pusty wolumen** — **NIE** |
| 6 | Czy dodać `name: ifg` | **Tak**, plus **`external` pin** na `docker_postgres_data` |

---

## 9. Rekomendacja końcowa

1. **Zatwierdzić** diff compose (sekcja 5A) i wdrożyć przez git na DS723+.
2. **Zweryfikować** `compose config` — wolumen musi wskazywać `docker_postgres_data`.
3. **Uruchomić** `up -d` — kontenery są zatrzymane, ryzyko niskie przy poprawnym pinie wolumenu.
4. **Potwierdzić** health + liczba rekordów w DB.
5. **Usunąć** stare kontenery `docker-*` (nie wolumen).
6. **Sprawdzić** Synology Container Manager → Projekt **`ifg`**.

---

## 10. Powiązane pliki

- `docker/docker-compose.prod.yml`
- `.env.production`
- Guardian deploy: `scripts/guardian2.py` — po zmianie `name:` zaktualizować komendy compose (usunąć implicit poleganie na projekcie `docker`)

---

*Raport przygotowany bez operacji destrukcyjnych. Migracja wymaga explicit OK operatora.*
