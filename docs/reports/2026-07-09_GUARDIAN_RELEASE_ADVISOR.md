# GUARDIAN CORE — Release Advisor

🩷 STATUS KOŃCOWY

✅ Co działa
- Wykonano analizę release gate na rzeczywistym outputcie Guardiana (`release evaluate --markdown`).
- Zidentyfikowano blockery pierwotne i wtórne (agregaty/skutki).
- Przeanalizowano working tree i podzielono zmiany na logiczne grupy releasowe.
- Określono, co realnie blokuje `PRODUCTION_READY`.
- Zaproponowano architekturę nowej capability: `guardian release advise` (analityczna, read-only).

⚠️ Znane problemy
- Aktualny stan repo ma bardzo duży, mieszany zakres zmian (tracked + untracked), co utrudnia jednoetapowe domknięcie release.

❌ Co nie działa
- Release Gate pozostaje `PRODUCTION_BLOCKED` (`36/100`), dopóki nie zostaną domknięte blockery pierwotne.

## ETAP 1 — ANALIZA BLOKERÓW (SOURCE OF TRUTH: GUARDIAN)

Źródło:
- `PYTHONPATH=scripts python3 -m ifg_guardian.cli release evaluate --markdown`

Wykryte blockery z raportu:
1. `[backend] backend changes: 7 backend/alembic change(s)`
2. `[backend] build required: rebuild api/worker required before deploy`
3. `Policy rule triggered: dirty_working_tree_blocks_production`
4. `Policy rule triggered: tests_must_pass`
5. `Production deployment blocked. Working tree contains uncommitted changes.`
6. `Test discovery failed.`
7. `Test discovery: ... No module named pytest`

### Zależności i redukcja do blockerów pierwotnych

**Agregaty / skutki (nie naprawiamy bezpośrednio):**
- `PRODUCTION_BLOCKED` — wynik polityk, nie samodzielny problem.
- `Production deployment blocked...` — efekt dirty working tree.
- `Test discovery failed` — efekt braku `pytest`.

**Blockery pierwotne:**
1. Dirty working tree na branchu `production` (`dirty_working_tree_blocks_production`).
2. Niespełniony gate testów (`tests_must_pass`) + brak narzędzia test discovery (`pytest`).
3. Zmiany backend wymagające rebuild (`backend_change_requires_api_worker_rebuild`), które i tak zostają wtórnie zablokowane przez 1 i 2.

## ETAP 2 — ANALIZA WORKING TREE (GRUPY LOGICZNE)

Na podstawie `git status --porcelain`:

### 1) Monitor KSeF (frontend + backend + testy)
- Dotyczy: `app/api/routers/transmissions.py`, `app/persistence/**`, `app/schemas/**`, `frontend-react/src/components/dashboard/**`, `frontend-react/src/api/invoices.js`, `tests/unit/test_transmission_api.py`.
- Czy do releasu? **Tak (kandydat główny)**.
- Czy odłożyć? **Nie**, jeśli celem jest release Monitora.

### 2) Guardian Core / Platform
- Dotyczy: `scripts/ifg_guardian/**`, `scripts/guardian_platform/**`, nowe moduły core (dashboard/progress/deferred/reporting).
- Czy do releasu? **Częściowo** — tylko zmiany konieczne dla bieżącego celu release; reszta potencjalnie odłożyć/split.
- Czy odłożyć? **Tak, selektywnie**, gdy nie są wymagane do release Monitora.

### 3) Dokumentacja operacyjna i raporty
- Dotyczy: bardzo duży zestaw `docs/reports/**`, `docs/guardian/**`, inne `docs/*.md`.
- Czy do releasu? **Częściowo** (raporty istotne historycznie/operacyjnie).
- Czy odłożyć? **Tak, selektywnie**; nie powinny blokować technicznego gate jeśli repo jest uporządkowane.

### 4) Środowisko / lokalne artefakty
- Dotyczy: `.state/`, `reports/`, możliwe artefakty sesyjne.
- Czy do releasu? **Nie**.
- Czy odłożyć? **Tak** (powinny zostać poza releasem produkcyjnym).

### 5) Zmiany niejednoznaczne / mieszane
- Dotyczy: np. `pyproject.toml`, `scripts/ds723.env`, `frontend-react/vite.config.js`, `frontend-react/src/components/invoice/InvoiceActions.jsx`.
- Czy do releasu? **Wymaga decyzji scope**.
- Czy odłożyć? **Tak, jeśli nie są krytyczne dla Monitora KSeF i release gate**.

## ETAP 3 — ANALIZA TESTÓW (WG RELEASE GATE)

Na podstawie Guardiana wymagane są:
- Gate `tests_must_pass`.
- Sprawny test discovery (`pytest collect`) — obecnie **blokowany** przez brak `pytest`.

Stan:
- **Blokuje release:** test discovery (`No module named pytest`) -> `tests_must_pass`.
- **Już przechodzi:** build frontend (`npm run build` wg raportu evaluate: OK).
- **Można pominąć:** testy nienależące do gate policy (niepodpięte do release evaluate), ale tylko jeśli policy nie wymaga ich przejścia.

Wniosek:
- Bez naprawy test discovery oraz potwierdzenia przejścia wymaganych testów, `PRODUCTION_READY` nie zostanie osiągnięte.

## ETAP 4 — KONKRETNY PLAN DOJŚCIA DO PRODUCTION_READY

KROK 1  
Uruchom ponownie baseline:
- `guardian release evaluate --markdown`
Oczekiwany rezultat:
- aktualna lista blockerów i punkt startowy (już zebrane).

-------------------------

KROK 2  
Zdefiniuj release scope (co wchodzi do tego releasu) i odseparuj zmiany spoza scope.
Oczekiwany rezultat:
- working tree gotowy do domknięcia bez losowych/ubocznych zmian.

-------------------------

KROK 3  
Domknij dirty working tree dla scope release (brak nieuporządkowanych zmian blokujących policy).
Oczekiwany rezultat:
- znikają blockery: `dirty_working_tree_blocks_production` oraz `uncommitted changes`.

-------------------------

KROK 4  
Napraw test discovery środowiska i uruchom wymagany gate testów.
Oczekiwany rezultat:
- znika `Test discovery failed` i `tests_must_pass`.

-------------------------

KROK 5  
Wykonaj wymagany rebuild backend (`api/worker`) dla zmian backendowych.
Oczekiwany rezultat:
- spełniony warunek `backend_change_requires_api_worker_rebuild`.

-------------------------

KROK 6  
Uruchom finalną walidację:
- `guardian release evaluate --markdown`
Oczekiwany rezultat:
- `PRODUCTION_READY`.

## ETAP 5 — ARCHITEKTURA NOWEJ CAPABILITY: RELEASE ADVISOR

Proponowana komenda:
- `guardian release advise`

Cel:
- tylko analiza i plan (read-only), bez commit/deploy/push/mutacji.

### Proponowany workflow
1. Odpalenie `release evaluate --markdown` (lub reuse ostatniego wyniku).
2. Parsowanie policy blockerów i deduplikacja agregatów.
3. Analiza working tree:
   - klasyfikacja ścieżek do grup domenowych (backend/frontend/guardian/docs/artifacts),
   - wskazanie grup „IN RELEASE” vs „OUT OF SCOPE”.
4. Analiza test gate:
   - co jest wymagane przez policy,
   - co failuje,
   - co jest blockerem pierwotnym.
5. Render planu krok-po-kroku do `PRODUCTION_READY`.

### Sugerowany interfejs CLI
- `guardian release advise`
- `guardian release advise --json`
- `guardian release advise --markdown`
- `guardian release advise --project ifg`
- `guardian release advise --report docs/reports/...`

### Sugerowany output CLI (przykład)
```text
Release Advisor: PRODUCTION_BLOCKED
Primary blockers: 3
  1) Dirty working tree
  2) Tests gate (discovery/tooling)
  3) Backend rebuild required

Working tree groups:
  - KSeF Monitor: INCLUDE
  - Guardian Core: REVIEW
  - Documentation: SPLIT/DEFER
  - Local artifacts (.state/, reports/): EXCLUDE

Next actions:
  K1 scope freeze
  K2 clean tree
  K3 tests gate pass
  K4 rebuild api/worker
  K5 re-run release evaluate
```

A. Root cause
- Release jest blokowany przez kombinację: brudny working tree + niespełniony gate testów + wymagany rebuild backendu; agregat `PRODUCTION_BLOCKED` jest tylko skutkiem tych trzech klas problemu.

B. Zmienione pliki
- `docs/reports/2026-07-09_GUARDIAN_RELEASE_ADVISOR.md`

C. Deploy
- Nie wykonywano deployu.

D. Testy
- Nie uruchamiano zmian kodu; wykonano tylko workflow analityczny `release evaluate`.

E. Następny krok
- Wdrożyć capability `guardian release advise` jako workflow read-only oparty na istniejących danych z `release evaluate` + klasyfikacji working tree.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-09_GUARDIAN_RELEASE_ADVISOR.md`
