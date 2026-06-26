# Guardian2 / DS723+ — diagnoza: migracja PZ draft niewidoczna w kontenerze api

**Data:** 2026-06-19  
**Commit prod:** `6d00b34` — `feat(warehouse): PZ draft as real stock`  
**Oczekiwana migracja:** `f8a9b0c1d2e3` (revizja po `e7f8a9b0c1d2`)  
**Objaw:** `git` na hoście = `6d00b34`, `alembic current` w kontenerze `api` = `e7f8a9b0c1d2 (head)`

---

## 1. Analiza Guardian2 deploy flow

### Co robi `guardian2.py deploy-ksef` (remote)

Sekwencja w `scripts/guardian2.py` → `deploy_ksef_remote()`:

| Krok | Polecenie | Efekt |
|------|-----------|--------|
| 1 | `git pull origin production` | Aktualizuje **pliki na hoście** |
| 2 | `npm ci && npm run build` (frontend-react) | Odświeża **bind-mount** `dist/` |
| 3 | `docker compose build api` | **Przebudowuje obraz** z `COPY alembic`, `COPY app` |
| 4 | `docker compose up -d --no-deps --force-recreate api worker` | Nowe kontenery na nowym obrazie |
| 5 | `guardian.py --ksef-async-check`, `--deploy-check`, `curl /health` | Weryfikacja |

Guardian2 **nie uruchamia** `alembic upgrade head` — migracja pozostaje krokiem operacyjnym ręcznym (zgodnie z `DS723_DEPLOYMENT_CHECKLIST.md` §5).

### Co robi `guardian.py --deploy-check`

- Porównuje **git HEAD** Mac mini / origin / DS723+
- Sprawdza **świeżość `frontend-react/dist`**
- Sprawdza **`docker compose ps`** (api/worker/db running)
- **Nie sprawdza:** rewizji Alembic w obrazie vs hoście, `alembic heads` w kontenerze, ani czy obraz był przebudowany po `git pull`

### Architektura prod (`docker/docker-compose.prod.yml`)

```yaml
api:
  image: ifg-api:latest
  build: { context: .., dockerfile: docker/Dockerfile }
  volumes:
    - ../frontend-react/dist:/app/frontend-react/dist:ro   # tylko UI
    - ../.env.production:/app/.env:ro
  # BRAK bind-mount: app/, alembic/
```

`docker/Dockerfile`:

```dockerfile
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
```

**Wniosek:** Kod backendu i pliki migracji są **wbudowane w obraz Docker** w momencie `docker compose build api`. Samo `git pull` na hoście **nie aktualizuje** działającego kontenera.

---

## 2. Dokładna przyczyna problemu

### Przyczyna główna (potwierdzona architekturą)

**Kontener `api` działa na starym obrazie `ifg-api:latest`**, zbudowanym przed commitem `6d00b34`. Obraz zawiera katalog `/app/alembic/versions/` **bez** pliku `f8a9b0c1d2e3_*.py`, więc wewnątrz kontenera:

- `alembic heads` → nadal **`e7f8a9b0c1d2e3`**
- `alembic history` → brak rewizji `f8a9b0c1d2e3`

To **nie jest** rozjazd bazy z repo — to **stary filesystem aplikacji w kontenerze**.

### Wyjaśnienie `alembic current` vs `alembic heads`

| Polecenie | Co pokazuje | Wartość oczekiwana **przed** `upgrade head` |
|-----------|-------------|---------------------------------------------|
| `alembic current` | Rewizja **zapisana w DB** | `e7f8a9b0c1d2` — **normalne** |
| `alembic heads` | Najnowsza rewizja **w plikach w kontenerze** | powinno być `f8a9b0c1d2e3` po rebuild |

Jeśli użytkownik widzi `(head)` przy `e7f8a9b0c1d2`, oznacza to że **w kontenerze** `e7f8` jest nadal ostatnią znaną rewizją w kodzie — potwierdzenie starego obrazu.

Typowy scenariusz na DS723+:

```text
git pull / checkout 6d00b34     ✅ pliki na hoście OK
docker compose up -d api        ❌ restart bez --build → stary obraz
# lub
git pull bez compose build api  ❌
```

Guardian2 `deploy-ksef` robi `build api`, ale:

- scenariusz **KSeF-only** z allowlistą — deploy magazynu mógł być **ręczny** (sam `git pull`)
- checklist DS723 §4: `up -d --build` — `--build` przy `up` czasem **nie przebudowuje**, jeśli Docker uzna warstwy za aktualne (cache); bezpieczniej jawne `compose build api`

---

## 3. Minimalny plan naprawy

```text
1. Potwierdź plik migracji na hoście (git + ls)
2. docker compose build api          ← kluczowe
3. Weryfikacja: alembic heads w kontenerze = f8a9b0c1d2e3
4. force-recreate api + worker
5. alembic upgrade head              ← DB do f8a9 (backup już jest)
6. backfill PZ draft (no-op przy 0 draft)
7. verify_pz_draft_backfill.sql (E3 gate)
8. npm run build (frontend E5)
9. smoke: health, PZ draft UI, Stany
```

**Polityka IFG:** bez `down -v`, bez resetu DB, bez usuwania volume — plan spełnia wymagania.

---

## 4. Dokładne komendy DS723+

Załóż katalog repo (dostosuj jeśli inny niż checklist):

```bash
export IFG_ROOT=/volume1/docker/ifg/ifg_standalone
export COMPOSE="sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production"
cd "$IFG_ROOT"
```

> Guardian domyślnie używa `DEFAULT_REMOTE_PATH=/volume1/docker/ifg_v2/ifg_standalone` — zweryfikuj faktyczną ścieżkę: `pwd`.

### A. Diagnostyka (read-only)

```bash
git rev-parse HEAD
git log -1 --oneline
ls alembic/versions/f8a9b0c1d2e3_pz_draft_nullable_layer_cost.py

# Host vs kontener — kluczowy test
$COMPOSE exec api ls alembic/versions/f8a9b0c1d2e3_pz_draft_nullable_layer_cost.py
# Oczekiwane po rebuild: plik istnieje
# Teraz (stary obraz): ls: cannot access ... → potwierdzenie diagnozy

$COMPOSE exec api alembic heads
$COMPOSE exec api alembic current
```

### B. Naprawa (wykonaj w oknie maintenance)

```bash
cd "$IFG_ROOT"

# 1. Rebuild obrazu api (worker używa ifg-api:latest — ten sam build)
$COMPOSE build api

# 2. Gate: migracja widoczna w NOWYM obrazie
$COMPOSE run --rm api alembic heads
# Oczekiwane: f8a9b0c1d2e3 (head)

# 3. Recreate kontenerów na nowym obrazie
$COMPOSE up -d --no-deps --force-recreate api worker

# 4. Migracja DB (backup już wykonany)
$COMPOSE exec api alembic upgrade head
$COMPOSE exec api alembic current
# Oczekiwane: f8a9b0c1d2e3 (head)

# 5. E2 backfill (prod: 0 PZ draft → no-op)
$COMPOSE exec api python -m scripts.backfill_pz_draft_layers --dry-run
$COMPOSE exec api python -m scripts.backfill_pz_draft_layers --execute

# 6. E3 gate SQL
$COMPOSE exec -T db psql -U postgres -d ksef_backend < scripts/verify_pz_draft_backfill.sql

# 7. Frontend E5 (bind-mount dist — wymagany osobno od rebuild api)
cd frontend-react && npm ci && npm run build && cd ..

# 8. Smoke
curl -fsS http://127.0.0.1:8000/health
$COMPOSE ps
```

### C. Rollback (awaryjny, bez niszczenia volume)

```bash
# Cofnięcie migracji (tylko jeśli upgrade już poszedł i trzeba wrócić)
$COMPOSE exec api alembic downgrade e7f8a9b0c1d2

# Przywrócenie poprzedniego obrazu: checkout poprzedniego commitu + build api + recreate
# Przywrócenie DB: pg_restore z backupu (poza scope — backup już jest)
```

---

## 5. Wymagania rebuild / restart / frontend

| Akcja | Wymagana? | Uzasadnienie |
|-------|-----------|--------------|
| **`docker compose build api`** | **TAK** | `alembic/` i `app/` są w obrazie, nie na volume |
| **Restart / recreate `api`** | **TAK** | `--force-recreate` po build |
| **Restart / recreate `worker`** | **TAK** | Ten sam `image: ifg-api:latest` — stary kod worker |
| **`npm run build` frontend** | **TAK** | E5 zmienia `DocumentsTab.jsx`, `BalanceTab.jsx`; dist bind-mount |
| **Restart `db`** | **NIE** | Volume `postgres_data` nietknięty |
| **`down -v`** | **NIE** | Zabronione polityką IFG |

---

## 6. Czy wdrożenie można kontynuować?

**TAK** — po wykonaniu sekwencji B (build → heads gate → recreate → `upgrade head` → backfill → verify SQL → frontend build).

**NIE kontynuować** `alembic upgrade head` ani testów PZ draft **przed** rebuildem api — upgrade na starym obrazie i tak nie zobaczy `f8a9`, a aplikacja E4 bez nowego kodu w obrazie będzie niespójna.

Stan prod z audytu (0 PZ draft, 1 posted PZ) → backfill E2 = no-op, ryzyko danych **niskie** po poprawnym rebuild + migrate.

---

## 7. Guardian2 — luka i proponowana poprawka (bez implementacji)

### Luka

1. **`--deploy-check` nie porównuje `alembic heads` host vs kontener**
2. **Brak checku „obraz vs git”** po deployu ręcznym (`git pull` bez `build`)
3. **`deploy-ksef`** to scenariusz KSeF z allowlistą — **nie obejmuje** deployu magazynowego; użytkownik mógł pominąć krok `build api`
4. **`alembic upgrade`** nigdy nie jest w Guardian2 — łatwo zrobić pull bez migrate

### Proponowana poprawka (minimalna, do osobnego commitu)

Dodać do `scripts/guardian.py` (np. `--deploy-check` lub `--alembic-check`):

```python
# Pseudokod
host_head = git show HEAD:alembic/versions/ | grep -l f8a9...  # lub: alembic heads na hoście w venv
container_heads = ssh "compose exec -T api alembic heads"
if host_head != container_heads:
    ERROR "Obraz api niezgodny z repo — wymagany: docker compose build api && recreate"
```

Dodatkowo w `guardian2.py`:

- Nowy scenariusz `deploy-warehouse` **lub** rozszerzenie remote o obowiązkowy krok:
  - `compose build api`
  - `compose exec api alembic heads` == oczekiwany
  - opcjonalnie prompt przed `alembic upgrade head`
- Po `git pull` na remote: jeśli `git diff OLD..NEW --name-only` zawiera `alembic/versions/` lub `app/` → **fail** gdy obraz nie był rebuildowany (porównanie `docker inspect` Created vs git commit timestamp)

Komunikat dla operatora:

```text
❌ DS723+: alembic heads w kontenerze (e7f8a9b0c1d2) != repo (f8a9b0c1d2e3).
   Wykonaj: docker compose build api && up -d --force-recreate api worker
```

---

## 8. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Dlaczego migracja niewidoczna? | Stary obraz Docker; `alembic/` nie jest mountowany z hosta |
| Czy `git pull` wystarczy? | **Nie** |
| Co naprawi? | `compose build api` + recreate api/worker + `alembic upgrade head` |
| Czy kontynuować wdrożenie PZ draft? | **Tak**, po naprawie obrazu i migracji |
| Guardian2 winny? | Częściowo — flow KSeF ma build, ale brak detekcji rozjazdu obraz/repo |

---

## Powiązane dokumenty

- [`docs/PZ_DRAFT_IMPLEMENTATION_REPORT.md`](PZ_DRAFT_IMPLEMENTATION_REPORT.md)
- [`docs/DS723_DEPLOYMENT_CHECKLIST.md`](DS723_DEPLOYMENT_CHECKLIST.md)
- [`docs/GUARDIAN2_DEPLOY.md`](GUARDIAN2_DEPLOY.md)
- [`docs/guardian2/FRONTEND_DIST_DEPLOY_VALIDATION.md`](guardian2/FRONTEND_DIST_DEPLOY_VALIDATION.md)
