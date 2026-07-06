# GWO-IFG-002B — Zachowanie Synology Container Manager przy tworzeniu Project z istniejącego compose

**Data:** 2026-07-06  
**Zakres:** wyłącznie analiza zachowania **Container Manager** (DSM 7.2+ / 7.3) — **bez kodu, bez deployu, bez migracji**  
**Kontekst IFG:** compose prep (`name: ifg`, external `docker_postgres_data`, external `docker_ifg_prod`) — commit `9505adc`  
**Powiązane:** [GWO_IFG_002A_COMPOSE_PROJECT_PREP.md](./GWO_IFG_002A_COMPOSE_PROJECT_PREP.md), [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md)

---

## 1. Pytanie badawcze

Jak zachowuje się **Container Manager → Project → Create** dla istniejącego stacku IFG (kontenery `docker-*-1`, wolumen `docker_postgres_data`, sieć `docker_ifg_prod`), gdy w compose jest już:

```yaml
name: ifg
volumes:
  postgres_data:
    name: docker_postgres_data
    external: true
networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

---

## 2. Źródła

| Źródło | Co potwierdza |
|--------|----------------|
| [Synology Developer Guide — Docker Project Worker](https://help.synology.com/developer-guide/resource_acquisition/docker-project.html) | Container Manager Projects są **powered by docker-compose**; worker robi create/update + build; domyślnie `force_recreate: true` |
| [Synology Knowledge Center — Project](https://kb.synology.com/en-global/DSM/help/ContainerManager/docker_project?version=7) | Oficjalna strona CM Project (treść UI; brak szczegółowego opisu „adopt vs recreate”) |
| [SynoForum — migrating containers with compose.yaml](https://www.synoforum.com/threads/container-manager-migrating-redoing-containers-with-compose-yaml.15218/) | Migracja = **stop + compose + Create Project**; brak adoptacji; dane w volume bind/named volume zostają |
| [SynoForum — Docker to Container Manager migration](https://www.synoforum.com/threads/docker-to-container-manager-migration.15444/) | CM = UI nad Docker engine; zmiany przez **duplicate/rebuild** compose, nie edycja kontenera |
| [Twingate / HabitTrove / Dawarich install guides](https://www.twingate.com/docs/how-to-set-up-twingate-on-a-synology-nas-dsm-7) | Wizard Create → opcja **„Start the project once it is created”** = natychmiastowy deploy (= compose up) |
| [Docker Compose issue #11151](https://github.com/docker/compose/issues/11151) | Przy recreate: konflikt nazw kontenera jeśli stary kontener **nie został usunięty** |
| Diagnoza IFG DS723+ (2026-07-05) | Stack `docker-*` **Exited**; wolumen `docker_postgres_data` istnieje |

**Uwaga metodologiczna:** Synology **nie publikuje** oficjalnego opisu „adopt existing containers into Project”. Wnioski opierają się na mechanice **Docker Compose** (którą CM wywołuje) oraz spójnych raportach użytkowników DSM 7.2/7.3.

---

## 3. Jak działa Container Manager → Project → Create

### 3.1 Co robi wizard (UI)

Typowy przebieg (DSM 7.2 / 7.3):

1. **Container Manager → Project → Create**
2. Operator podaje **nazwę projektu** (np. `ifg`) i **ścieżkę katalogu** (np. repo IFG lub podkatalog `docker/`)
3. DSM wykrywa istniejący plik compose (`docker-compose.yml`, `compose.yaml`) lub operator **uploaduje / wkleja** YAML
4. Kolejne kroki: Web Station (opcjonalnie), podsumowanie
5. Checkbox: **„Start the project once it is created”** (domyślnie często zaznaczony w tutorialach)
6. **Done** → CM rejestruje projekt w swojej warstwie UI i — jeśli Start zaznaczony — uruchamia deploy

### 3.2 Co dzieje się pod spodem

Container Manager **nie ma własnego silnika orchestracji**. Oficjalnie:

> *Docker Project Worker is provided by ContainerManager **powered by docker-compose***

Operacje UI mapują się na standardowe polecenia Compose:

| Akcja CM | Odpowiednik operacyjny |
|----------|------------------------|
| Create + Start | `docker compose up` (pull/build według potrzeb) |
| Start | `docker compose up` |
| Stop | `docker compose stop` / `down` (zależnie od wersji CM) |
| Build | `docker compose build` + recreate (worker domyślnie `force_recreate: true`) |
| Edit compose + rebuild | `compose up` z recreate |

**Create bez Start** rejestruje projekt i plik compose w CM — **nie tworzy kontenerów** do momentu Start/Build.

### 3.3 Czy CM „widzi” istniejące kontenery CLI?

**Nie adoptuje ich automatycznie.** Kontener należy do projektu Compose przez etykiety:

- `com.docker.compose.project` (np. `docker` vs `ifg`)
- `com.docker.compose.service` (np. `api`, `db`)

Kontenery `docker-api-1` mają `project=docker`. Nowy projekt `ifg` tworzy **nowe** kontenery `ifg-api-1` z `project=ifg`. Docker Compose **nie przepina** istniejących kontenerów na inny project name.

---

## 4. Odpowiedź na pytanie A / B / C

### Werdykt jednoznaczny

**Scenariusz prawdziwy: B — Recreate containers using existing volumes**

(z doprecyzowaniem mechanizmu jako wariant **C** poniżej)

| Scenariusz | Prawda dla IFG? | Wyjaśnienie |
|------------|-----------------|-------------|
| **A. Adopt existing containers** | **NIE** | Brak mechanizmu adoptacji w CM ani w Compose przy zmianie `com.docker.compose.project` z `docker` → `ifg` |
| **B. Recreate containers using existing volumes** | **TAK** | Start/Build uruchamia `compose up`, który **tworzy nowe** kontenery `ifg-*-1`, montując **istniejące** zasoby dzięki `external: true` |
| **C. Inny mechanizm** | **Częściowo (opakowanie UI)** | CM najpierw **rejestruje metadane projektu** (ścieżka, nazwa, plik YAML), potem deleguje recreate do Compose — to nie jest osobny „trzeci silnik”, ale **UI + metadata + compose up** |

**Jednoznaczna odpowiedź dla operatora:** wybierz **B**.

---

## 5. Zachowanie przy `name: ifg` + external pins (IFG)

### 5.1 Wolumen `docker_postgres_data`

| Oczekiwanie | Wynik |
|-------------|-------|
| Zachowa istniejący wolumen | **TAK** — `external: true` + `name: docker_postgres_data` wymusza użycie istniejącego wolumenu |
| Utworzyć pusty `ifg_postgres_data` | **NIE** (przy poprawnym compose prep) |
| Utrata danych przy samym Create | **NIE** — Create bez Start nie dotyka wolumenów |

Nowy kontener `ifg-db-1` dostanie **ten sam** mountpoint co wcześniejszy `docker-db-1`:  
`/volume1/@docker/volumes/docker_postgres_data/_data`.

### 5.2 Sieć `docker_ifg_prod`

| Oczekiwanie | Wynik |
|-------------|-------|
| Zachowa istniejącą sieć | **TAK** — external pin |
| Utworzyć nową `ifg_ifg_prod` | **NIE** (przy pinie w compose) |

### 5.3 Kontenery

| Oczekiwanie | Wynik |
|-------------|-------|
| Utworzyć nowe kontenery | **TAK** — `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` |
| Przejąć stare `docker-*-1` | **NIE** — stare pozostają jako **Exited** (orphans) aż do `docker rm` |
| Konflikt nazw kontenerów | **NIE** przy zatrzymanym starym stacku (różne prefiksy: `docker-` vs `ifg-`) |
| Konflikt portu `127.0.0.1:8000` | **TAK, jeśli** stary `docker-api-1` nadal **Running** podczas Start projektu `ifg` |

### 5.4 Podwójny stack / podwójna baza

| Ryzyko | Warunek |
|--------|---------|
| Dwa działające stacki | Operator uruchomi **równolegle** stary projekt `docker` i nowy `ifg` |
| **Korupcja PostgreSQL** | **Dwa kontenery DB jednocześnie** montujące **ten sam** wolumen `docker_postgres_data` — **krytyczne** |
| Pusta baza „iluzja sukcesu” | Brak external pin → nowy wolumen `ifg_postgres_data` — **wyeliminowane** w compose prep |

---

## 6. Ryzyka (macierz)

| # | Ryzyko | Prawdopodobieństwo | Skutek | Mitygacja |
|---|--------|-------------------|--------|-----------|
| R1 | Pusta baza (`ifg_postgres_data`) | Niskie po prep | Krytyczny | Gate: `compose config \| grep docker_postgres_data`; external pin |
| R2 | Utrata danych | Bardzo niskie przy B + pin | Krytyczny | Backup `pg_dump` przed Start; zakaz `down -v` |
| R3 | Konflikt nazw kontenerów | Niskie (stack Exited) | Blokada Start | Stare `docker-*` **Exited** wystarczą — **nie** `docker rm` przed Start (rollback); konflikt tylko gdy Running |
| R4 | Konflikt portu 8000 | Średnie jeśli stary API Running | Blokada Start | Upewnić się: `docker-api-1` **nie Running** |
| R5 | Podwójny stack / dual DB | Niskie przy dyscyplinie | **Korupcja PG** | Tylko jeden projekt aktywny; jeden kontener DB na wolumen |
| R6 | Orphan kontenery `docker-*` | **Pewne** po cutover | Niski (bałagan UI) | `docker rm docker-*` **dopiero po pełnej walidacji** (health + Guardian + test funkcjonalny); do tego czasu = **rollback asset** |
| R7 | CM nie znajdzie pliku compose | Średnie dla IFG | Blokada UI | Plik to `docker/docker-compose.prod.yml`, nie domyślne `docker-compose.yml` — patrz cutover |
| R8 | CM Start = nieoczekiwany recreate | Średnie | Średni | Create z **odznaczonym** Start; weryfikacja; potem kontrolowany Start |

---

## 7. Specyfika IFG — plik compose a wizard CM

IFG używa **nietypowej nazwy pliku**:

```
/volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml
```

Container Manager domyślnie szuka `docker-compose.yml` / `compose.yaml` **w wskazanym katalogu**. Przy Create Project operator musi:

- wskazać katalog `docker/` **i** wybrać istniejący plik, **albo**
- utworzyć symlink `docker-compose.yml` → `docker-compose.prod.yml` (osobna decyzja ops), **albo**
- wykonać cutover **CLI** z repo root (Guardian/runbook) — CM **wyświetli** projekt po `compose up` jeśli wykryje stack (zachowanie UI bywa wersjo-zależne; CLI jest źródłem prawdy).

Pole `name: ifg` w pliku **nadpisuje** domyślną nazwę projektu z katalogu `docker/` — po Start projekt w Dockerze to **`ifg`**, nie `docker`.

---

## 8. Czy można przejść do backupu DS723+ i GO/NO-GO?

**TAK** — analiza zachowania CM **nie blokuje** następnego kroku, pod warunkiem:

1. Cutover plan zakłada **recreate (B)**, nie adopt (A).
2. Przed Start: backup DB + gate `compose config`.
3. Stary stack **zatrzymany** (Exited); kontenery `docker-*` **zachowane** do pełnej walidacji — służą rollbackowi.
4. Operator świadomy: **Create + Start = compose up = nowe kontenery**, dane z external volume.

---

## 9. Potwierdzenia obowiązkowe

| Stwierdzenie | Status |
|--------------|--------|
| Migracja w ramach tego GWO **nie wykonana** | ✅ |
| Deploy / compose up **nie wykonany** | ✅ |
| Kod **nie zmieniany** | ✅ |
| CM adoptuje istniejące kontenery | ❌ **NIE** |
| CM/Compose tworzy nowe kontenery z istniejącymi wolumenami (external) | ✅ **TAK** |
| `docker_postgres_data` zachowany przy poprawnym compose | ✅ **TAK** |

---

## RECOMMENDED CUTOVER:

**Autorytatywny runbook:** [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md)

1. **Backup (GO gate)** — na DS723+ przed cutover. Jeśli stack Exited, tymczasowo podnieś **tylko db** starym projektem albo użyj wcześniejszego backupu + `volume inspect`. **Backup musi być GO przed dalszymi krokami.**

2. **`git pull`** na DS723+ — compose prep (`name: ifg`, external pins) z brancha `production`.

3. **Gate compose config (obowiązkowy):**
   ```bash
   cd /volume1/docker/ifg_v2/ifg_standalone
   sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config \
     | grep -E '^name:|docker_postgres_data|docker_ifg_prod|external'
   ```
   Wymagane: `name: ifg`, `docker_postgres_data`, `docker_ifg_prod`, `external: true`.  
   **NO-GO** jeśli pojawi się `ifg_postgres_data` bez external.

4. **Preflight:** potwierdź, że `docker-api-1`, `docker-worker-1`, `docker-db-1` są **Exited** (nie Running). **Nie usuwaj** ich — to **rollback asset**.

5. **Start projektu `ifg`** (CLI — preferowane):
   ```bash
   cd /volume1/docker/ifg_v2/ifg_standalone
   sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
   ```
   **Alternatywa UI:** Container Manager → Project → Create/Start (patrz runbook).

6. **Health** — `compose ps`, `curl http://127.0.0.1:8000/health`, `pg_isready`, sanity SQL.

7. **Guardian verify** — z Mac mini (read-only): `python3 scripts/guardian.py deploy check`.

8. **Test funkcjonalny IFG** — logowanie UI, lista faktur, KSeF (patrz runbook).

9. **Sprzątanie — dopiero po pełnej walidacji (kroki 6–8 OK):**
   ```bash
   sudo docker rm docker-api-1 docker-worker-1 docker-db-1
   ```
   **Nigdy wcześniej.** **Nie** `-v`. **Nie** `docker volume rm`.

10. **GO/NO-GO:** GO jeśli wszystkie kroki 6–8 OK. NO-GO → rollback (stop `ifg`, start stary projekt `docker` z zachowanych kontenerów / `-p docker`) — patrz runbook § Rollback.

---

*Analiza dokumentacyjna — zaktualizowano 2026-07-06 (runbook: zachowanie `docker-*` do pełnej walidacji).*
