# GWO-IFG-0046 — Production Push + Deploy + Runtime Verification

**Data:** 2026-07-08  
**Branch:** `production`  
**Zakres:** push + deploy + runtime verification

## Przebieg push

### Weryfikacja przed push

```bash
git status --short
git log origin/production..HEAD --oneline
```

`git log origin/production..HEAD --oneline` przed push:

```text
f5215b0 fix(auth): map invalid JWT sub to 401 instead of HTTP 500
876900f feat(guardian): GWO-IFG-0037 release engine quality
2fff98c fix(ksef): GWO-IFG-0036 monitor UI remnants
a8410f3 GWO-IFG-0036: fix KSeF monitor and production integrity policy
```

`git push origin production`:

```text
To github.com:lukaszwyszom-creator/ifg.git
   b7ad331..f5215b0  production -> production
```

### Weryfikacja po push

```bash
git log origin/production..HEAD --oneline
git log HEAD..origin/production --oneline
```

Wynik:
- `origin/production..HEAD`: brak wpisow
- `HEAD..origin/production`: brak wpisow

Wniosek: branch lokalny i zdalny sa zsynchronizowane po push.

## Wdrazone commity (push)

1. `a8410f3` — GWO-IFG-0036: fix KSeF monitor and production integrity policy
2. `2fff98c` — fix(ksef): GWO-IFG-0036 monitor UI remnants
3. `876900f` — feat(guardian): GWO-IFG-0037 release engine quality
4. `f5215b0` — fix(auth): map invalid JWT sub to 401 instead of HTTP 500

## Przebieg deployu (Guardian)

Uruchomione polecenie:

```bash
.venv/bin/python scripts/guardian.py ifg deploy run --yes --markdown
```

Wynik: **FAILED** (Guardian zablokowal produkcyjny deploy).

### Etap bledu (dokladny)

- `Stage init`: `Production deployment blocked. Working tree contains uncommitted changes.`
- `Stage blocker`: `6 blocker(s)`
- Policy decision: `PRODUCTION_BLOCKED (74/100)`

### Traceback

- Brak tracebacka Pythona (blad kontrolowany przez gate policy Guardiana).
- Komunikat koncowy:

```text
❌ Deploy workflow failed: FAILED
  Stage init: Production deployment blocked. Working tree contains uncommitted changes.
  Stage blocker: 6 blocker(s)
```

## Status kontenerow

Z raportu Guardiana (`IFG_RELEASE_EVALUATE_2026_07_08.md`):
- `docker compose config`: PASS
- `containers`: `api/worker/db running`
- `images`: compose ps returned 3 services

Uwaga: to status diagnostyczny przed mutujacym deployem; deploy nie zostal wykonany.

## Wynik endpointu `/api/v1/transmissions`

Nie wykonano runtime call po stronie sesji usera, poniewaz deploy zostal zablokowany na etapie gate (`PRODUCTION_BLOCKED`).

## Wynik Monitora KSeF

Niezweryfikowane w tej probie, bo zgodnie z instrukcja zatrzymano proces po pierwszym bledzie deployu.

Elementy niewykonane:
- ponowne logowanie i nowy JWT,
- otwarcie Monitora KSeF,
- ladowanie listy transmisji,
- odswiezanie,
- filtr "Tylko ostrzezenia i bledy",
- potwierdzenie HTTP 500 absence po deployu,
- kontrola nowych tracebackow po deployu.

## Wynik smoke testow

Nie wykonano (zatrzymanie po bledzie deploy gate):
- logowanie,
- lista faktur,
- Monitor KSeF,
- wyszukiwanie,
- podstawowe endpointy API,
- health endpoint.

## Lista zmodyfikowanych plikow

W ramach GWO-IFG-0046 zmodyfikowano:
- `docs/reports/2026-07-08_GWO-IFG-0046_PRODUCTION_DEPLOY.md`

## Lista wygenerowanych raportow `.md`

1. `docs/reports/2026-07-08_GWO-IFG-0046_PRODUCTION_DEPLOY.md`
2. `docs/guardian/IFG_DOCTOR_2026_07_08.md`
3. `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_08.md`

## 🩷 STATUS KONCOWY

### ✅ CO DZIALA

- Push `production -> origin/production` zakonczony sukcesem.
- Cztery oczekujace commity sa na origin.
- Guardian poprawnie zatrzymal ryzykowny deploy zgodnie z policy.

### ⚠️ ZNANE PROBLEMY

- Working tree pozostaje dirty (tracked + untracked), co aktywuje `dirty_working_tree_blocks_production`.
- Frontend gate (`npm run build` / dist freshness) jest niespelniony.

### ❌ CO NIE DZIALA

- Produkcyjny deploy w tej probie nie zostal wykonany (BLOCKED).
- Runtime verification i smoke test po deployu nie mogly zostac wykonane.

## A. ROOT CAUSE

Guardian policy gate zablokowal deploy przez niezcommitowane zmiany i niespelniony frontend build gate.

## B. ZMIENIONE PLIKI

- `docs/reports/2026-07-08_GWO-IFG-0046_PRODUCTION_DEPLOY.md`

## C. DEPLOY

Deploy przerwany na etapie `init/blocker` (FAILED, `PRODUCTION_BLOCKED`).

## D. TESTY

Brak testow runtime po deployu (deploy nie doszedl do etapu wykonania).

## E. NASTEPNY KROK

Potrzebna decyzja operatora: czy uruchomic deploy z jawnym override (`--allow-dirty-build --yes`) czy najpierw wyczyscic/izolowac working tree oraz domknac frontend build gate.
