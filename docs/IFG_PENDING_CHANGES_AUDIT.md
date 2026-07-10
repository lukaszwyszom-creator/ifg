# IFG Pending Changes Audit

**Data:** 2026-05-22  
**Zakres:** 10 plików w `app/`, `frontend-react/` widocznych jako `M` w `git status`  
**Metoda:** `git diff -w`, `git diff --ignore-cr-at-eol`, porównanie bajtów `HEAD` vs working tree

---

## Podsumowanie

| Metryka | Wartość |
|---------|---------|
| Pliki z realnymi zmianami funkcjonalnymi | **0** |
| Pliki wyłącznie CRLF/LF (artefakt EOL) | **10** |
| Rekomendacja globalna | **discard** — nie commitować |

---

## Kontekst techniczny

Repozytorium ma w `.gitattributes`:

```
* text=auto eol=lf
*.py text eol=lf
*.js text eol=lf
*.jsx text eol=lf
```

Pliki w indeksie Git są zapisane z terminatorami **CRLF**. Working tree ma **identyczne bajty** jak `HEAD` (potwierdzone skryptem porównującym surowe bajty). Git nadal pokazuje status `M`, ponieważ przy porównaniu stosuje normalizację `eol=lf` — `git hash-object` na pliku dyskowym daje inny hash niż blob w indeksie, mimo że treść logiczna jest taka sama.

`git diff -w` i porównanie znormalizowane (`\r\n` → `\n`) dla wszystkich 10 plików: **brak różnic**.

---

## Analiza plik po pliku

### 1. `app/api/deps.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 229 insertions, 229 deletions  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak** (229 linii CRLF)

---

### 2. `app/domain/enums.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 110 / 110  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

---

### 3. `app/persistence/mappers/invoice_mapper.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 277 / 277  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

---

### 4. `app/persistence/models/invoice.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 64 / 64  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

---

### 5. `app/persistence/repositories/transmission_repository.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 105 / 105  
- `git diff -w`: pusty  
- `git diff --ignore-cr-at-eol`: pokazuje 105/105 (fałszywy alarm — wynika z filtra Git, nie z różnicy treści względem `HEAD`)  
- Bajty `HEAD` == working tree: **tak**

---

### 6. `app/services/invoice_number_policy.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 22 / 22  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

Powiązane dokumenty w WIP (`docs/FV_*NUMBERING*`) dotyczą osobnych, niezacommitowanych notatek — **nie** tych zmian w pliku.

---

### 7. `app/services/payment_service.py`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 626 / 626  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

Duży diff stat wynika wyłącznie z liczby linii z CRLF, nie z refaktoru logiki płatności.

---

### 8. `frontend-react/src/api/invoices.js`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 33 / 33  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

---

### 9. `frontend-react/src/components/invoice/InvoiceActions.jsx`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 319 / 319  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

---

### 10. `frontend-react/vite.config.js`

| Pytanie | Odpowiedź |
|---------|-----------|
| Wyłącznie CRLF/LF? | **Tak** |
| Zmiany funkcjonalne? | **Nie** |
| Opis / zadanie IFG | — |
| Commit message | — (discard) |

- `git diff --stat`: 58 / 58  
- `git diff -w`: pusty  
- Bajty `HEAD` == working tree: **tak**

---

## Rekomendacja

### discard (zalecane)

Te pliki **nie powinny trafić do żadnego commita** w obecnym WIP. Nie zawierają zmian funkcjonalnych względem `HEAD`.

Opcje wyczyszczenia statusu `M`:

```bash
# Przywrócenie z HEAD (treść i tak jest identyczna bajtowo)
git restore app/ \
  frontend-react/src/api/invoices.js \
  frontend-react/src/components/invoice/InvoiceActions.jsx \
  frontend-react/vite.config.js

# Jeśli status M nadal widoczny — to znany konflikt .gitattributes (eol=lf) vs CRLF w historii.
# Nie tworzyć commita „chore: normalize line endings” bez osobnej decyzji i git add --renormalize.
```

### commit — nie

Brak uzasadnienia do commita: zero diff logicznego względem `HEAD`.

### review — nie wymagane

Żaden plik nie wymaga review funkcjonalnego. Ewentualna przyszła praca nad numeracją FV / magazynem / KSeF jest w **osobnych**, jeszcze niezacommitowanych plikach docs i teście `invoiceCardListNumbering.test.js` — nie w tych 10 plikach.

---

## Powiązane WIP (poza tym audytem)

| Element | Status |
|---------|--------|
| `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | Nowy plik — osobny commit testowy (Commit 3 z planu WIP) |
| `docs/FV_*`, `docs/PZ_*`, `docs/WAREHOUSE_*` | Dokumentacja domenowa — osobny commit docs |
| Funkcjonalne zmiany backend/frontend w powyższych 10 plikach | **Brak** |
