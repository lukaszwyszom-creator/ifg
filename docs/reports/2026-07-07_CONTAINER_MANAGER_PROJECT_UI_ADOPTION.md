# Container Manager — adopcja projektu UI nad istniejącym stackiem `ifg` (CLI)

**Data:** 2026-07-07  
**GWO:** GWO-IFG-002A (kontekst po zamknięciu cutover)  
**Zakres:** analiza read-only — **bez zmian w systemie**, bez restartu, bez UI, bez automatyzacji

---

## Stan faktyczny

| Element | Wartość |
|---------|---------|
| Kontenery | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` — **Running** |
| Etykieta Compose | `com.docker.compose.project=ifg` |
| Plik compose | `/volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml` |
| `name:` w compose | `ifg` |
| Wolumen DB | `docker_postgres_data` (external) |
| Sieć | `docker_ifg_prod` (external) |
| Tunnel | `cloudflared-ifg` — poza projektem Compose (oczekiwane) |
| Aplikacja | działa (health 200, UI OK) |
| Container Manager → **Projekt** | **„Nie utworzono projektów”** |
| Container Manager → **Kontener** | `ifg-*` widoczne (typowo) |

**Istotna obserwacja:** cutover **techniczny się powiódł** (projekt Compose `ifg` w Dockerze), ale **rejestr projektów DSM** (zakładka Projekt) jest **pusty**. To dwa różne poziomy abstrakcji.

---

## 1. Czy Synology Container Manager potrafi zaadoptować istniejący compose stack uruchomiony z CLI?

# NIE — w sensie „adoptacji” istniejących kontenerów.

| Warstwa | Co widzi stack CLI | Co widzi CM → Projekt |
|---------|-------------------|------------------------|
| **Docker Engine** | Kontenery `ifg-*`, etykiety `com.docker.compose.*` | (pośrednio, przez API Docker) |
| **Compose CLI** | Projekt `ifg`, plik YAML na dysku | **nie rejestruje** wpisu w DSM |
| **DSM Project registry** | **brak wpisu** | lista projektów z CM (UUID, ścieżka, stan UI) |

Container Manager **nie ma** udokumentowanego mechanizmu „import existing running stack into Project without compose operation”. Projekty CM to **metadane DSM** + operacje delegowane do **docker-compose** (patrz [Synology Docker Project Worker](https://help.synology.com/developer-guide/resource_acquisition/docker-project.html), [GWO_IFG_002B](./GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md)).

`docker compose up` z CLI:
- tworzy/utrzymuje kontenery i etykiety,
- **nie** dodaje rekordu do `SYNO.Docker.Project`.

Wniosek z wcześniejszej analizy GWO-IFG-002B (nadal aktualny):

> CM **nie adoptuje** istniejących kontenerów — przy „Start” wykonuje `compose up`, który **tworzy lub rekonsyluje** kontenery według pliku YAML, a nie „przepina” ownership w UI.

W obecnym stanie IFG kontenery **już mają** `project=ifg`. Brak wpisu w UI oznacza **lukę rejestracyjną DSM**, nie błąd runtime.

---

## 2. Czy trzeba utworzyć projekt z UI wskazując ten sam `docker-compose.prod.yml`?

# TAK — jeśli celem jest widoczność w zakładce **Projekt**.

Aby CM pokazał projekt `ifg` w UI, operator musi **jawnie zarejestrować** projekt w DSM:

| Metoda | Rejestruje w CM? | Uwagi |
|--------|------------------|-------|
| CLI `docker compose up` | **NIE** (stan obecny) | Źródło prawdy runtime |
| CM → Project → **Create** | **TAK** | Wskazać katalog + plik compose |
| `SYNO.Docker.Project` API (`synowebapi method=list`) | **TAK** | Poza zakresem tego raportu (bez automatyzacji) |

### Pułapka ścieżki pliku (IFG)

IFG używa **nietypowej nazwy pliku**: `docker-compose.prod.yml`, nie domyślnego `docker-compose.yml`.

Etykiety na kontenerach wskazują:

```
com.docker.compose.project.working_dir = .../ifg_standalone/docker
com.docker.compose.project.config_files = .../docker/docker-compose.prod.yml
```

Przy Create Project w CM:

- katalog projektu powinien odpowiadać **`docker/`** (zgodnie z `working_dir`), **nie** root repo,
- operator musi **wybrać** `docker-compose.prod.yml` (lub mieć symlink `docker-compose.yml` → prod — osobna decyzja ops, **nie** wykonywana w tym raporcie).

Nazwa projektu w wizardzie (`ifg`) powinna być **zgodna** z `name: ifg` w YAML — inaczej CM może utworzyć projekt o innej nazwie i próbować kontenerów `inna_nazwa-api-1`.

---

## 3. Czy utworzenie projektu UI nad istniejącymi kontenerami `ifg-*` jest bezpieczne?

# ZALEŻY od kroku — domyślnie: NIE bez okna maintenance.

| Wariant Create | Ryzyko dla produkcji | Komentarz |
|----------------|---------------------|-----------|
| **Create, Start ODZNACZONY** | **Niskie** | Rejestracja metadanych; brak natychmiastowego `compose up` |
| **Create + Start** | **Średnie** | Wywołuje `compose up` — zwykle idempotentny przy zgodnej konfiguracji, ale **nie gwarantowany** brak recreate |
| **Create + Build / Rebuild** | **WYSOKIE** | Synology worker domyślnie `force_recreate: true` — **restart/recreate** kontenerów |
| **Stop / Down z UI po rejestracji** | **KRYTYCZNE** | Dual control: UI może pokazywać „Stopped”, podczas gdy CLI utrzymuje Running — operator może przypadkowo zatrzymać prod |

### Co jest bezpieczne w obecnym stanie

- Kontenery **już** należą do projektu Compose `ifg`.
- Wolumen i sieć są **external** — rejestracja UI **nie zmienia** fizycznych zasobów sama z siebie.
- **Niebezpieczne** jest kliknięcie **Start / Build / Stop** w CM bez świadomości, że stack już działa pod CLI.

---

## 4. Czy grozi recreate / restart / konflikt nazw?

### Konflikt nazw kontenerów

| Scenariusz | Ryzyko |
|------------|--------|
| `compose up` gdy `ifg-api-1` **już istnieje** z tą samą specyfikacją | Compose **nie tworzy duplikatu** — rekonsyluje stan (brak nowego kontenera) |
| `compose up` gdy specyfikacja **się różni** | **Recreate** pojedynczego serwisu (krótki downtime API/worker) |
| CM **Build** z `force_recreate` | **Recreate wszystkich** serwisów projektu |
| Próba drugiego stacku z tym samym `container_name` | Błąd „name already in use” — **blokada**, nie duplikat |

Przy poprawnym compose i działających `ifg-*` **nie powstanie** drugi zestaw `ifg-api-1` równolegle — Docker zablokuje kolizję nazw.

### Konflikt portu `127.0.0.1:8000`

Tylko gdy CM/compose próbuje **uruchomić drugi** API na tym samym porcie. Przy istniejącym `ifg-api-1` — port zajęty; nowy kontener nie wystartuje (błąd bind), **bez** podwójnego API.

### Podwójna baza (krytyczne)

| Warunek | Skutek |
|---------|--------|
| Dwa kontenery DB na **`docker_postgres_data`** jednocześnie | **Korupcja PostgreSQL** |
| Prawidłowy `compose up` z jednym serwisem `db` | **Jeden** `ifg-db-1` — ryzyko niskie przy braku duplikatu |

### Restart produkcji

| Akcja CM | Prawdopodobieństwo restartu |
|----------|----------------------------|
| Create bez Start | **Brak** |
| Start (compose up, config bez zmian) | **Niskie** — kontenery zostają Running |
| Start po zmianie compose/env | **Średnie** — selektywny recreate |
| Build | **Wysokie** — traktować jak maintenance |

---

## 5. Najbezpieczniejsza procedura, jeśli chcemy widzieć projekt w UI

### Faza 0 — tylko read-only (obowiązkowa)

```bash
# Etykiety projektu
sudo docker inspect ifg-api-1 --format '{{index .Config.Labels "com.docker.compose.project"}}'
sudo docker inspect ifg-api-1 --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
sudo docker inspect ifg-api-1 --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'

# Stan compose (bez mutacji)
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config > /dev/null

# Backup punktu kontrolnego (jeśli brak świeżego)
# ls -la /volume1/docker/ifg_v2/backups/
```

### Faza 1 — rejestracja UI (najniższe ryzyko, **okno maintenance zalecane**)

1. Zaplanować okno (nawet jeśli krótkie) + osoba na monitoringu health/UI.
2. CM → **Project** → **Create**.
3. Nazwa: **`ifg`** (zgodna z `name:` w YAML).
4. Ścieżka: **`/volume1/docker/ifg_v2/ifg_standalone/docker`**.
5. Plik: **`docker-compose.prod.yml`** (lub symlink — poza tym raportem).
6. **ODZNACZYĆ** „Start the project once it is created” / „Uruchom po utworzeniu”.
7. **Done** — tylko rejestracja.
8. **Nie klikać** Build / Rebuild.
9. Zweryfikować zakładkę Projekt i **nie** używać Stop, dopóki nie ustalono modelu dual-control.

### Faza 2 — synchronizacja stanu UI (opcjonalna, **tylko w oknie maintenance**)

Jeśli po Fazie 1 UI pokazuje projekt jako **Stopped**, mimo że kontenery Running:

1. Potwierdzić identyczność pliku compose z tym, który utworzył kontenery (`git status`, `HEAD`).
2. Wykonać **najpierw** suchy test CLI (bez CM):
   ```bash
   sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
   ```
   Oczekiwane: `Running` / `unchanged` — **bez recreate** przy zgodnej konfiguracji.
3. Dopiero potem rozważyć **Start** w CM — traktować jak ten sam `compose up`.
4. Monitorować: `curl -fsS http://127.0.0.1:8000/health`, logi API, UI.

### Faza 3 — czego NIE robić na produkcji bez planu

| Akcja | Dlaczego |
|-------|----------|
| **Build** w CM | `force_recreate` — restart stacku |
| **Stop** projektu w CM przy dual control | Zatrzymanie produkcji |
| **down -v** | Kasowanie wolumenów |
| Tworzenie **drugiego** projektu na ten sam compose | Chaos operacyjny |
| Zmiana `name:` / ścieżki bez testu | Nowe kontenery / nowe wolumeny |

### Alternatywa bez UI (najbezpieczniejsza operacyjnie)

Kontynuować zarządzanie przez **CLI + Guardian (Mac mini → SSH)** — patrz runbook i Execution Guard. Zakładka **Kontener** w CM nadal pokazuje `ifg-*`.

---

## 6. Czy można zostawić obecny stan jako poprawny technicznie, mimo braku projektu w UI?

# TAK.

| Kryterium | Stan |
|-----------|------|
| Projekt Compose w Dockerze | **`ifg`** ✅ |
| Kontenery produkcyjne | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` ✅ |
| Dane DB | `docker_postgres_data` zachowany ✅ |
| Health / UI | działają ✅ |
| Guardian deploy / cutover (SSH) | kompatybilne ✅ |
| Wpis w CM → Projekt | **brak** — luka **kosmetyczno-operacyjna**, nie runtime |

**Źródło prawdy** dla IFG po cutover to:

```
docker compose -f docker/docker-compose.prod.yml --env-file .env.production
```

w katalogu repo na DS723+, sterowane z Mac mini (Guardian) lub ręcznie SSH.

Zakładka **Projekt** w CM to warstwa **zarządzania DSM** (wygoda, Web Station, przyciski Start/Stop). Jej brak **nie oznacza**, że stack jest „niepoprawny” ani „niezmigrowany”.

---

## 7. Rekomendacja

# LEAVE_AS_CLI_COMPOSE

| Opcja | Werdykt | Uzasadnienie |
|-------|---------|--------------|
| **ADOPT_NOW** | ❌ Nie | Rejestracja UI (nawet bez Start) wprowadza **dual control**; pełna widoczność Running w UI często wymaga Start/Build → ryzyko restartu |
| **LEAVE_AS_CLI_COMPOSE** | ✅ **TAK** | Produkcja działa; cutover zakończony; Guardian i CLI są sprawdzonym modelem; zero ryzyka przy braku zmian |
| **NEED_MAINTENANCE_WINDOW** | ⚠️ Tylko jeśli UI jest wymagane | Gdy zespół **musi** mieć Projekt w CM (operacje bez SSH) — procedura Faza 0→2 w oknie, bez Build |

### Podsumowanie decyzyjne

```
Stan obecny:     TECHNICZNIE POPRAWNY (CLI Compose project ifg)
Brak w UI:       Oczekiwalna luka rejestru DSM po cutover CLI
Działanie teraz: ZOSTAW — nie tworzyć projektu UI na gorącej produkcji
Działanie później: NEED_MAINTENANCE_WINDOW — Create bez Start → weryfikacja → ewentualny Start
Unikać:          Build / Stop w CM bez procedury
```

---

## Powiązane dokumenty

| Dokument | Rola |
|----------|------|
| [GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md](./GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md) | Adopt vs recreate — analiza podstawowa |
| [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md) | Architektura migracji `docker` → `ifg` |
| [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md) | Krok 10 — UI check (oczekiwany po cutover) |
| [2026-07-07_GWO_IFG_002A_CONTAINER_CUTOVER_CLOSED.md](./2026-07-07_GWO_IFG_002A_CONTAINER_CUTOVER_CLOSED.md) | Zamknięcie GWO — stan po migracji |
| [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md](../guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md) | `SYNO.Docker.Project` vs CLI compose |

---

*Raport analityczny. Bez zmian w systemie, restartu kontenerów i automatyzacji UI.*
