# UI deploy diag — stara tabela pozycji PZ na DS723+

**Data:** 2026-06-19  
**Zakres audytu:** `frontend-react/src`, `frontend-react/dist`, `docker/docker-compose.prod.yml`, `docker/Dockerfile`, `docker/Dockerfile.frontend`

---

## 1. Plik źródłowy z nagłówkami tabeli pozycji

**`frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`**

Tabela pozycji towarowych (formularz `DocForm` + podgląd `DocDetail`) w zakładce Magazyn → Dokumenty.  
Brak osobnego komponentu „szczegółu produktu” — pozycje dokumentu PZ/WZ/KK są wyłącznie tutaj.

*(Kartoteka towarów: `CatalogTab.jsx` — inna tabela, poza zakresem zmian PZ.)*

---

## 2. Nagłówki w kodzie źródłowym (obecnie)

**PZ** (`docType === 'PZ'` / `doc.doc_type === 'PZ'`):

| Kolumna |
|---------|
| Towar |
| ISBN |
| ILOŚĆ |
| CENA ZAKUPU (NETTO) |
| STAWKA VAT |
| NORMATYWNA CENA SPRZEDAŻY BRUTTO |

**Inne typy (KK/WZ)** — bez zmian:

| Kolumna |
|---------|
| Towar |
| ISBN |
| Ilość |
| Cena zakupu *(KK)* |
| Cena suger. / Cena sprzedaży *(detail)* |

---

## 3. `frontend-react/dist` — nowe czy stare nagłówki?

**Nowe** (lokalny build z 2026-06-19, `index-CuztDB4W.js`):

- `ILOŚĆ`, `CENA ZAKUPU (NETTO)`, `STAWKA VAT`, `NORMATYWNA CENA SPRZEDAŻY BRUTTO` — **obecne**
- Stare etykiety (`Cena suger.`, `Ilość`, `Cena zakupu`) — **nadal w bundlu**, ale tylko dla gałęzi KK/WZ (oczekiwane)

Stare nagłówki PZ (`VAT %`, jedna kolumna `Cena suger.` zamiast normatywnej brutto) — **brak w lokalnym dist**.

---

## 4. Skąd kontener API serwuje frontend

| Warstwa | Ścieżka |
|---------|---------|
| URL publiczny | `/ui/` (redirect z `/`) |
| Mount FastAPI | `SPAStaticFiles` na `/ui` |
| Katalog w kontenerze | **`/app/frontend-react/dist`** |
| Pliki statyczne | `/ui/assets/index-*.js`, `/ui/index.html` |

*(Źródło mountu: `app/main.py` — `FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend-react" / "dist"`; poza zakresem audytu, potwierdza compose.)*

---

## 5. Kopiowanie vs volume

| Mechanizm | Zachowanie |
|-----------|------------|
| `docker/Dockerfile` (API) | **Nie kopiuje** `frontend-react/dist` do obrazu |
| `docker/docker-compose.prod.yml` | **Bind mount:** `../frontend-react/dist:/app/frontend-react/dist:ro` |
| `docker/Dockerfile.frontend` | Buduje SPA + nginx — **nieużywany** w `docker-compose.prod.yml` (brak serwisu frontend) |

**Wniosek:** Produkcja serwuje **zawartość katalogu `frontend-react/dist` na hoście DS723+**, nie z warstwy obrazu API. Samo `docker compose … up --build` **nie** przebudowuje frontendu.

---

## 6. Dlaczego DS723+ może pokazywać starą tabelę

1. **Brak `npm run build` na hoście** po `git pull` — stary `dist/` nadal montowany do kontenera.
2. **`--build` przebudowuje tylko obraz Pythona** — nie dotyka JS bundla.
3. **Cache przeglądarki** — mniej prawdopodobne po pełnym rebuildzie (Vite zmienia hash pliku w `index.html`); możliwe jeśli `index.html` jest cache'owany a stary JS nadal istnieje na dysku.
4. **Niesynchronizowany kod źródłowy** — jeśli `DocumentsTab.jsx` nie trafił na NAS (niecommitowane zmiany), nawet build da stary UI.

---

## 7. Minimalna procedura wdrożenia (gwarantuje nowe nagłówki)

Na DS723+, z katalogu głównego repozytorium (`ifg_standalone/`):

```bash
# 1. Pobierz kod ze zmianami w DocumentsTab.jsx
git pull   # lub rsync/scp — ważne: aktualny src

# 2. Zbuduj frontend na hoście (wymagane!)
cd frontend-react
npm ci
npm run build
cd ..

# 3. Weryfikacja przed restartem (opcjonalnie, na hoście)
grep -o 'NORMATYWNA CENA SPRZEDAŻY BRUTTO' frontend-react/dist/assets/index-*.js | head -1
# oczekiwane: jedna linia z tekstem

# 4. Przeładuj kontener API (mount dist jest :ro — wystarczy nowy plik na hoście)
docker compose -f docker/docker-compose.prod.yml up -d api
# lub: docker compose -f docker/docker-compose.prod.yml restart api

# 5. Weryfikacja w kontenerze (opcjonalnie)
docker compose -f docker/docker-compose.prod.yml exec api \
  grep -l 'NORMATYWNA CENA' /app/frontend-react/dist/assets/index-*.js
```

**Hard refresh** w przeglądarce (Ctrl+Shift+R) po wdrożeniu.

`docker compose … up --build` **bez kroku 2 nie wystarczy**.

---

## Pliki objęte audytem

- `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`
- `frontend-react/dist/index.html`
- `frontend-react/dist/assets/index-CuztDB4W.js`
- `docker/docker-compose.prod.yml`
- `docker/Dockerfile`
- `docker/Dockerfile.frontend` *(istnieje, nieużywany w prod compose)*
