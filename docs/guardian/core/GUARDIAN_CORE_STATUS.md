# Guardian Core — status w repo IFG

**Status:** FROZEN (IFG scope)  
**Wersja:** 1.0  
**Data zamrożenia zakresu IFG:** 2026-07-11 (GWO-GUARDIAN-0074A)  
**Powiązane:** [GUARDIAN_VISION.md](./GUARDIAN_VISION.md), [GWO-GUARDIAN-0074](../reports/2026-07-11_GWO-GUARDIAN-0074_GDD_REGISTRY_INTEGRITY.md)

---

## Status globalny

Guardian Core osiągnął dojrzałość operacyjną.  
Zmiany Core wymagają ADR w dedykowanym repo Guardian (patrz `guardian/ADR/ADR-0001-guardian-core-v1-freeze.md`).

Przyszły rozwój Guardiana ma wynikać z realnych projektów (IFG, PSAG, …), nie ze spekulacyjnej architektury.

---

## Granica architektoniczna IFG / Guardian (GWO-GUARDIAN-0074A)

### Co pozostaje w tym repo

1. **`ifg_guardian`** jest produkcyjną implementacją Guardiana obsługującą IFG.
2. **IFG nie jest poligonem** do budowy ogólnej architektury Guardian Core.
3. W repo IFG **dozwolone** są wyłącznie:
   - poprawki Guardiana wymagane do **utrzymania IFG**,
   - nowe workflow wynikające z **konkretnej operacji administracyjnej IFG**,
   - integracje biznesowe IFG korzystające z **istniejących** mechanizmów Guardiana.

### Czego nie rozpoczynać w repo IFG

Bez jawnego GWO projektu **Guardian** (osobny projekt, nie IFG) **nie wolno** rozpoczynać:

- ogólnego Event Bus,
- Runtime State Engine,
- uniwersalnego Notification Engine,
- Conductora,
- multi-project registry,
- wydzielenia wspólnego Guardian Core.

Decyzje odłożone do przyszłego Guardian Core pozostają w GDD jako **OPEN** (np. GDD-0013, GDD-0014, GDD-0015).

### `guardian_platform`

- **Zamrożony** — bez dalszego rozwoju do czasu osobnego GWO migracyjnego.
- **Nie usuwać** i **nie refaktoryzować** w ramach bieżących GWO IFG.
- **Nie przenosić** kodu między `ifg_guardian` a `guardian_platform` bez dedykowanego GWO migracyjnego.

### Zasada guard rail (prompty / workflow)

> **Nie rozwijaj Guardian Core w repo IFG bez jawnego GWO projektu Guardian.**

Zapis operacyjny dla Cursor: `.cursor/rules/rules_10_guardian.mdc` (sekcja *Zakres rozwoju*).

---

## Następny planowany zakres IFG (nie Guardian Core)

**Temat:** Powiadomienia o nowych fakturach (zakres roboczy — bez implementacji w GWO-0074A).

- wykrywanie nowych faktur zakupowych pobranych z KSeF,
- wykrywanie nowych faktur sprzedażowych przyjętych przez KSeF (jeśli potrzebne),
- deduplikacja powiadomień,
- powiadomienie dopiero po trwałym zapisaniu faktury w IFG,
- brak sekretów w repo,
- wykorzystanie istniejącego monitora/schedulera tam, gdzie uzasadnione,
- **bez** budowy pełnego uniwersalnego Notification Engine w repo IFG.

Realizacja jako osobne GWO IFG — nie jako rozwój Guardian Core.

---

## Zamknięte GWO Guardian w IFG

| GWO | Status | Commit |
|-----|--------|--------|
| GWO-GUARDIAN-0074 | **IMPLEMENTED / CLOSED** | `d9cba7a` |
| GWO-GUARDIAN-0074A | **CLOSED_AND_FROZEN** | (ten cykl) |
