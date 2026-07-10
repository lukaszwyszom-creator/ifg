# GWO-IFG-0044 — Deploy Relevance Assessment

**Data:** 2026-07-08  
**Zakres:** ocena wpływu dirty working tree na wdrożenie poprawki auth z GWO-0042  
**Deploy:** nie wykonywano (zgodnie z poleceniem)

---

## Kontekst

Guardian blokuje deploy przy dirty tree regułą globalną (`dirty_working_tree_blocks_production`).  
Ten raport ocenia **relewantność** zmian względem wdrożenia poprawki:

- `app/services/auth_service.py` (fix 500 -> 401 dla legacy/uszkodzonych tokenów),
- `tests/unit/test_auth_service.py` (test regresyjny).

---

## 1) Czy zmiany poza GWO-0042 wpływają na deploy poprawki auth?

**Tak, część z nich wpływa istotnie.**

Aktualny dirty tree (159 pozycji):

- **33 modified**
- **126 untracked**

Podział:

- `app/*`: 6
- `frontend-react/*`: 4
- `scripts/ifg_guardian/*`: 22
- `tests/*`: 7
- `docs/*`: 117
- `scripts/*` (inne): 2
- `other` (`pyproject.toml`): 1

Zmiany, które wpływają na ryzyko deployu poprawki auth:

1. **`app/*` poza samym `auth_service.py`**  
   (dodatkowe backendowe zmiany mogą zostać wdrożone razem z fixem auth i zmienić runtime API).

2. **`scripts/ifg_guardian/*`**  
   (to warstwa control-plane; zmienia zachowanie samego narzędzia deployowego).

3. **`frontend-react/*` + `vite.config.js`**  
   (jeśli workflow obejmuje budowę/sync frontend artefaktów, mogą wejść niezamierzone zmiany UI/build).

4. **`pyproject.toml`**  
   (zmiana zależności/środowiska wykonania może wpływać na stabilność procesu lub runtime).

---

## 2) Czy poprawka może zostać bezpiecznie wdrożona mimo dirty tree?

**Nie w obecnym stanie globalnie.**

Możliwe jest to tylko warunkowo, jeżeli deploy byłby **ściśle izolowany** do:

- commit zawierający wyłącznie:
  - `app/services/auth_service.py`
  - `tests/unit/test_auth_service.py`
- bez dołączania innych zmian backend/control-plane/frontend.

W obecnym drzewie ryzyko przypadkowego „przyklejenia” obcych zmian jest zbyt duże.

---

## 3) Które pliki rzeczywiście blokują deploy (relevance = BLOCKER)?

### A. Runtime backend (wysoki wpływ)

- `app/persistence/mappers/invoice_mapper.py`
- `app/persistence/models/invoice.py`
- `app/persistence/repositories/transmission_repository.py`
- `app/services/invoice_number_policy.py`
- `app/services/payment_service.py`

**Powód:** to kod wykonywany produkcyjnie, niezwiązany z fixem auth.

### B. Control-plane deploy (wysoki wpływ na sam proces)

- `scripts/ifg_guardian/core/workflow/*`
- `scripts/ifg_guardian/core/frontend_artifacts.py`
- `scripts/ifg_guardian/modules/*`
- `scripts/ifg_guardian/plugins/ifg/*`
- `scripts/ifg_guardian/config.py`
- `scripts/ifg_guardian/core/deploy_config.py`

**Powód:** modyfikuje logikę Guardiana używaną do deployu.

### C. Build/runtime environment

- `pyproject.toml`

**Powód:** zmiany środowiska i zależności.

### D. Frontend artefakt scope (jeśli deploy obejmuje frontend)

- `frontend-react/src/api/invoices.js`
- `frontend-react/src/components/invoice/InvoiceActions.jsx`
- `frontend-react/vite.config.js`

**Powód:** ryzyko wciągnięcia niepowiązanych zmian UI/build.

---

## 4) Które pliki są niepowiązane i nie powinny blokować wdrożenia?

### Niskie ryzyko / non-blocking (dla backend auth hotfix)

1. **Dokumentacja i raporty** (`docs/**`, w tym `docs/reports/**`, `docs/guardian/**`)  
   - nie wpływają na runtime aplikacji.

2. **Testy niezwiązane z artifactem runtime** (`tests/**` poza testem regresyjnym auth)  
   - powinny być sygnałem jakości, ale nie blockerem deploy relevance dla hotfixu, jeśli nie ma zmian runtime.

3. **Pliki operatorskie lokalne** (`scripts/ds723.env`)  
   - powinny być klasyfikowane oddzielnie (warning/policy), nie jako runtime blocker fixu auth.

---

## 5) Proponowane reguły „deploy relevance” dla Guardiana

### Reguła 1 — Scope-based target map

Dla deployu typu `backend_hotfix_auth` Guardian buduje mapę relewantności:

- **Target paths (must):** `app/services/auth_service.py`, powiązane testy auth/transmissions.
- **Runtime blockers:** każde dodatkowe zmiany w `app/**`, `alembic/**`, `docker/**`.
- **Control-plane blockers:** zmiany w `scripts/ifg_guardian/**` (gdy deploy wykonywany Guardianem lokalnym).

### Reguła 2 — Noise allowlist

Nie blokować automatycznie deployu przez:

- `docs/reports/**`
- `docs/guardian/**`
- inne `docs/**` (status: warning/information).

### Reguła 3 — Frontend conditional relevance

- jeśli deploy flagowany jako backend-only: `frontend-react/**` -> warning + wymóg potwierdzenia, nie hard-blocker,
- jeśli pipeline zawiera frontend build/sync -> `frontend-react/**` staje się blockerem.

### Reguła 4 — Risk scoring zamiast binary gate

Wprowadzić wynik:

- `RELEVANT_SAFE`
- `RELEVANT_WITH_WARNINGS`
- `RELEVANT_BLOCKED`

z listą konkretnych plików i uzasadnieniem per plik.

### Reguła 5 — Isolated hotfix override

Dodać tryb:

`guardian ifg deploy run --relevance-scope backend-auth-hotfix --allow-dirty-nonrelevant`

Warunki:

- brak dodatkowych zmian runtime/control-plane,
- dirty ogranicza się do allowlist (docs/tests/raporty),
- jawny raport ryzyka i potwierdzenie operatora.

---

## Wniosek końcowy

Aktualny dirty tree nie jest „nieszkodliwie brudny” dla GWO-0042.  
Są w nim realne zmiany runtime backend i control-plane Guardiana, które **powinny blokować** deploy poprawki auth w modelu bezpiecznym.

Jednocześnie większość `docs/**` jest niepowiązana i nie powinna sama z siebie blokować wdrożenia — to dobry kandydat do reguł deploy relevance w Guardianie.

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Przeprowadzono klasyfikację wpływu zmian względem deployu GWO-0042.
- Wskazano realne blokery i zmiany niepowiązane.
- Zaproponowano zestaw reguł „deploy relevance” do wdrożenia w Guardianie.

### ⚠️ Znane problemy

- Obecna polityka Guardiana jest globalna (`dirty tree`), bez semantycznej oceny relewantności zmian.

### ❌ Co nie działa

- Brak automatycznego mechanizmu pozwalającego bezpiecznie dopuścić deploy przy dirty tree ograniczonym do non-runtime noise.

---

## A. Root cause

Binarny gate „dirty tree” bez klasyfikacji wpływu na konkretny deploy scope.

## B. Zmienione pliki

- `docs/reports/2026-07-08_GWO-IFG-0044_DEPLOY_RELEVANCE_ASSESSMENT.md`

## C. Deploy

Nie wykonywano.

## D. Testy

Nie dotyczy (zadanie analityczne).

## E. Następny krok

Zaimplementować w Guardianie etap `deploy relevance assessment` przed finalnym gatingiem production.

