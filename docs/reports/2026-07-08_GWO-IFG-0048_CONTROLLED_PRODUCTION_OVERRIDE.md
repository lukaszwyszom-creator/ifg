# GWO-IFG-0048 — Controlled Production Override

**Data:** 2026-07-08  
**Branch:** `production`  
**Target commit:** `f5215b0`  
**Status:** FAILED (deploy zatrzymany przez Safety Gate)

---

## Uzasadnienie override

Override (`--allow-dirty-build`) zostal uruchomiony swiadomie, bo po GWO-0047:
- frontend build gate byl domkniety (`npm run build` PASS, `dist freshness` PASS),
- `ifg.doctor` mial status `READY_WITH_WARNINGS`,
- jedyny twardy blocker decyzji produkcyjnej wynikal z polityki `dirty_working_tree_blocks_production`.

Override nie byl proba pominiecia realnych kontroli technicznych (build/health/log checks), tylko obejsciem ograniczenia policy dla dirty working tree.

---

## Potwierdzenie synchronizacji origin/HEAD

Wykonane przed deploy:

```bash
git log origin/production..HEAD --oneline
git log HEAD..origin/production --oneline
git status --short
```

Wyniki:
- `origin/production..HEAD`: brak wpisow
- `HEAD..origin/production`: brak wpisow
- `git status --short`: dirty working tree lokalnie (tracked + untracked)

Wniosek:
- origin i lokalny HEAD sa zsynchronizowane.
- Deploy target to commit `f5215b0`.
- Dirty working tree jest lokalnym stanem roboczym i nie zmienia commita pobieranego z GitHub (`git pull origin production` na host docelowy zawsze pobiera `f5215b0`).

---

## Przebieg deployu (controlled override)

Uruchomione polecenie:

```bash
.venv/bin/python scripts/guardian.py ifg deploy run --allow-dirty-build --yes --markdown
```

Kluczowe etapy:
- `ifg.doctor`: SUCCESS (`READY_WITH_WARNINGS`)
- `ifg.release.plan`: SUCCESS (risk `MEDIUM`)
- `ifg.release.evaluate`: SUCCESS (decision `READY_WITH_OVERRIDE`)
- `ifg.deploy.run`: **FAILED** na etapie `preflight`

Dokladny blad:

```text
❌ Deploy workflow failed: FAILED
  Stage preflight: Safety Gate NO_GO (1 blocking item(s))
```

Traceback:
- brak tracebacka Pythona (kontrolowany fail Guardiana na Safety Gate).

Zgodnie z instrukcja stop-on-error proces zostal zatrzymany natychmiast i nie wykonywano dalszych mutacji.

---

## Wynik backup policy

- **Niewykonano** (pipeline nie przeszedl etapu preflight).
- Backup policy pozostaje wymaganiem z raportow release/doctor.

## Wynik buildow

- Frontend (`npm run build`): PASS (wykonane w GWO-0047, przed override).
- Build `api/worker`: **niewykonano** w tej probie (stop na preflight).

## Wynik restartu

- **Niewykonano** (zatrzymanie na preflight).

## Wynik health

- Brak nowej powdrozeniowej weryfikacji health, bo deploy nie doszedl do etapu wykonania.

## Wynik endpointu `/transmissions`

- Brak nowej powdrozeniowej weryfikacji endpointu:
  `GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=false`
- Powod: deploy nie zostal wykonany.

## Wynik Monitora KSeF

- **Niezweryfikowane** (deploy nie przeszedl).
- Niewykonane kroki:
  - wylogowanie/ponowne logowanie,
  - nowy JWT,
  - lista transmisji,
  - odswiezanie,
  - filtr "Tylko ostrzezenia i bledy",
  - potwierdzenie braku HTTP500 i nowych tracebackow po deploy.

## Wynik smoke testow

- **Niezweryfikowane** (deploy nie przeszedl).
- Niewykonane:
  - logowanie,
  - lista faktur,
  - Monitor KSeF,
  - health,
  - podstawowe endpointy.

---

## Koncowy status

**FAILED**

Przyczyna: `Stage preflight: Safety Gate NO_GO (1 blocking item(s))`.

---

## Rekomendacja pierwszego GWO dla projektu Guardian (po tym incydencie)

**GWO-IFG-0049 (proponowane):**
Dodać do Guardiana jawny raport `preflight blocking items` dla `ifg deploy run` (z pełną listą blokujących punktów i ich źródłem), aby przy `Safety Gate NO_GO` operator od razu widział konkretną przyczynę bez potrzeby dodatkowej diagnostyki.

---

## Lista wszystkich wygenerowanych raportow `.md`

1. `docs/reports/2026-07-08_GWO-IFG-0048_CONTROLLED_PRODUCTION_OVERRIDE.md`
2. `docs/guardian/IFG_DOCTOR_2026_07_08.md`
3. `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_08.md`
4. `docs/guardian/IFG_RELEASE_PLAN_2026_07_08.md`

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIALA

- Synchronizacja `origin/production` i lokalnego `HEAD` potwierdzona.
- Controlled override uruchomiony poprawnie (`READY_WITH_OVERRIDE` na etapie evaluate).

### ⚠️ ZNANE PROBLEMY

- Deploy zatrzymany przez `Safety Gate NO_GO` na etapie preflight.
- Guardian nie wypisal wprost blocking item details w output markdown z tego przebiegu.

### ❌ CO NIE DZIALA

- Brak finalnego deployu, brak powdrozeniowej walidacji runtime/monitor/smoke.

## A. ROOT CAUSE

Preflight Safety Gate zablokowal pipeline mimo override polityki dirty tree.

## B. ZMIENIONE PLIKI

- `docs/reports/2026-07-08_GWO-IFG-0048_CONTROLLED_PRODUCTION_OVERRIDE.md`

## C. DEPLOY

- Attempt wykonany, zakonczony FAILED na `preflight`.

## D. TESTY

- Brak testow powdrozeniowych (deploy nie doszedl do etapu wykonania).

## E. NASTEPNY KROK

- Uzyskac szczegoly `Safety Gate` blocking item i usunac ten warunek, potem ponowic deploy.
