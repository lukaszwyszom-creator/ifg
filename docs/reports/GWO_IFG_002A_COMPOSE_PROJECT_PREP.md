# GWO-IFG-002A — Compose Project Prep (Container Manager → `ifg`)

**Data:** 2026-07-06  
**Środowisko docelowe:** DS723+ — `/volume1/docker/ifg_v2/ifg_standalone`  
**Branch:** `production`  
**Status:** **PREP COMPLETE** — migracja **NIE wykonana**  
**Powiązane:** [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md)

---

## Cel

Przygotować repozytorium do migracji IFG jako Synology Container Manager → Project **`ifg`**, z zachowaniem istniejącej bazy PostgreSQL (`docker_postgres_data`) i sieci (`docker_ifg_prod`).

**Zakres tego GWO:** wyłącznie zmiana pliku compose + walidacja lokalna.  
**Poza zakresem:** `docker compose up`, restart kontenerów, usunięcie wolumenów/sieci, zmiany na DS723+.

---

## Zmienione pliki

| Plik | Akcja |
|------|-------|
| `docker/docker-compose.prod.yml` | Zmodyfikowany — project name + external volume/network |
| `docs/reports/GWO_IFG_002A_COMPOSE_PROJECT_PREP.md` | Ten raport |

**Nie zmieniano:** `.env.production`, skryptów deploy, Guardian workflow, DS723+.

---

## Diff logiczny (`docker/docker-compose.prod.yml`)

### 1. Top-level project name

```yaml
+ name: ifg
```

**Przed:** brak `name:` → Compose domyślnie projekt **`docker`** (katalog pliku compose).  
**Po:** projekt **`ifg`** — zgodnie z docelową nazwą w Container Manager.

### 2. Wolumen PostgreSQL — pin do istniejącej bazy

```yaml
 volumes:
   postgres_data:
+    name: docker_postgres_data
+    external: true
```

**Przed:** wolumen zarządzany przez Compose → przy zmianie projektu na `ifg` powstałby **`ifg_postgres_data`** (pusta baza).  
**Po:** serwis `db` montuje **istniejący** wolumen produkcyjny `docker_postgres_data`.

### 3. Sieć — pin do istniejącej sieci

```yaml
 networks:
   ifg_prod:
-    driver: bridge
+    name: docker_ifg_prod
+    external: true
```

**Przed:** Compose tworzyłby sieć `ifg_ifg_prod` dla projektu `ifg`.  
**Po:** usługi `api`, `worker`, `db` dołączają do **istniejącej** sieci `docker_ifg_prod`.

### 4. Komentarz w nagłówku pliku

Dodano sekcję opisującą migrację Container Manager i powód external pinów.

---

## Walidacja lokalna: `docker compose config`

**Metoda (bez sekretów produkcyjnych):**

```bash
cd /Users/lukasz/projekty/ifg_standalone
cp .env.production.migration-test .env.production   # tylko POSTGRES_* testowe
docker compose -f docker/docker-compose.prod.yml config
rm -f .env.production
```

Plik `.env.production.migration-test` zawiera wyłącznie:

```
POSTGRES_DB=ksef_backend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=test
```

**Exit code:** `0` (sukces)

### Wymagane pola w rendered config — potwierdzenie

| Wymaganie | Wynik `docker compose config` |
|-----------|-------------------------------|
| `name: ifg` | ✅ pierwsza linia outputu: `name: ifg` |
| `name: docker_postgres_data` | ✅ sekcja `volumes.postgres_data.name` |
| `external: true` (volume) | ✅ `volumes.postgres_data.external: true` |
| `name: docker_ifg_prod` | ✅ sekcja `networks.ifg_prod.name` |
| `external: true` (network) | ✅ `networks.ifg_prod.external: true` |

### Fragment rendered config (istotne sekcje)

```yaml
name: ifg
# … services: api, worker, db …
    volumes:
      - type: volume
        source: postgres_data
        target: /var/lib/postgresql/data
networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
volumes:
  postgres_data:
    name: docker_postgres_data
    external: true
```

### Potwierdzenie: DB nadal wskazuje `docker_postgres_data`

- Logiczna nazwa w compose: `postgres_data` (alias w serwisie `db`).
- **Fizyczny wolumen Docker:** `docker_postgres_data` (`name` + `external: true`).
- Renderowany config **nie** zawiera `ifg_postgres_data` ani nowego wolumenu bez external pin.

---

## Testy / Guardian (tryb bezpieczny)

**Wykonano lokalnie — bez deployu, bez `compose up`, bez SSH/DS723+:**

| Test | Wynik |
|------|-------|
| `pytest tests/unit/test_guardian_preflight.py tests/unit/test_guardian_deploy_executors.py -p no:cov` | **22 passed** |
| PreflightEngine (`skip_remote=True`, `DRY_RUN`) | **SafetyGate: GO** |
| `volume.external` check | **PASS** — `external pin to docker_postgres_data` |

**Nie wykonano:** remote preflight, deploy run, compose build/up, mutacji na DS723+.

---

## Potwierdzenie: migracja NIE wykonana

| Akcja | Status |
|-------|--------|
| `docker compose up` na DS723+ | ❌ nie wykonano |
| Usunięcie kontenerów `docker-*` | ❌ nie wykonano |
| Usunięcie/przeniesienie wolumenów | ❌ nie wykonano |
| Rejestracja projektu w Container Manager UI | ❌ nie wykonano |
| Zmiany w `.env.production` na produkcji | ❌ nie wykonano |

Repozytorium jest **gotowe do commit/push** compose prep; **cutover produkcyjny** wymaga osobnego kroku operatora.

---

## GO / NO-GO — czy można przejść do backupu DS723+?

| Kryterium | Werdykt |
|-----------|---------|
| Compose prep w repo (`name: ifg`, external pins) | ✅ **GOTOWE** |
| Lokalna walidacja `docker compose config` | ✅ **PASS** |
| DB volume pin → `docker_postgres_data` | ✅ **POTWIERDZONE** |
| Sieć pin → `docker_ifg_prod` | ✅ **POTWIERDZONE** |
| Testy jednostkowe Guardian (safe) | ✅ **22/22** |
| Commit na `production` | ✅ przygotowany (tylko compose + raport) |
| Backup DS723+ przed cutover | ⏳ **NASTĘPNY KROK OPERATORA** |
| Remote preflight na DS723+ (volume exists, compose config) | ⏳ po `git pull` na DS723+ |
| Właściwy GO/NO-GO cutover | ⏳ po backupie + remote preflight + akceptacja operatora |

**Rekomendacja:** **TAK** — można przejść do **backupu bazy na DS723+** i przygotowania właściwego GO/NO-GO cutover (GWO-IFG-002A production migration), **pod warunkiem**:

1. `git pull` na DS723+ po merge/commit tej zmiany.
2. Backup: `pg_dump` z `docker-db-1` / wolumenu `docker_postgres_data` **przed** pierwszym `compose up` z nowym project name.
3. Stack nadal zatrzymany (Exited) — cutover w oknie maintenance.
4. Remote preflight (`volume.postgres`, `compose.validation` z `project=ifg`) — GO przed `up`.

**NO-GO cutover** jeśli backup nieudany, brak wolumenu `docker_postgres_data` na hoście, lub remote config nie pokazuje external pinów.

---

## Commit

```
git add docker/docker-compose.prod.yml docs/reports/GWO_IFG_002A_COMPOSE_PROJECT_PREP.md
git commit -m "..."
```

**Push:** celowo **nie wykonany** — w working tree pozostają niezwiązane zmiany; operator decyduje o pushu samego commita prep.
