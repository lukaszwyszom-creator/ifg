# Guardian2 — walidacja pipeline deploy frontendu (dist vs src)

**Data:** 2026-05-22  
**Commit referencyjny:** `9abc884` — fix numerów purchase w `InvoiceCardList.jsx`  
**Zakres:** analiza statyczna + grep artefaktu `dist/` (bez deploy, bez `npm run build`, bez restartu kontenerów)  
**Kontekst produkcyjny:** objaw `01/05/2026` w UI przy poprawnych danych w DB

---

## Werdykt skrócony

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy hipoteza „stary dist” jest potwierdzona? | **TAK** (dowód lokalny dist ≠ src po 9abc884; pipeline prod umożliwia ten sam stan na DS723+) |
| Czy `npm run build` na DS723+ jest konieczny? | **TAK** — przy każdej zmianie w `frontend-react/src/` |
| Czy restart API jest wymagany po przebudowie dist? | **NIE** — volume mount `:ro` od razu widoczny w kontenerze |

---

## 1. Walidacja źródła (`src`)

**Plik:** `frontend-react/src/components/invoice/InvoiceCardList.jsx`

| Kryterium | Wynik |
|-----------|-------|
| Gałąź `direction === 'purchase'` w `preparedItems` | ✅ linie 171–189 |
| `displayNumber: rawNumber \|\| 'brak numeru'` | ✅ linia 182 |
| `numberSource: rawNumber ? 'ksef:P_2' : 'missing'` | ✅ linia 183 |
| `temporary_sequence` poza gałęzią purchase | ✅ tylko w bloku sale (linie 192–257, `ui:temporary_sequence` linia 239) |

**Commit:** HEAD = `9abc884` — fix obecny w repozytorium.

---

## 2. Walidacja artefaktu (`dist/assets/*.js`)

**Plik:** `frontend-react/dist/assets/index-D4VJtUbE.js`  
**Data modyfikacji bundle:** 2026-06-11 22:50  
**Data commita fix:** 2026-06-12 11:56 (`9abc884`)  
**Data modyfikacji `InvoiceCardList.jsx`:** 2026-06-12 11:45

→ **Bundle powstał ~13 h przed commitem fix** — nie zawiera zmian purchase numbering.

### Grep bundle (Guardian2-style)

| Wzorzec | Liczba trafień | Interpretacja |
|---------|----------------|---------------|
| `ksef:P_2` | **0** | brak fix purchase w dist |
| `brak numeru` | **0** | brak fix purchase w dist |
| `temporary_sequence` / `ui:temporary_sequence` | **1** | stary kod sale/temporary nadal w bundle |

**Wniosek:** lokalny `frontend-react/dist` odpowiada **staremu** frontendowi (generowanie `NN/MM/RRRR`), mimo poprawnego `src/`.

To jest bezpośredni dowód mechanizmu opisanego w `PURCHASE_UI_NUMBERING_PRODUCTION_ANALYSIS.md`.

> **Uwaga:** ten sam stan na DS723+ wystąpi, jeśli po `git pull` 9abc884 wykonano tylko `docker compose build api` bez `npm run build`.

---

## 3. Pipeline deploy — analiza plików

### 3.1 `docker/Dockerfile` (obraz `ifg-api`)

- Kopiuje: `app/`, `alembic/`, zależności Python.
- **Nie kopiuje** `frontend-react/`.
- **Nie uruchamia** `npm run build`.

### 3.2 `docker/docker-compose.prod.yml`

```yaml
api:
  volumes:
    - ../frontend-react/dist:/app/frontend-react/dist:ro
worker:
  # brak mountu dist — worker nie serwuje UI
```

- Frontend serwowany **wyłącznie** z katalogu **hosta** `frontend-react/dist`.
- `dist/` **nie jest** w obrazie Docker.
- `dist/` jest w `.gitignore` — `git pull` **nie aktualizuje** bundle.

### 3.3 `app/main.py`

```python
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend-react" / "dist"
application.mount("/ui", SPAStaticFiles(directory=str(FRONTEND_DIST_DIR), html=True))
```

- API czyta pliki statyczne z zamontowanej ścieżki w runtime.

### 3.4 Ścieżki wdrożenia

| Procedura | Buduje `dist`? | Ryzyko stale dist |
|-----------|----------------|-------------------|
| `docker compose … up -d --build` (DS723 checklist §4) | ❌ | **Wysokie** |
| Ręczny `git pull` + recreate api/worker | ❌ (domyślnie) | **Wysokie** |
| `guardian2.py deploy-ksef` remote krok 4 | ✅ `npm ci && npm run build` | Niskie |

**Guardian2 dry-run** (`python3 scripts/guardian2.py deploy-ksef --dry-run`):

- Lokalnie: krok 3 = `npm ci && npm run build`
- Remote DS723+: krok po `git pull` = `cd frontend-react && npm ci && npm run build`
- Następnie: `docker compose build api` + recreate api/worker

**Luka:** `guardian.py --ksef-async-check` weryfikuje `runPurchaseSync` w dist, **nie** weryfikuje markerów purchase numbering (`ksef:P_2`, `brak numeru`).

---

## 4. Mapowanie na produkcję DS723+

Bez SSH do DS723+ (poza zakresem tej sesji) — wnioskowanie:

| Obserwacja prod (zgłoszona) | Zgodność ze stale dist |
|-----------------------------|------------------------|
| DB: `vendor_other=50`, brak IFG w DB | ✅ API zwraca poprawne `number_local` |
| UI: format `01/05/2026` | ✅ sygnatura `ui:temporary_sequence` ze starego bundle |
| Backend wdrożony (9abc884) | ✅ Python w obrazie; frontend poza obrazem |
| Problem tylko w UI | ✅ klasyczny objaw src≠dist |

**Hipoteza „stary dist na DS723+”:** **potwierdzona logicznie i empirycznie** (lokalny dist jako proxy tego samego pipeline).

### Komendy weryfikacji na DS723+ (read-only, do wykonania operacyjnie)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# src ma fix
grep -n "ksef:P_2\|brak numeru" frontend-react/src/components/invoice/InvoiceCardList.jsx

# dist — oczekiwane PRZED naprawą: 0 trafień ksef:P_2, 1+ temporary_sequence
grep -c 'ksef:P_2' frontend-react/dist/assets/*.js
grep -c 'brak numeru' frontend-react/dist/assets/*.js
grep -c 'temporary_sequence' frontend-react/dist/assets/*.js

# daty
ls -la frontend-react/dist/assets/*.js
git log -1 --oneline
```

---

## 5. Restart API po przebudowie dist

**Nie wymagany.**

- Volume `../frontend-react/dist:/app/frontend-react/dist:ro` montuje katalog hosta.
- Po `npm run build` na hoście nowe pliki są natychmiast dostępne dla `StaticFiles`.
- Recreate kontenera **nie jest konieczny** wyłącznie z powodu odświeżenia dist.

**Wymagane w przeglądarce:** twarde odświeżenie (Ctrl+Shift+R) — Vite emituje hashowane nazwy plików; stary `index.html` w cache mógłby wskazywać poprzedni chunk.

---

## 6. Minimalna procedura naprawcza (DS723+)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull origin production                    # upewnij się: commit >= 9abc884
export PATH="/usr/local/bin:/opt/bin:/opt/homebrew/bin:$PATH"
cd frontend-react && npm ci && npm run build  # OBOWIĄZKOWE
cd ..

# weryfikacja
grep -c 'ksef:P_2' frontend-react/dist/assets/*.js    # oczekiwane: >= 1
grep -c 'temporary_sequence' frontend-react/dist/assets/*.js  # może być 1 (sale branch)

# restart API NIE jest wymagany; opcjonalnie tylko przy problemach z cache reverse proxy
```

Po buildzie: hard refresh w przeglądarce na `/ui/` → Advanced Dashboard → Faktury zakupowe → kolumna „Numer” = numer dostawcy z API.

---

## 7. Rekomendacje pipeline (bez implementacji w tym zadaniu)

1. Uzupełnić `DS723_DEPLOYMENT_CHECKLIST.md` o krok `npm run build` przed `docker compose up`.
2. Rozszerzyć `guardian.py --deploy-check` o grep `ksef:P_2` / `brak numeru` w `dist/assets/*.js`.
3. Traktować brak świeżego dist po zmianie w `frontend-react/src/` jako **bloker deployu UI**.

---

## 8. Podsumowanie Guardian2

| Etap walidacji | Status |
|----------------|--------|
| src zawiera fix 9abc884 | ✅ PASS |
| dist zawiera fix | ❌ **FAIL** (lokalny proxy prod) |
| Dockerfile buduje frontend | ❌ NIE |
| compose montuje host dist | ✅ TAK |
| deploy api/worker bez npm build aktualizuje UI | ❌ NIE |
| Guardian2 full deploy buduje dist | ✅ TAK |
| DS723 checklist domyślny deploy buduje dist | ❌ NIE |

**Przyczyna:** rozjazd **src (git) ↔ dist (artefakt hosta)** — `dist` nie jest częścią obrazu API ani repozytorium; samo wdrożenie backendu nie przebudowuje SPA.
