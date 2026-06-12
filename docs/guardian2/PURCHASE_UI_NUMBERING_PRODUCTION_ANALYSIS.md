# Analiza produkcyjna: fikcyjne numery IFG w liście zakupów (po 9abc884)

**Data:** 2026-05-22  
**Commit:** `9abc884` — fix numeracji purchase + sequence sale  
**Objaw:** UI pokazuje `01/05/2026` zamiast numerów dostawców; DB zweryfikowana jako poprawna (`vendor_other=50`, `ifg_format=0`).

---

## 1. Faktycznie używany komponent ( łańcuch renderowania )

| Warstwa | Plik | Rola |
|---------|------|------|
| Advanced Dashboard — zakładka „Faktury zakupowe” | `frontend-react/src/pages/advanced/AdvancedDashboard.jsx` | `{tab === 'purchase' && <InvoiceList direction="purchase" … />}` |
| Lista + paginacja + pool | `frontend-react/src/components/invoice/InvoiceList.jsx` | `<InvoiceCardList items={pagedItems} direction={direction} … />` |
| **Render kolumny „Numer”** | `frontend-react/src/components/invoice/InvoiceCardList.jsx` | `item.displayNumber` w pierwszej kolumnie |

**Wniosek:** jedyny komponent formatujący numer w liście zakupów Advanced Dashboard to **`InvoiceCardList.jsx`** (pośrednio przez `InvoiceList`).

Inne widoki (np. `OpenInvoicesPanel.jsx`) pokazują `number_local || '—'` — nie generują formatu `NN/MM/RRRR`. Objaw `01/05/2026` jest charakterystyczny **wyłącznie** dla starej logiki `ui:temporary_sequence` w `InvoiceCardList`.

---

## 2. Czy commit 9abc884 zmodyfikował właściwy komponent?

**TAK.**

Commit `9abc884` dodał w `InvoiceCardList.jsx` wczesną gałąź:

```javascript
if (direction === 'purchase') {
  // displayNumber = raw number_local || 'brak numeru'
  // bez parseBackendNumber / temporary_sequence
}
```

Przed fixem **cała** lista (sale i purchase) przechodziła przez `parseBackendNumber` + `displayNumber: \`${pad2(sequence)}/${month}/${year}\`` — stąd fikcyjne `01/05/2026` gdy `number_local` dostawcy nie pasował do wzorca IFG (`FV/n/MM/YYYY` lub `n/MM/YYYY`).

Kod źródłowy w repo (branch `production`) jest poprawny. Problem nie leży w wyborze komponentu ani w mapowaniu API.

---

## 3. Proces budowania i serwowania frontendu (produkcja)

### 3.1 Architektura prod

```
Źródło (git)     frontend-react/src/…
       ↓  npm run build  (POZA obrazem Docker API)
Artefakt         frontend-react/dist/   ← .gitignore, NIE w obrazie
       ↓  volume mount (read-only)
Kontener API     /app/frontend-react/dist
       ↓  FastAPI StaticFiles
URL              http://host:8000/ui/
```

**Kluczowe pliki:**

| Plik | Zachowanie |
|------|------------|
| `docker/docker-compose.prod.yml` | `volumes: ../frontend-react/dist:/app/frontend-react/dist:ro` — **dist z hosta**, nie z obrazu |
| `docker/Dockerfile` | Kopiuje tylko `app/`, **bez** frontendu |
| `docker/Dockerfile.frontend` | Osobny nginx build — **nieużywany** w `docker-compose.prod.yml` |
| `app/main.py` | `SPAStaticFiles` montuje `PROJECT_ROOT/frontend-react/dist` pod `/ui` |
| `.gitignore` | `frontend-react/dist/` — dist nigdy nie trafia przez `git pull` |

### 3.2 Typowe ścieżki wdrożenia

| Ścieżka | Backend | Frontend dist |
|---------|---------|---------------|
| `docker compose … up -d --build` (DS723 checklist) | ✅ rebuild obrazu `ifg-api` | ❌ **brak kroku `npm run build`** |
| Ręczny `git pull` + `build api` | ✅ nowy kod Python w obrazie | ❌ dist bez zmian, jeśli nie było buildu |
| `guardian2.py deploy-ksef` (remote) | ✅ pull + build api | ✅ **`npm ci && npm run build` na DS723+** |

**Guardian2 allowlist** (`DEPLOY_ALLOWLIST`) dotyczy tylko **lokalnego `git add`** — nie ogranicza `git pull` na serwerze. Po `pull` commit `9abc884` jest w `src/`, ale **bez `npm run build` dist pozostaje stary**.

---

## 4. Przyczyna problemu (werdykt)

### Główna przyczyna (wysokie P=95%)

**Produkcja serwuje stary bundle z `frontend-react/dist/` na hoście DS723+, podczas gdy backend został zaktualizowany do 9abc884.**

Mechanizm:

1. `git pull` pobiera poprawiony `InvoiceCardList.jsx` do katalogu źródeł.
2. Wdrożenie ograniczone do `docker compose build api && up -d` **nie przebudowuje** `dist/`.
3. API montuje **istniejący** katalog `dist/` (sprzed fixu).
4. Przeglądarka ładuje JS ze starą logiką `temporary_sequence` → numery `01/05/2026`.
5. API zwraca poprawne `number_local` z DB — ale stary JS je ignoruje i syntetyzuje numer.

To jest spójne z faktami użytkownika: **DB OK, backend OK, tylko UI złe**, format `NN/MM/YYYY` = stary kod UI (nie IFG z bazy).

### Przyczyny wtórne (niskie)

| Przyczyna | Ocena |
|-----------|-------|
| Cache przeglądarki | Możliwy po rebuild dist — Vite hashuje pliki w `assets/`, ale `index.html` może być cache'owany |
| Zły komponent | **Wykluczone** — Advanced Dashboard używa `InvoiceCardList` |
| Błędny commit / branch na serwerze | Możliwe — weryfikacja: `git log -1` + grep w `src` |
| `direction !== 'purchase'` w runtime | **Wykluczone** — wtedy nagłówek kolumny byłby „Nabywca”, nie „Sprzedawca” |

---

## 5. Diagnostyka na DS723+ (read-only)

```bash
# 1. Commit na serwerze
cd /volume1/docker/ifg_v2/ifg_standalone   # lub właściwa ścieżka
git log -1 --oneline

# 2. Fix w źródle (powinno zwrócić trafienia)
grep -n "ksef:P_2\|brak numeru" frontend-react/src/components/invoice/InvoiceCardList.jsx

# 3. Fix w PRODUKCYJNYM bundle (kluczowy test)
grep -l "ksef:P_2\|brak numeru" frontend-react/dist/assets/*.js 2>/dev/null || echo "BRAK FIX W DIST"

# 4. Stary kod w dist (jeśli nadal obecny = root cause potwierdzony)
grep -l "temporary_sequence\|ui:temporary" frontend-react/dist/assets/*.js 2>/dev/null

# 5. Data modyfikacji dist vs src
ls -la frontend-react/dist/assets/*.js | head -3
ls -la frontend-react/src/components/invoice/InvoiceCardList.jsx

# 6. API zwraca poprawny numer (porównanie z UI)
curl -fsS -H "Authorization: Bearer …" \
  "http://127.0.0.1:8000/api/v1/invoices/?direction=purchase&size=3" \
  | jq '.items[] | {number_local, issue_date}'
```

**Oczekiwany wynik przy root cause:**  
- `src/` zawiera `ksef:P_2`  
- `dist/assets/*.js` **nie** zawiera `ksef:P_2`, **zawiera** `temporary_sequence`  
- API `number_local` = numer dostawcy

---

## 6. Minimalna rekomendacja naprawy (bez automatycznego wdrożenia)

### A. Natychmiastowa naprawa prod (operacyjna)

Na DS723+, po `git pull` (commit ≥ 9abc884):

```bash
export PATH="/usr/local/bin:/opt/bin:/opt/homebrew/bin:$PATH"
cd frontend-react && npm ci && npm run build
```

**Restart API nie jest wymagany** — volume mount `dist/` jest od razu widoczny w kontenerze.  
W przeglądarce: twarde odświeżenie (Ctrl+Shift+R) lub tryb incognito.

Weryfikacja po buildzie:

```bash
grep -l "ksef:P_2" frontend-react/dist/assets/*.js
```

### B. Zapobieganie regresji (minimalne zmiany w repo — do osobnego PR)

1. **`docs/DS723_DEPLOYMENT_CHECKLIST.md`** — dodać obowiązkowy krok przed `docker compose up`:
   ```bash
   cd frontend-react && npm ci && npm run build
   ```

2. **`scripts/guardian.py --deploy-check`** (lub nowy `--frontend-purchase-number-check`) — sprawdzenie w `dist/assets/*.js`:
   - ✅ obecność `ksef:P_2` lub `brak numeru`
   - ❌ brak `temporary_sequence` w kontekście purchase (heurystyka: brak stringu `ui:temporary_sequence` jeśli jest gałąź purchase w src)

3. **Opcjonalnie:** skrypt `scripts/deploy-frontend-prod.sh` wywoływany zawsze razem z recreate api.

**Nie rekomenduje się** zmiany kodu React — fix w `InvoiceCardList.jsx` jest poprawny; problem to **pipeline deploy**, nie logika aplikacji.

---

## 7. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Komponent listy zakupów Advanced Dashboard | `InvoiceList` → **`InvoiceCardList.jsx`** |
| Czy 9abc884 trafił we właściwy plik? | **Tak** |
| Dlaczego UI nadal pokazuje `01/05/2026`? | **Stary `frontend-react/dist` na hoście** — backend-only deploy bez `npm run build` |
| Czy prod może serwować stary build przy aktualnym kodzie źródłowym? | **Tak** — dist nie jest w git ani w obrazie Docker API |
