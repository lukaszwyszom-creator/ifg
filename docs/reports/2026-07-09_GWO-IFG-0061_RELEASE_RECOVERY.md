# GWO-IFG-0061 — Release Recovery

🩷 STATUS KOŃCOWY

✅ Co działa
- Uruchomiono release gate na rzeczywistym workflow Guardiana:
  - `PYTHONPATH=scripts python3 -m ifg_guardian.cli ifg deploy run --dry-run --markdown`
- Zidentyfikowano wszystkie aktywne blockery na podstawie outputu Guardiana.
- Potwierdzono kontekst repo:
  - branch: `production`
  - working tree: bardzo duża liczba zmian tracked + untracked.

⚠️ Znane problemy
- Release Gate pozostaje w stanie `PRODUCTION_BLOCKED` z ryzykiem `CRITICAL`.

❌ Co nie działa
- Nie udało się osiągnąć `PRODUCTION_READY` bez decyzji użytkownika dotyczącej sposobu obsługi bieżącego, mieszanego working tree na branchu produkcyjnym.

## ETAP 1 — ANALIZA RELEASE GATE

Źródło prawdy:
- workflow Guardian: `ifg.deploy.run` (dry-run)
- decyzja polityki release: `PRODUCTION_BLOCKED (34/100)`

Wykryte blockery (Guardian):
1. `Release decision is PRODUCTION_BLOCKED`
2. `Policy blocker: [backend] backend changes: 7 backend/alembic change(s)`
3. `Policy blocker: [backend] build required: rebuild api/worker required before deploy`
4. `Policy rule triggered: dirty_working_tree_blocks_production`
5. `Policy rule triggered: tests_must_pass`
6. `Production deployment blocked. Working tree contains uncommitted changes`

## ETAP 2 — ANALIZA USUNIĘCIA BLOKERÓW

### Blocker 1 — `PRODUCTION_BLOCKED`
- Źródło: Release Engine (`ifg.release.evaluate` zależne od doctor/policy).
- Przyczyna: skumulowanie blockerów 2-6.
- Sposób usunięcia: usunąć wszystkie pozostałe blockery.
- Auto-naprawa: pośrednio (nie samodzielny blocker).
- Wymaga decyzji użytkownika: tak (bo zależy od strategii uporządkowania zmian produkcyjnych).

### Blocker 2 — `backend changes: 7 backend/alembic change(s)`
- Źródło: policy gate backend.
- Przyczyna: obecne zmiany backend/alembic w working tree.
- Sposób usunięcia: świadoma decyzja co zrobić z tym zestawem zmian (commit/split/odłożenie).
- Auto-naprawa: nie.
- Wymaga decyzji użytkownika: tak.

### Blocker 3 — `build required: rebuild api/worker required before deploy`
- Źródło: plan deploy.
- Przyczyna: zmiany backend wymagające rebuild obrazów.
- Sposób usunięcia: uruchomić wymagany build pipeline po odblokowaniu polityk.
- Auto-naprawa: technicznie tak, ale nie usuwa blockerów 4-6.
- Wymaga decyzji użytkownika: tak (najpierw strategia dla zmian i test gate).

### Blocker 4 — `dirty_working_tree_blocks_production`
- Źródło: policy rule.
- Przyczyna: duża liczba lokalnych zmian (tracked/untracked) na `production`.
- Sposób usunięcia: doprowadzić working tree do stanu zgodnego z polityką release.
- Auto-naprawa: nie (bezpieczne działania wymagają decyzji właściciela zmian).
- Wymaga decyzji użytkownika: tak.

### Blocker 5 — `tests_must_pass`
- Źródło: policy rule test gate.
- Przyczyna: gate testowy nie został potwierdzony jako pass przez workflow evaluate.
- Sposób usunięcia: uruchomić i domknąć wymagany zestaw testów zgodny z polityką release.
- Auto-naprawa: częściowo (uruchomienie tak, decyzja o zakresie i naprawach nie).
- Wymaga decyzji użytkownika: tak (zakres testów i priorytet napraw).

### Blocker 6 — `uncommitted changes`
- Źródło: policy rule.
- Przyczyna: repo nie jest w stanie clean.
- Sposób usunięcia: decyzja co wchodzi do releasu i uporządkowanie stanu repo.
- Auto-naprawa: nie.
- Wymaga decyzji użytkownika: tak.

## ETAP 3 — PONOWNA WALIDACJA

Ponowna walidacja po analizie:
- uruchomiono ten sam release gate ponownie,
- wynik pozostaje: `PRODUCTION_BLOCKED`, `CRITICAL`, `6 blocker(s)`.

## ETAP 4 — KOŃCOWA OCENA BLOKERÓW

| Blocker | Priorytet | Auto-naprawa | Wymaga decyzji użytkownika | Rekomendowany następny krok |
|---|---|---|---|---|
| PRODUCTION_BLOCKED (agregat) | HIGH | Nie bezpośrednio | Tak | Rozwiązać blockery 2-6 |
| backend changes gate | HIGH | Nie | Tak | Ustalić zakres zmian backend do releasu |
| build required api/worker | MEDIUM | Częściowo | Tak | Wykonać build po odblokowaniu polityk |
| dirty_working_tree_blocks_production | HIGH | Nie | Tak | Uporządkować working tree zgodnie z polityką |
| tests_must_pass | HIGH | Częściowo | Tak | Uzgodnić i zamknąć wymagany gate testowy |
| uncommitted changes | HIGH | Nie | Tak | Domknąć stan commitów/untracked dla produkcji |

## ETAP 5 — PODSUMOWANIE

**PRODUCTION_BLOCKED**

Pełna lista pozostałych blockerów:
- `Release decision is PRODUCTION_BLOCKED`
- `[backend] backend changes: 7 backend/alembic change(s)`
- `[backend] build required: rebuild api/worker required before deploy`
- `dirty_working_tree_blocks_production`
- `tests_must_pass`
- `working tree contains uncommitted changes`

A. Root cause
- Polityki Guardiana poprawnie blokują release z brancha `production` przy dużej liczbie nieuporządkowanych zmian i niezamkniętym gate testowym.

B. Zmienione pliki
- `docs/reports/2026-07-09_GWO-IFG-0061_RELEASE_RECOVERY.md`

C. Deploy
- Nie wykonywano deployu (zgodnie z wymaganiem).

D. Testy / walidacje
- `PYTHONPATH=scripts python3 -m ifg_guardian.cli ifg deploy run --dry-run --markdown` (2x) -> `PRODUCTION_BLOCKED`
- `git branch --show-current && git status -sb` -> potwierdzony dirty working tree

E. Następny krok
- Wymagane decyzje użytkownika:
  1. Jaką strategię zastosować dla obecnych zmian na `production` (co ma wejść do release)?
  2. Jak domknąć gate `tests_must_pass` (zakres testów i akceptowalne kryterium pass)?
  3. Czy i kiedy wykonywać wymagany rebuild `api/worker` po uporządkowaniu repo?

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-09_GWO-IFG-0061_RELEASE_RECOVERY.md`
