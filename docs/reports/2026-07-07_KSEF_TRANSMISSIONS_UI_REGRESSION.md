# GWO-IFG-0035 — Diagnostyka regresji zakładki KSeF po wdrożeniu PurchaseAuth

**Data:** 2026-07-07  
**Zakres:** read-only — bez naprawy  
**Kontekst:** deploy GWO-IFG-0034 (`b7ad331`) na DS723+

---

## 🩷 STATUS KOŃCOWY

### ✅ Co ustalono z dowodami

1. **Błąd transmisji** — HTTP **500** z `GET /api/v1/transmissions/`, przyczyna: `TransmissionResponse.invoice_id` wymaga UUID, a wpisy dziennika KSeF mają `invoice_id = NULL`.
2. **Stara nazwa zakładki** — zmiana na „Monitor KSeF” **nie jest w commicie `production`**; istnieje tylko w niezcommitowanym working tree lokalnym.

### ⚠️ Znane problemy

- Deploy GWO-IFG-0034 zbudował frontend z **lokalnego dirty tree** (Guardian `LOCAL_NPM`), więc `dist/` na DS723+ może zawierać „Monitor KSeF”, podczas gdy **git na serwerze** nadal ma „Transmisje KSeF”.
- Na serwerze pozostał stary bundle `index-SvT4fhAr.js` (rsync bez `--delete`) — ryzyko cache przeglądarki.

### ❌ Co nie jest regresją PurchaseAuth w sensie strict

- Sam kod `PurchaseAuthService` **nie zmienia** endpointu `/transmissions/`.
- Błąd ujawnia **istniejącą niezgodność schematu API** z modelem Monitor KSeF (journal bez `invoice_id`), przyspieszoną przez **nowe wpisy dziennika** z dzisiejszego syncu/auth.

---

## Problem 1 — „Błąd ładowania transmisji” + pusta tabela

### Przepływ React → API → Backend → Render

```
AdvancedDashboard (tab=transmissions)
  → TransmissionTable.load()
    → transmissionsApi.list(page, size, warningsOnly)
      → GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=false
        → list_transmissions() [transmissions.py]
          → transmission_service.list_all()
            → _transmission_to_response() × N
              → TransmissionResponse (Pydantic)
    ← axios: HTTP 500 (catch)
  → setError('Błąd ładowania transmisji')
  → setData NIE aktualizowane (pozostaje { items: [], total: 0 })
  → Table rows=[] → emptyMsg="Brak transmisji"
  → alert alert-error z komunikatem
```

### Frontend

| Element | Plik | Zachowanie |
|---------|------|------------|
| Wywołanie API | `frontend-react/src/api/transmissions.js` | `GET /transmissions/` z `page`, `size`, `warnings_or_errors_only` |
| Obsługa błędu | `TransmissionTable.jsx:64-65` | `catch { setError('Błąd ładowania transmisji'); }` — **bez logowania statusu HTTP** |
| Pusta tabela | `TransmissionTable.jsx:219-223` | `rows={data.items}` przy `items=[]` → „Brak transmisji” |
| Komunikat czerwony | `TransmissionTable.jsx:216` | `{error && <div className="alert alert-error">…` |

### HTTP i odpowiedź backendu (produkcja DS723+, 2026-07-07 ~23:52)

**Request (z logów API, autoryzowany użytkownik UI):**

```
GET /api/v1/transmissions/?page=1&size=20 HTTP/1.1" 500 Internal Server Error
```

**Wyjątek (fragment logu `ifg-api-1`):**

```
File "/app/app/api/routers/transmissions.py", line 101, in list_transmissions
    items=[_transmission_to_response(t) for t in items],
File "/app/app/api/routers/transmissions.py", line 57, in _transmission_to_response
    return TransmissionResponse(...)
pydantic_core.ValidationError: 1 validation error for TransmissionResponse
invoice_id
  UUID input should be a string, bytes or UUID object [type=uuid_type, input_value=None, input_type=NoneType]
```

**Odpowiedź do klienta:** brak poprawnego JSON — ASGI 500 (axios trafia w `catch`).

### Przyczyna backendowa

| Warstwa | Stan |
|---------|------|
| `TransmissionORM.invoice_id` | **nullable** (`UUID \| None`) — wpisy dziennika KSeF bez faktury |
| `TransmissionResponse.invoice_id` | **wymagane** `UUID` (nie optional) — `app/schemas/transmission.py:11` |
| Serializacja | `_transmission_to_response()` przekazuje `invoice_id=None` → Pydantic ValidationError |

### Dane produkcyjne (dowód)

```sql
-- DS723+ ksef_backend, 2026-07-07
SELECT COUNT(*) total, COUNT(*) FILTER (WHERE invoice_id IS NULL) null_invoice FROM transmissions;
-- total=69, null_invoice=20

SELECT date_trunc('day', created_at), COUNT(*) FILTER (WHERE invoice_id IS NULL)
FROM transmissions GROUP BY 1 ORDER BY 1 DESC;
-- TYLKO 2026-07-07: 20 wierszy z invoice_id IS NULL
```

Przykładowe wpisy z `invoice_id IS NULL` (utworzone 2026-07-07):

| operation_type | severity | status |
|----------------|----------|--------|
| `SESSION_RENEWED` | SUCCESS | authenticated |
| `PURCHASE_SYNC_AUTO` | SUCCESS | ok |
| `PURCHASE_METADATA_FETCH` | INFO | success |
| `SCHEDULER_SKIP_ALREADY_EXECUTED` | INFO | skipped |
| `ERROR` | ERROR | failed |

### Czy to regresja po PurchaseAuth?

| Aspekt | Ocena |
|--------|-------|
| Bezpośrednia zmiana w `/transmissions/` w GWO-IFG-0032/0033 | **Nie** — commit `b7ad331` nie dotykał `transmissions.py` ani schematów |
| Pośredni związek z deployem GWO-IFG-0034 | **Tak** — pierwszy udany purchase auth + sync zapisał wpisy dziennika (`SESSION_RENEWED`, `PURCHASE_SYNC_AUTO`, …) z `invoice_id=NULL` |
| Bug schematu Monitor KSeF | **Tak, pre-existing** — od implementacji journal w `transmissions`; wcześniej na prod **wszystkie** wiersze miały `invoice_id` (0 null przed 2026-07-07), więc endpoint „działał” |

**Wniosek:** PurchaseAuth **ujawnił** latentny błąd serializacji listy transmisji, zapisując pierwsze wpisy dziennika bez `invoice_id`. To nie jest błąd logiki auth, ale **skutek uboczny** nowych zdarzeń KSeF w tabeli `transmissions`.

---

## Problem 2 — Nazwa zakładki „Transmisje KSeF”

### Gdzie powinna być zmiana

| Lokalizacja | Oczekiwana nazwa (Monitor KSeF) | Stan w `git production` (`b7ad331`) | Stan working tree lokalnie |
|-------------|--------------------------------|--------------------------------------|----------------------------|
| Zakładka `TABS` | `Monitor KSeF` | `Transmisje KSeF` | `Monitor KSeF` ✅ (niezcommitowane) |
| Tytuł w `TransmissionTable` | `Monitor KSeF` | `Transmisje KSeF` | `Monitor KSeF` ✅ (niezcommitowane) |
| Tooltip `invoiceOpenMode.js` | (opcjonalnie) | `Transmisje KSeF` | bez zmian |

### Czy zmiana została zaimplementowana?

**Częściowo — tylko lokalnie, poza commitem deployu GWO.**

```bash
# commit b7ad331 (wdrożony backend)
git show b7ad331:frontend-react/src/pages/advanced/AdvancedDashboard.jsx
# → { id: 'transmissions', label: 'Transmisje KSeF' }

# working tree (lokalnie, NIE w production)
grep transmissions frontend-react/src/pages/advanced/AdvancedDashboard.jsx
# → label: 'Monitor KSeF'
```

**Remote DS723+ źródło po `git pull`:**

```
{ id: 'transmissions', label: 'Transmisje KSeF' },
```

### Czy trafiła do właściwego komponentu?

Tak — w working tree zmiana jest w:

- `frontend-react/src/pages/advanced/AdvancedDashboard.jsx` — **przyciski zakładek**
- `frontend-react/src/components/dashboard/TransmissionTable.jsx` — **nagłówek panelu**

To są właściwe komponenty (nie pominięte przez merge w plikach źródłowych — **nie były w ogóle commitowane**).

### Czy frontend build na produkcji zawiera zmianę?

**Niespójnie:**

| Artefakt | `Transmisje KSeF` (tab) | `Monitor KSeF` (tab) |
|----------|-------------------------|----------------------|
| `index-SvT4fhAr.js` (2026-07-06, osierocony) | **3×** (w tym `{id:"transmissions",label:"Transmisje KSeF"}`) | 0 |
| `index-B6-DH4n-.js` (2026-07-07, w `index.html`) | 1× (tylko tooltip `invoiceOpenMode`) | **2×** (tab + tytuł) |
| `index.html` aktywny | wskazuje `index-B6-DH4n-.js` | ✅ |

**Dlaczego dist ma Monitor KSeF mimo git `Transmisje KSeF`?**

Guardian deploy (`ifg.deploy.run`) buduje frontend **lokalnie** z maszyny operatora (`LOCAL_NPM` — `cd frontend-react && npm run build`), a nie z czystego stanu gita na DS723+. Deploy GWO-IFG-0034 użył **niezcommitowanego** working tree z rename → `dist/` na serwerze ma „Monitor KSeF”, ale **repozytorium na DS723+ nie**.

### Dlaczego użytkownik nadal widzi „Transmisje KSeF”?

Najbardziej prawdopodobne przyczyny (z dowodami):

1. **Cache przeglądarki** — stary `index.html` / `index-SvT4fhAr.js` (nadal na dysku DS723+, rsync bez `--delete`).
2. **Źródło prawdy git** — każdy kolejny deploy z czystego `production` **przywróci** „Transmisje KSeF” w `dist`, dopóki rename nie zostanie commitnięty.
3. **Mylenie z tooltipem** — `invoiceOpenMode.js` nadal mówi „zakładkę Transmisje KSeF” (1 wystąpienie w nowym bundle).

---

## Proponowane poprawki (do osobnego zadania — nie implementowano)

### 1. Błąd transmisji (krytyczne)

```python
# app/schemas/transmission.py
invoice_id: UUID | None = None
```

Opcjonalnie: w `_transmission_to_response` jawnie mapować `None` dla wpisów dziennika; dodać test API z wierszem `invoice_id=NULL`.

**Priorytet:** P0 — blokuje Monitor KSeF na produkcji.

### 2. Nazwa zakładki

- Commitnąć rename w `AdvancedDashboard.jsx` + `TransmissionTable.jsx` (+ opcjonalnie tooltip w `invoiceOpenMode.js`).
- Deploy z **czystego** commita (nie dirty tree).
- `rsync --delete` dla `frontend-react/dist/assets/` lub polityka cache-bust (Vite już hashuje nazwy — wystarczy usunąć stare chunki).

**Priorytet:** P2 — kosmetyka / spójność UX.

### 3. UX diagnostyki (opcjonalnie)

W `TransmissionTable.jsx` w `catch` logować `err.response?.status` i treść `error.message` zamiast generycznego komunikatu.

---

## Podsumowanie decyzyjne

| Problem | Przyczyna | Regresja PurchaseAuth? |
|---------|-----------|------------------------|
| Czerwony „Błąd ładowania transmisji” + „Brak transmisji” | HTTP 500 — Pydantic odrzuca `invoice_id=None` przy wpisach dziennika KSeF | **Pośrednio** — auth/sync utworzyły pierwsze takie wpisy dziś |
| Nazwa „Transmisje KSeF” | Rename **nie commitnięty**; cache / stary bundle; deploy z dirty tree | **Nie** — pominięty commit, nie merge |

---

## A. Root cause

1. **API:** `TransmissionResponse` vs nullable `invoice_id` w ORM + journal entries.
2. **UI nazwa:** rename Monitor KSeF poza commitem `production`.

## B. Zmienione pliki (diagnoza)

Brak zmian kodu w ramach GWO-IFG-0035.

## C. Deploy

Nie wykonano.

## D. Testy

Weryfikacja operacyjna: logi API DS723+, zapytania SQL, analiza bundle `dist/`.

## E. Następny krok

Osobne zadanie naprawcze: schemat `invoice_id` optional + commit rename + redeploy frontend z czystego gita.

---

## Lista wykonanych analiz

1. Grep komunikatów UI: „Błąd ładowania transmisji”, „Transmisje KSeF”, „Monitor KSeF”.
2. Odczyt `TransmissionTable.jsx`, `transmissions.js`, `AdvancedDashboard.jsx`, `Table.jsx`.
3. Odczyt `app/api/routers/transmissions.py`, `app/schemas/transmission.py`, `TransmissionORM`.
4. Analiza przepływu błędu w `catch` + stan początkowy `data.items`.
5. Logi produkcyjne API DS723+ (`500` + traceback Pydantic).
6. Zapytania SQL: liczba `transmissions` z `invoice_id IS NULL`, rozkład po dacie.
7. Próbkowanie wpisów dziennika (`SESSION_RENEWED`, `PURCHASE_SYNC_AUTO`, …).
8. Porównanie `git show b7ad331` vs working tree dla nazwy zakładki.
9. Weryfikacja źródeł na DS723+ po deploy.
10. Analiza bundle `index-B6-DH4n-.js` vs `index-SvT4fhAr.js` (prod + lokalnie).
11. Weryfikacja `index.html` i nagłówków cache na `/ui/`.
12. Analiza pipeline Guardiana (`LOCAL_NPM` build z lokalnego dirty tree).
13. Ocena związku z GWO-IFG-0032/0034 (commit scope vs skutki uboczne journal).
