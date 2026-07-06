# IFG — migracja do Synology Container Manager → Projekt

**Data:** 2026-07-05  
**Środowisko:** DS723+ (produkcja), Mac mini (dev / Guardian)  
**Repo prod:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Branch / commit (DS723+):** `production` @ `a405646`  
**Status:** raport techniczny — **migracja nie wykonana** (oczekuje akceptacji operatora)

**Runbook produkcyjny (APPROVED):** [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md)

Powiązany dokument: [IFG_DS723_CONTAINER_MANAGER_PROJECT.md](./IFG_DS723_CONTAINER_MANAGER_PROJECT.md)

---

## Streszczenie wykonawcze

| Aspekt | Werdykt |
|--------|---------|
| Obecny projekt Compose | **`docker`** (nie `ifg`) |
| Dane PostgreSQL | wolumen **`docker_postgres_data`** — **bezpieczny, nie ruszać** |
| Stack aplikacji | **zatrzymany** (Exited) — dobry moment na migrację nazwy |
| Rekomendacja | **`name: ifg` + `external: true` na wolumenie DB** (i opcjonalnie sieci) |
| Wariant odrzucony | Samo `-p ifg` lub samo `name: ifg` **bez pinu wolumenu** → **pusta baza** |
| Guardian | po migracji: `compose -f docker/docker-compose.prod.yml` z repo root; zaktualizować docs/skrypty |

---

## 1. Obecny stan

### 1.1 Struktura repozytorium

```
/volume1/docker/ifg_v2/ifg_standalone/     ← katalog roboczy prod (git root)
├── .env.production                        ← sekrety i env prod (env_file compose)
├── docker/
│   └── docker-compose.prod.yml            ← plik compose prod
├── frontend-react/dist/                   ← bind mount → API (frontend statyczny)
├── app/                                   ← backend Python
└── scripts/guardian2.py                   ← deploy prod (SSH → DS723+)
```

**Uruchomienie compose (Guardian / runbook):** z **katalogu głównego repo**, nie z `docker/`:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production …
```

W `ifg_guardian/config.py`: `COMPOSE_FILE = "docker/docker-compose.prod.yml"`.

### 1.2 Zawartość `docker/docker-compose.prod.yml` (skrót)

| Usługa | Rola | Porty / mounty |
|--------|------|----------------|
| **api** | FastAPI + serwowanie `frontend-react/dist` | `127.0.0.1:8000:8000`, bind: `.env.production`, `frontend-react/dist` |
| **worker** | `python -m app.worker` | bind: `.env.production` |
| **db** | PostgreSQL 17 | wolumen `postgres_data` → `/var/lib/postgresql/data` |

Sieć logiczna: `ifg_prod` (bridge).  
**Brak** top-level `name:` w pliku.  
**Brak** `COMPOSE_PROJECT_NAME` w `.env.production`.

### 1.3 Nazwa projektu Compose

Docker Compose v2 ustala domyślną nazwę projektu z **katalogu pliku compose** → katalog `docker/` → projekt **`docker`**.

Weryfikacja (DS723+, 2026-07-05):

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config | grep '^name:'
# name: docker
```

### 1.4 Kontenery, sieci, wolumeny

#### Kontenery IFG (compose)

| Kontener | Status | Obraz | `com.docker.compose.project` |
|----------|--------|-------|------------------------------|
| `docker-api-1` | Exited (137) | `ifg-api:latest` | `docker` |
| `docker-worker-1` | Exited (137) | `ifg-api:latest` | `docker` |
| `docker-db-1` | Exited (0) | `postgres:17` | `docker` |

#### Poza stackiem IFG (compose)

| Kontener | Status | Uwagi |
|----------|--------|-------|
| `cloudflared-ifg` | Up | tunel — **nie** w `docker-compose.prod.yml` |
| `syncthing-1` | Up | osobny projekt `syncthing` |

#### Sieci

| Nazwa Docker | Użycie |
|--------------|--------|
| `docker_ifg_prod` | sieć stacku IFG |

#### Wolumeny (istotne)

| Nazwa Docker | Utworzony | Powiązanie |
|--------------|-----------|------------|
| **`docker_postgres_data`** | 2026-05-04 | **produkcyjna baza PostgreSQL** |
| `docker_ksef_keys` | 2026-04-16 | legacy — **nie** w obecnym compose prod |

### 1.5 Etykiety Compose na `docker-db-1`

```json
{
  "com.docker.compose.project": "docker",
  "com.docker.compose.project.config_files": "/volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml",
  "com.docker.compose.project.working_dir": "/volume1/docker/ifg_v2/ifg_standalone/docker",
  "com.docker.compose.service": "db",
  "com.docker.compose.version": "2.20.1"
}
```

Wniosek: historycznie compose był uruchamiany w kontekście katalogu `docker/` (working_dir), co utrwaliło projekt **`docker`**.

### 1.6 Fizyczna lokalizacja danych PostgreSQL

| Typ | Wartość |
|-----|---------|
| Typ mountu DB | **named volume** (nie bind mount hosta) |
| Nazwa wolumenu | `docker_postgres_data` |
| Mountpoint Docker | `/volume1/@docker/volumes/docker_postgres_data/_data` |
| W kontenerze | `/var/lib/postgresql/data` |

API/worker używają **bind mountów** plików repo (`.env.production`, `frontend-react/dist`) — te ścieżki **nie zależą** od nazwy projektu Compose.

### 1.7 Synology Container Manager — obserwacja UI

- **Projekt → brak „IFG”** — oczekiwane: projekt nazywa się **`docker`**, nie `ifg`.
- **Kontener → luźne `docker-*-1`** — kontenery mają prefiks projektu `docker`; po migracji docelowo: `ifg-api-1`, `ifg-worker-1`, `ifg-db-1`.
- Frontend **nie** jest osobnym kontenerem — jest montowany w **api** (Container Manager pokaże go jako część usługi `api` w projekcie).

---

## 2. Odpowiedzi na pytania techniczne (1–10)

### (3) `name:` vs `COMPOSE_PROJECT_NAME`

| Mechanizm | Stan |
|-----------|------|
| `name:` w `docker-compose.prod.yml` | **brak** |
| `COMPOSE_PROJECT_NAME` w `.env.production` | **brak** |
| Efektywna nazwa projektu | **`docker`** (domyślnie z katalogu compose) |

### (7) Czy projekt DSM może powstać z istniejącego compose **bez zmiany wolumenu DB**?

**Tak**, pod warunkiem:

1. W compose ustawić **`name: ifg`** (widoczność w Container Manager → Projekt).
2. **Przypiąć** istniejący wolumen:

   ```yaml
   volumes:
     postgres_data:
       name: docker_postgres_data
       external: true
   ```

3. **Nie** uruchamiać `down -v` ani tworzyć nowego projektu z domyślnym wolumenem.

Synology Container Manager grupuje stacki według projektu Compose — po poprawnej konfiguracji i `up -d` pojawi się projekt **`ifg`** z usługami `api`, `worker`, `db`.

### (8) Czy samo `name: ifg` zmieni nazwy i stworzy **nowe** wolumeny?

**Tak — bez pinu wolumenu to katastrofa operacyjna.**

Symulacja (`-p ifg`, bez `external`):

```bash
sudo docker compose -p ifg -f docker/docker-compose.prod.yml --env-file .env.production config | grep name:
# name: ifg
#     name: ifg_ifg_prod
#     name: ifg_postgres_data    ← NOWY PUSTY WOLUMEN
```

| Zasób | Projekt `docker` (dziś) | Projekt `ifg` (bez pinu) |
|-------|-------------------------|---------------------------|
| Wolumen DB | `docker_postgres_data` | **`ifg_postgres_data` (pusty)** |
| Sieć | `docker_ifg_prod` | `ifg_ifg_prod` |
| Kontenery | `docker-*-1` | `ifg-*-1` |

### (9) Czy trzeba `external: true` dla wolumenu DB?

**Tak — obowiązkowo** przy zmianie nazwy projektu z `docker` na `ifg`.

`external: true` + `name: docker_postgres_data` mówi Compose: **użyj istniejącego wolumenu**, nie twórz `ifg_postgres_data`.

Sieć — **zalecane** pinowanie `docker_ifg_prod` (spójność), ale przy cold start można też utworzyć nową sieć `ifg_ifg_prod` — **nie wpływa na dane DB**. Pin sieci upraszcza rollback i brak duplikatów.

### (10) Guardian — deploy w modelu Container Manager Project

Obecny model (`scripts/guardian2.py`, `ifg_guardian`):

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml build api
sudo docker compose -f docker/docker-compose.prod.yml up -d --no-deps --force-recreate api worker
```

Po migracji (z `name: ifg` w pliku compose):

| Element | Zmiana |
|---------|--------|
| Flaga `-p ifg` | **niepotrzebna** — nazwa z pola `name:` |
| Flaga `-p docker` | **zakazana** — tworzyłaby równoległy stack / inne wolumeny |
| `COMPOSE_FILE` | bez zmiany ścieżki: `docker/docker-compose.prod.yml` |
| Working directory | **zawsze repo root** na DS723+ |
| Weryfikacja deploy | `docker compose ps` → projekt **ifg**, serwisy `api` `worker` `db` |
| Post-check | `curl http://127.0.0.1:8000/health` **w kontenerze** (nie Python 3.8 na hoście NAS) |

Proponowana aktualizacja Guardian (osobne GWO po migracji):

1. W `ifg_guardian/config.py` — stała `COMPOSE_PROJECT_NAME = "ifg"` tylko jako dokumentacja (opcjonalnie).
2. W deploy pipeline — krok **`compose config | grep docker_postgres_data`** przed `up`.
3. W runbook — zakaz `docker compose down -v` i `-p docker`.

---

## 3. Największe ryzyka

| # | Ryzyko | Poważność | Mitygacja |
|---|--------|-----------|-----------|
| R1 | Utworzenie `ifg_postgres_data` (pusta baza) | **Krytyczne** | `external: true` + `name: docker_postgres_data`; weryfikacja `compose config` |
| R2 | `docker compose down -v` | **Krytyczne** | zakaz; checklist operatora |
| R3 | Równoległy stack (`-p ifg` + stary `docker` Running) | Wysokie | tylko `ifg-*` Running; `docker-*` Exited; po **pełnej walidacji** → `docker rm docker-*` |
| R4 | Uruchomienie `up` bez `--env-file .env.production` | Średnie | zawsze pełna komenda z runbooka |
| R5 | Guardian / skrypt woła compose z `-p docker` | Średnie | ujednolicić po merge `name: ifg` |
| R6 | `cloudflared-ifg` pozostaje poza projektem | Niskie | świadomie osobno; opcjonalny osobny compose później |
| R7 | Utrata bind mount frontendu | Niskie | ścieżki względne `../frontend-react/dist` — bez zmian |

---

## 4. Wariant rekomendowany

### Wariant A — **`name: ifg` + external volume (i sieć)**

**Opis:** Jedna zmiana w repo; na DS723+ `git pull`, weryfikacja config, `up -d`. Produkcyjne dane zostają w `docker_postgres_data`.

**Diff compose (propozycja):**

```yaml
name: ifg

services:
  # api, worker, db — bez zmian merytorycznych
  …

volumes:
  postgres_data:
    name: docker_postgres_data
    external: true

networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

**Efekt w Container Manager:**

- Projekt: **`ifg`**
- Kontenery: `ifg-api-1`, `ifg-worker-1`, `ifg-db-1`
- Wolumen DB: nadal **`docker_postgres_data`** (nazwa fizyczna bez zmian — to OK)

**Dlaczego teraz:** stack **zatrzymany** — brak ruchu na API; minimalny downtime przy `up -d`.

---

## 5. Warianty odrzucone

| Wariant | Opis | Dlaczego odrzucony |
|---------|------|---------------------|
| **B** | Tylko `-p ifg` / tylko `name: ifg` bez pinu wolumenu | Tworzy **`ifg_postgres_data`** — pusta baza, iluzja sukcesu |
| **C** | `docker volume rename` na `ifg_postgres_data` | Zmiana nazwy wolumenu + zmiana projektu = zbędne ryzyko; lepszy pin `external` |
| **D** | Równoległy stack `ifg` obok działającego `docker` | Dwa stacki, dwa wolumeny; chaos i 429/sync — **zakaz bez akceptacji** |
| **E** | Tylko UI DSM „Utwórz projekt” bez edycji compose | DSM i tak użyje domyślnego nazewnictwa wolumenów przy nowej nazwie projektu — bez pinu to R1 |
| **F** | `docker compose down -v` + świeży start | **Kasuje dane** — sprzeczne z wymaganiami |
| **G** | Zostawić projekt `docker` i tylko zmienić wyświetlaną nazwę | Container Manager nie ma sensownego aliasu; nadal mylące operacyjnie |

---

## 6. Plan migracji krok po kroku

### Faza 0 — przygotowanie (Mac mini / git)

1. Zatwierdzić diff compose (Wariant A).
2. Zaktualizować komentarz nagłówka w `docker-compose.prod.yml` (komenda uruchomienia).
3. Merge / push na `production`.
4. **Nie** wykonywać `up` na DS723+ przed Fazą 1.

### Faza 1 — diagnostyka przed (DS723+) — **bezpieczne, read-only**

Patrz sekcja 7.

### Faza 2 — wdrożenie pliku compose (DS723+)

1. `git pull origin production`
2. `compose config` — **gate** (musi wskazywać `docker_postgres_data`, nie `ifg_postgres_data`)

### Faza 3 — uruchomienie stacku

1. Potwierdź: `docker-*` **Exited**, **nie usuwaj** ich przed Start.
2. `compose up -d` (kontenery obecnie zatrzymane)
3. Opcjonalnie `--build api` jeśli równolegle deploy kodu

### Faza 4 — weryfikacja (health)

Patrz sekcja 9 (checklist) — kroki 1–8.

### Faza 5 — Guardian verify + test funkcjonalny

1. Mac mini: `python3 scripts/guardian.py deploy check` (read-only)
2. Test funkcjonalny IFG (UI, faktury, KSeF) — patrz runbook

### Faza 6 — sprzątanie (tylko po pełnej walidacji Faz 4–5)

Usunąć **wyłącznie** stare kontenery (nie wolumeny) — **nigdy wcześniej**:

```bash
sudo docker rm docker-api-1 docker-worker-1 docker-db-1
```

### Faza 7 — Container Manager (UI)

Sprawdzić: **Projekt → `ifg`** z trzema usługami.

---

## 7. Komendy diagnostyczne (read-only)

Wykonać na DS723+:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# Repo
git branch --show-current && git rev-parse --short HEAD

# Projekt i zasoby compose (obecny stan)
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config \
  | grep -E '^name:|^    name:'

# Symulacja niebezpiecznego -p ifg (NIE stosować jako deploy)
sudo docker compose -p ifg -f docker/docker-compose.prod.yml --env-file .env.production config \
  | grep -E '^name:|postgres'

# Kontenery
sudo docker ps -a --filter "name=docker-" --format 'table {{.Names}}\t{{.Status}}'

# Wolumen prod
sudo docker volume inspect docker_postgres_data \
  --format 'Name={{.Name}} Mountpoint={{.Mountpoint}} Created={{.CreatedAt}}'

# Etykiety compose DB
sudo docker inspect docker-db-1 --format '{{index .Config.Labels "com.docker.compose.project"}}'

# Mounty DB
sudo docker inspect docker-db-1 --format '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

---

## 8. Komendy wykonawcze — **DO WYKONANIA DOPIERO PO AKCEPTACJI**

> ⚠️ Poniższe komendy **nie zostały wykonane** w ramach tego raportu.

### 8.1 Wdrożenie compose z repo

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull origin production
```

### 8.2 Gate przed uruchomieniem (OBOWIĄZKOWY)

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production config \
  | grep -E '^name:|postgres_data|ifg_prod'
```

**Oczekiwane po merge Wariantu A:**

```
name: ifg
name: docker_ifg_prod          # jeśli external network
name: docker_postgres_data     # MUSI być — nie ifg_postgres_data
```

**Jeśli widać `ifg_postgres_data` → STOP. Nie uruchamiać `up`.**

### 8.3 Uruchomienie stacku

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

Z rebuild obrazu (przy deploy kodu):

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

### 8.4 Sprzątanie starych kontenerów (po pełnej walidacji §9 + Guardian + test funkcjonalny)

**Warunek:** health OK, Guardian verify OK, test funkcjonalny IFG OK.

```bash
sudo docker rm docker-api-1 docker-worker-1 docker-db-1
```

**Nie wykonywać przed Start projektu `ifg`.** **Nie wykonywać:** `docker volume rm`, `docker compose down -v`.

---

## 9. Checklist weryfikacyjna po migracji

| # | Check | Oczekiwany wynik | ✓ |
|---|-------|------------------|---|
| 1 | `docker compose ps` (z repo root, ten sam `-f`) | `ifg-api-1`, `ifg-worker-1`, `ifg-db-1` **Up** | |
| 2 | Etykieta projektu | `com.docker.compose.project=ifg` | |
| 3 | Wolumen DB | nadal **`docker_postgres_data`**, mount w DB poprawny | |
| 4 | `curl -fsS http://127.0.0.1:8000/health` | JSON `"status":"ok"` | |
| 5 | `compose exec db pg_isready -U postgres -d ksef_backend` | `accepting connections` | |
| 6 | Liczba rekordów (sanity) | `SELECT COUNT(*) FROM invoices;` > 0 (prod) | |
| 7 | Worker log | `Worker startuje` bez crash loop | |
| 8 | Frontend | pliki z `frontend-react/dist` widoczne w API | |
| 9 | Container Manager → **Projekt** | widoczny projekt **`ifg`** (3 usługi) | |
| 10 | Stary stack `docker-*` | **Exited** do czasu sprzątania (rollback asset); po GO → `docker rm` | |
| 11 | Brak równoległego **Running** stacku | tylko `ifg-*` Running, `docker-*` Exited | |
| 12 | `cloudflared-ifg` | nadal Up (jeśli wymagany tunel) | |

---

## 10. Rollback plan

### Kiedy rollback

- `compose config` wskazuje zły wolumen po pull.
- DB startuje na pustej instancji (brak oczekiwanych tabel / COUNT=0).
- API health fail po 5 min.

### Kroki rollback (bez kasowania wolumenu)

**DO WYKONANIA DOPIERO PO AKCEPTACJI — tylko w razie problemu**

**Zaleta zachowania `docker-*` przed walidacją:** rollback nie wymaga odtwarzania kontenerów od zera — wystarczy zatrzymać `ifg` i podnieść stary projekt.

1. Zatrzymać nowy stack (projekt `ifg`):

   ```bash
   cd /volume1/docker/ifg_v2/ifg_standalone
   sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop
   ```

2. Przywrócić poprzedni commit compose (bez `name: ifg` / bez external) **lub** tymczasowo:

   ```bash
   git checkout <commit_przed_migracja> -- docker/docker-compose.prod.yml
   ```

3. Uruchomić stary projekt **`docker`** (zachowane kontenery `docker-*` ułatwiają powrót):

   ```bash
   sudo docker compose -p docker -f docker/docker-compose.prod.yml --env-file .env.production up -d
   ```

   Jeśli stary compose nie ma external pin — **upewnić się**, że domyślny wolumen to nadal `docker_postgres_data` (projekt `docker`).

4. Weryfikacja health + COUNT invoices.

5. **Nigdy** `docker volume rm docker_postgres_data`.

6. **Nie** usuwaj `docker-*` przed rollbackiem — są potrzebne do szybkiego powrotu.

### Ochrona danych

Dane produkcyjne są w **`docker_postgres_data`**. Rollback dotyczy **nazw kontenerów i projektu Compose**, nie samego wolumenu — o ile nie utworzono przypadkiem `ifg_postgres_data` (dlatego gate w §8.2 jest obowiązkowy).

---

## 11. Propozycja zmian w repo (Mac mini → git)

Plik: `docker/docker-compose.prod.yml`

```yaml
name: ifg

# ... services unchanged ...

volumes:
  postgres_data:
    name: docker_postgres_data
    external: true

networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

Opcjonalnie w nagłówku pliku zaktualizować przykład:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
```

---

## 12. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Dlaczego nie ma projektu IFG w DSM? | Projekt Compose nazywa się **`docker`**, nie `ifg` |
| Czy można migrować bez utraty DB? | **Tak**, z `name: ifg` + **`external: true`** na `docker_postgres_data` |
| Czy wystarczy samo `name: ifg`? | **Nie** — powstanie pusty `ifg_postgres_data` |
| Czy stack można podnieść teraz? | **Tak** — kontenery zatrzymane; wymaga akceptacji i merge compose |
| Guardian po migracji | `compose -f docker/docker-compose.prod.yml` z repo root; bez `-p docker` |

---

**Koniec raportu.**  
Operacje wykonawcze nie zostały uruchomione. **Wykonanie:** [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md) (STATUS: APPROVED).
