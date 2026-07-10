# Weryfikacja: `frontend-react/dist/index.html` po cutover `ifg` + pełny deploy

**Data:** 2026-07-06  
**Zakres:** analiza read-only (bez LIVE cutover, bez deployu, bez restartu)  
**Pytanie:** Czy po przejściu na projekt Compose `ifg` i wykonaniu pełnego procesu deploy plik `frontend-react/dist/index.html` zostanie **poprawnie wygenerowany i udostępniony**?

---

## Werdykt

# NIE

Pełny proces (cutover LIVE + `ifg deploy run`) **nie gwarantuje** obecności ani poprawnego serwowania `index.html` na DS723+. Wymaga **jawnych kroków operatora** poza samym cutoverem.

---

## Uzasadnienie (skrót)

| # | Fakt | Wpływ na werdykt |
|---|------|------------------|
| 1 | `git pull` / cutover **nie dostarczają** `dist/` | `index.html` **nie pojawi się** z repozytorium (`dist/` w `.gitignore`, usunięty z indeksu w `f25c54b`) |
| 2 | Workflow `ifg cutover run` **nie zawiera** `npm run build` ani rsync dist | Sam LIVE cutover **nie generuje** `index.html` |
| 3 | `docker compose up -d` / `--build` buduje **tylko obraz API** | Dockerfile API **nie kopiuje** `frontend-react/dist` — dist jest bind-mountem z hosta |
| 4 | `ifg deploy run` buduje frontend **warunkowo** | Krok `frontend build` + `dist sync` może być **pominięty**, gdy Doctor uzna dist za „aktualny” lokalnie |
| 5 | Weryfikacja remote **nie sprawdza** `index.html` | `check_remote_frontend_dist_freshness()` patrzy na `dist/assets/*.js`, nie na istnienie `index.html` |
| 6 | Stan faktyczny DS723+ (2026-07-06) | `assets/` istnieją, **`index.html` MISSING** — po pull/unblock |
| 7 | Migracja `docker` → `ifg` | **Nie zmienia** ścieżki mountu — serwowanie OK **tylko jeśli** plik jest na hoście |

---

## 1. Architektura serwowania frontendu (bez zmian po cutover)

Produkcja **nie ma** osobnego kontenera frontend/nginx. UI jest serwowane z API:

```yaml
# docker/docker-compose.prod.yml (api)
volumes:
  - ../frontend-react/dist:/app/frontend-react/dist:ro
```

```103:107:app/main.py
    # Serve frontend SPA under /ui with SPA fallback to index.html.
    if FRONTEND_DIST_DIR.is_dir():
        application.mount(
            "/ui",
            SPAStaticFiles(directory=str(FRONTEND_DIST_DIR), html=True),
```

- Vite (`npm run build`) emituje `frontend-react/dist/index.html` + `assets/*`.
- Bind-mount `:ro` — pliki muszą **istnieć na hoście DS723+** przed/during działania API.
- Zmiana `name: ifg` w compose **nie zmienia** mountu `../frontend-react/dist` — mechanizm udostępniania jest ten sam.

**Wniosek:** Udostępnienie zależy wyłącznie od zawartości katalogu na hoście, nie od nazwy projektu Compose.

---

## 2. Co robi LIVE cutover (`ifg cutover run`)

Etapy workflow (`scripts/ifg_guardian/plugins/ifg/container_cutover/`):

| Etap | Zawiera build frontend? |
|------|-------------------------|
| backup | nie |
| git_pull | nie |
| compose_config_gate | nie |
| preflight | nie (nie gate'uje `index.html`) |
| cutover_up (`docker compose up -d`) | nie |
| post_health (`curl /health`, SQL, worker logs) | **nie** — brak `test -f .../index.html` |
| guardian_verify (`deploy check`) | nie sprawdza `index.html` na remote |
| functional_gate | ręczna checklista operatora |

Skrypt startu projektu `ifg`:

```92:93:scripts/ifg_guardian/plugins/ifg/container_cutover/remote.py
def cutover_up_script(cfg: DS723Config) -> str:
    return f"{compose_base(cfg)} up -d\n"
```

Runbook (`docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md`) opcjonalnie wspomina `build api`, **nie** `npm run build` frontendu.

**Wniosek:** Sam cutover LIVE **nie generuje ani nie synchronizuje** `index.html`.

---

## 3. Co robi pełny deploy (`ifg deploy run`)

Pipeline (`plugins/ifg/deploy_run/pipeline.py`):

1. `git pull` (remote)
2. `cd frontend-react && npm run build` — **lokalnie na Mac mini** (warunkowo)
3. `rsync ... frontend-react/dist/` → DS723+ (warunkowo)
4. `docker compose build api worker` (remote)
5. `docker compose up -d` (remote, projekt `ifg` z pliku)
6. `curl /health`, logi

### 3.1 Warunkowe pominięcie buildu

`detect_build_decisions()` ustawia `Frontend Build` / `Static Files` na `required=False`, gdy Doctor uzna dist za świeży **lokalnie** (`frontend.build_required` PASS, `frontend.dist_freshness` PASS, brak zmian src).

Doctor ocenia **Mac mini**, nie stan DS723+. Przy lokalnym dist „OK” kroki 2–3 są **skipped**.

### 3.2 Luka weryfikacji remote

```164:177:scripts/ifg_guardian/modules/frontend.py
def check_remote_frontend_dist_freshness(host: str, repo_path: str) -> tuple[bool, str]:
    ...
    dist_ts = remote_frontend_dist_newest_epoch(host, repo_path)
    if dist_ts is None:
        return False, f"❌ [DS723+] {FRONTEND_DIST_STALE_MSG}"
```

`remote_frontend_dist_newest_epoch()` czyta mtime **`dist/assets/*.js`**, nie `index.html`.

**Scenariusz potwierdzony na DS723+ (2026-07-06):**

```
frontend-react/dist/
  assets/index-*.js   ← istnieją (2026-07-03)
  index.html          ← MISSING (po git checkout HEAD podczas pull unblock)
```

Taki stan może przejść część kontroli „świeżości dist”, a UI pod `/ui` **nie zadziała poprawnie** (brak entrypoint SPA).

### 3.3 `preflight-ds723.sh` vs workflow cutover

`scripts/preflight-ds723.sh` **sprawdza** `index.html`:

```46:52:scripts/preflight-ds723.sh
echo "[preflight] frontend-react/dist na NAS:"
DIST_OK="$(ssh ... test -f '.../frontend-react/dist/index.html' ...)"
```

Ten skrypt **nie jest** częścią `ifg cutover run` ani `ifg deploy run`.

---

## 4. Wpływ `git pull` i housekeeping

Commit `f25c54b` (w zakresie pull `a405646` → `0cbaeba`):

- `git rm --cached -r frontend-react/dist/` — dist poza indeksem Git
- `.gitignore` zawiera `frontend-react/dist/`

Po pull:

- pliki `dist/` **nie są** aktualizowane z remote
- `git checkout HEAD -- frontend-react/dist/index.html` (pull unblock) **usuwa** lokalny `index.html`, jeśli plik nie jest już w HEAD

To wyjaśnia obecny brak `index.html` mimo pozostałych `assets/`.

---

## 5. Tabela: skąd bierze się `index.html`

| Źródło | Generuje `index.html`? |
|--------|------------------------|
| `git pull` | **NIE** (gitignored) |
| `ifg cutover run --yes` | **NIE** |
| `docker compose up -d --build` | **NIE** (tylko obraz API) |
| `npm run build` (Mac lub DS723+) | **TAK** (Vite → `dist/index.html`) |
| `rsync dist/` na DS723+ | **TAK** (kopia, jeśli wykonany po buildzie) |
| `ifg deploy run --yes` | **TAK, warunkowo** (kroki 2–3 tylko gdy Doctor wymusi build) |

---

## 6. Serwowanie po udostępnieniu pliku

Gdy `index.html` **istnieje** na hoście w `frontend-react/dist/`:

| Element | Status |
|---------|--------|
| Mount w kontenerze `ifg-api-1` | `../frontend-react/dist:/app/frontend-react/dist:ro` |
| FastAPI mount | `/ui` → `SPAStaticFiles` z fallbackiem na `index.html` |
| Cloudflare → origin | `http://127.0.0.1:8000` (ścieżki `/ui/...`) |
| Restart API po zmianie dist | **Nie wymagany** — bind-mount odświeża się natychmiast |

Projekt `ifg` vs `docker` **nie wpływa** na powyższe — zmienia się tylko nazwa kontenerów (`ifg-api-1` zamiast `docker-api-1`).

---

## 7. Warunki, pod którymi odpowiedź byłaby TAK

Odpowiedź **TAK** obowiązywałaby wyłącznie gdy operator **przed** `compose up` projektu `ifg` wykona:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone/frontend-react
npm ci    # jeśli package-lock się zmienił
npm run build
test -f ../frontend-react/dist/index.html && echo "OK"
```

**albo** na Mac mini: `npm run build` + rsync z SSH (jak w `docs/WORKFLOW.md`) **i** potwierdzi obecność pliku na DS723+.

Te kroki **nie są** automatycznie egzekwowane przez cutover LIVE.

---

## 8. Rekomendacja przed LIVE cutover

1. **Traktuj build frontendu jako GO gate** — niezależny od cutover:
   - `test -f frontend-react/dist/index.html` na DS723+ (jak `preflight-ds723.sh`)
2. **Nie polegaj na `git pull`** dla dist.
3. **Rozważ** dodanie gate'a `index.html` do `post_health` cutover lub `functional_gate` checklisty.
4. **Po obecnym stanie DS723+** — przed jakimkolwiek `up -d`: przywróć/build dist (backup: `backups/pull_unblock_20260706_224806/index.html.bak` to minimum awaryjne, nie zastępuje pełnego `npm run build` przy nowym HEAD).

---

## 9. Odpowiedź jednoznaczna

### Czy po cutover `ifg` + pełny deploy `index.html` zostanie poprawnie wygenerowany i udostępniony?

# NIE

**Uzasadnienie:** Automatyczny łańcuch cutover + deploy **nie gwarantuje** wygenerowania `index.html` na DS723+ (cutover go nie buduje; deploy może pominąć build/sync; weryfikacja nie gate'uje `index.html`). Udostępnienie przez API działa poprawnie **tylko jeśli** plik istnieje na hoście — obecnie **nie istnieje**. Wymagany jest **jawny** `npm run build` (+ sync) przed lub w ramach procedury operatora, z potwierdzeniem `test -f frontend-react/dist/index.html`.

---

*Analiza read-only. LIVE cutover, deploy i restart nie wykonano.*
