# CHATGPT HANDOFF 2026-07-09

## Streszczenie

- Liczba znalezionych raportów: 1
- Zakres GWO: brak jawnych identyfikatorów GWO
- Preferencja raportów z dzisiaj: TAK
- Scalono pliki:
  - `docs/reports/2026-07-09_GUARDIAN_REPOSITORY_INTELLIGENCE.md`

## Co wymaga decyzji ChatGPT

Brak decyzji wymagających oceny ChatGPT.

## Raport 1: `docs/reports/2026-07-09_GUARDIAN_REPOSITORY_INTELLIGENCE.md`

# GUARDIAN CORE — Guardian Repository Intelligence (GRI)

🩷 STATUS KOŃCOWY

✅ Co działa
- Zaprojektowano architekturę warstwy **Guardian Repository Intelligence (GRI)** jako wspólnego substrate analitycznego.
- Rozdzielono odpowiedzialności: GRI (analiza/semantyka) vs Policy Engine (decyzja).
- Zdefiniowano model danych, przepływ informacji i integrację z:
  - Release Gate,
  - Deploy,
  - Cleanup,
  - Doctor,
  - GDD,
  - PSAG.
- Utworzono formalny ADR: `Architecture/ADR/ADR-0065_GUARDIAN_REPOSITORY_INTELLIGENCE.md`.

⚠️ Znane problemy
- Brak wspólnej warstwy GRI powoduje dziś duplikację heurystyk i file-centric output w wielu capability.

❌ Co nie działa
- Guardian nadal nie ma natywnej odpowiedzi semantycznej „co dokładnie jest w repo i jak zmiany są logicznie powiązane” bez dodatkowej, ręcznej analizy.

## 1. Problem

Aktualny Guardian odpowiada na pytanie:
- „Czy release jest możliwy?”

ale nie odpowiada wystarczająco dobrze na:
- „Jakie logiczne grupy zmian są w repo, jak się wiążą i co z nich realnie blokuje release?”

Konsekwencja:
- output bywa plikocentryczny (`N changed files`, `dirty tree`) zamiast semantyczny (`Monitor KSeF`, `Guardian Core`, `artefakty`, `dokumentacja`, `test gate`).

## 2. Rozważane warianty

### Wariant A — Ulepszać każdą capability osobno
- plus: niski koszt startu,
- minus: duplikacje, niespójność, brak wspólnego modelu.

### Wariant B — Wspólna warstwa GRI (wybrany)
- plus: jednolita semantyka i reużywalny model,
- minus: potrzeba kontraktów i migracji capability.

### Wariant C — Od razu trwała baza wiedzy GRI
- plus: historia/trendy od początku,
- minus: wysoki koszt i złożoność na starcie.

## 3. Wybrana architektura GRI

GRI jako warstwa read-only:
- analizuje stan repo i workflow outputs,
- klasyfikuje zmiany do modułów/capabilities,
- redukuje blockery do przyczyn pierwotnych,
- buduje graf wpływu i zależności,
- generuje plan działań do stanu docelowego (`PRODUCTION_READY`).

### Kluczowe komponenty
1. `Repository Snapshot Adapter`
2. `Change Classifier Engine`
3. `Dependency & Impact Graph`
4. `Blocker Reducer` (primary vs derivative)
5. `Recommendation Planner`
6. `Consumer Facades` dla Release/Deploy/Cleanup/Doctor/GDD/PSAG

## 4. Dane utrzymywane przez GRI

Minimalny model:
- `RepositorySnapshot` (branch/sync/dirty/changes),
- `ChangeItem` (path -> module/capability/category/release_scope),
- `ChangeGroup` (np. Monitor KSeF, Guardian Core, Docs, Artefakty),
- `Blocker` (source/severity/primary/depends_on/auto_fixable/requires_decision),
- `ImpactRelation` (graph module->module),
- `TestGateState` (required/discovery/pass/fail),
- `GRIRecommendationStep` (krok + oczekiwany rezultat + co odblokowuje).

## 5. Przepływ informacji

1. Git + workflow outputs -> snapshot.
2. Klasyfikacja zmian -> change items/groups.
3. Parsowanie blockerów policy -> raw blocker set.
4. Redukcja agregatów -> blockery pierwotne.
5. Graf wpływu -> zależności modułów/capabilities.
6. Planner -> uporządkowane kroki.
7. Capability facade -> format docelowy (terminal/markdown/json).

## 6. Integracja capability

### Release Gate
- raportuje primary blockers i ich zależności,
- pokazuje logiczne grupy working tree zamiast samej liczby plików.

### Deploy
- konsumuje GRI preflight scope:
  - co jest in-scope do deployu,
  - co jest noise/out-of-scope.

### Cleanup
- grupuje pliki wg semantyki (artefakty/reporty/cache/docs), nie tylko count.

### Doctor
- mapuje lokalne problemy narzędziowe na konkretne gate’y i wpływ na release.

### GDD
- wiąże deferred decisions z modułami dotkniętymi bieżącym zakresem zmian.

### PSAG
- używa tych samych danych klasyfikacji i grafu do oceny typu repo/capability.

## 7. Przykładowy output CLI (docelowy)

```text
guardian release advise

Decision: PRODUCTION_BLOCKED
Primary blockers: 3
  1) Dirty working tree (scope conflict)
  2) Tests gate (discovery/tooling)
  3) Backend rebuild prerequisite

Working tree groups:
  - Monitor KSeF: INCLUDE
  - Guardian Core: REVIEW
  - Dokumentacja: SPLIT/DEFER
  - Artefakty lokalne: EXCLUDE

Plan:
  K1 scope freeze
  K2 clean working tree
  K3 tests gate pass
  K4 backend rebuild
  K5 release evaluate -> PRODUCTION_READY
```

## 8. Plan migracji

1. Zdefiniować słownik modułów/capabilities i kategorie zmian.
2. Wdrożyć MVP GRI read-only dla Release Advisor.
3. Podpiąć Release Evaluate/Deploy/Doctor do GRI jako consumerów.
4. Rozszerzyć na Cleanup i GDD linking.
5. Dodać adapter PSAG.
6. Opcjonalnie: później snapshot history store (trend analysis).

A. Root cause
- Brak wspólnej warstwy semantycznej repo prowadzi do rozproszonej, capability-specific analizy i słabszej explainability decyzji release.

B. Zmienione pliki
- `Architecture/ADR/ADR-0065_GUARDIAN_REPOSITORY_INTELLIGENCE.md`
- `docs/reports/2026-07-09_GUARDIAN_REPOSITORY_INTELLIGENCE.md`

C. Deploy
- Nie wykonywano deployu.

D. Testy
- Zadanie projektowe/ADR, bez implementacji kodu.

E. Następny krok
- Przełożyć ADR na backlog wdrożenia: MVP `guardian release advise` jako pierwszy consumer GRI (read-only).

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `Architecture/ADR/ADR-0065_GUARDIAN_REPOSITORY_INTELLIGENCE.md`
- `docs/reports/2026-07-09_GUARDIAN_REPOSITORY_INTELLIGENCE.md`

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/reports/CHATGPT_HANDOFF_2026-07-09.md`
- `docs/reports/2026-07-09_GUARDIAN_REPOSITORY_INTELLIGENCE.md`
