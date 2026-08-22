# Guardian IFG Release State Contract

**Version:** 1  
**Status:** Active  
**Workflow:** GWO-GUARDIAN IFG RELEASE STATE CONTRACT  
**Scope:** Standard workflow + raportowania IFG (bez zmian mechanizmu deploy / Guardian Deploy / kodu IFG)

---

## Cel

Uszczelnić zakończenie GWO zmieniających aplikację IFG.

Stan **implementacja + lokalny build PASS** bez dalszej decyzji wydania jest **niepożądany** i uznawany za **workflow niekompletny**.

Każdy taki workflow musi zakończyć się dokładnie jednym aktywnym **Release State**.

---

## Release State (dokładnie jeden aktywny)

| Stan | Znaczenie |
|------|-----------|
| `LOCAL_REVIEW_REQUIRED` | Zmiana wykonana, build OK, **brak deploy**. Operator ma obejrzeć zmianę lokalnie (Mac mini). |
| `READY_FOR_DEPLOY` | Zmiana zaakceptowana, gotowa do wdrożenia, **deploy jeszcze nie wykonany**. |
| `DEPLOYED_TO_DS723` | Deploy wykonany — zmiana na serwerze produkcyjnym DS723+. |
| `PRODUCTION_VERIFIED` | Deploy + weryfikacja produkcji (health PASS) — workflow w pełni zamknięty. |

### Diagram przejść

```text
                    (implementacja + build PASS)
                              │
                              ▼
                   LOCAL_REVIEW_REQUIRED
                              │
                     (akceptacja operatora)
                              ▼
                      READY_FOR_DEPLOY
                              │
                         (deploy GWO)
                              ▼
                      DEPLOYED_TO_DS723
                              │
                    (health / smoke PASS)
                              ▼
                     PRODUCTION_VERIFIED
```

Uwagi:

- Dozwolone jest **pominięcie** `LOCAL_REVIEW_REQUIRED`, gdy zmiana nie wymaga oceny wizualnej/operatorskiej (np. czysty backend) i operator od razu akceptuje deploy → start od `READY_FOR_DEPLOY`.
- **Zabronione** jest kończenie GWO aplikacyjnego na samym `SUCCESS` / „build PASS” bez sekcji Release State.
- Po `DEPLOYED_TO_DS723` brak weryfikacji produkcji = workflow **niezamknięty** (docelowo domknąć do `PRODUCTION_VERIFIED` w tym samym lub follow-up GWO).

---

## Obowiązkowa sekcja raportu IFG

Każdy raport GWO **zmieniający aplikację IFG** (frontend i/lub backend) musi zawierać:

```markdown
## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED
```

**Dokładnie jedno** pole zaznaczone (`[x]`).

Dodatkowo (zalecane):

- jednozdaniowe uzasadnienie wybranego stanu,
- dla `LOCAL_REVIEW_REQUIRED`: URL lokalny, checklista „co sprawdzić”, następny krok = Deploy GWO.

### Workflow UX (dashboard, popup, wykres, layout)

Domyślne zakończenie po implementacji + build:

**`LOCAL_REVIEW_REQUIRED`**

Raport musi wskazać:

1. adres lokalnej aplikacji (np. `http://127.0.0.1:3000/dashboard`),
2. listę rzeczy do sprawdzenia przez operatora,
3. że następnym krokiem jest Deploy GWO (po akceptacji → `READY_FOR_DEPLOY`).

### Workflow produkcyjny (po deploy)

Kolejność docelowa:

`READY_FOR_DEPLOY` → `DEPLOYED_TO_DS723` → `PRODUCTION_VERIFIED`

---

## GWO bez zmiany aplikacji

GWO wyłącznie dokumentacyjne / GDD / standardy (bez artefaktu deployowalnego):

- sekcja **RELEASE STATE** nadal **zalecana** dla spójności,
- typowo: `READY_FOR_DEPLOY` = standard zaakceptowany do stosowania w kolejnych GWO,
- **nie** wymaga się `DEPLOYED_TO_DS723` / `PRODUCTION_VERIFIED`, chyba że GWO obejmowało też deploy dokumentacji na host (rzadkie).

---

## Definicja workflow niekompletnego

Workflow implementacyjny IFG jest **niekompletny**, gdy jednocześnie:

1. zmieniono kod aplikacji,
2. raport ma `STATUS: SUCCESS` (lub równoważny),
3. build lokalny PASS,
4. **brak** jednoznacznie zaznaczonego Release State  
   **lub** stan domyślnie interpretowany jako „gotowe” bez review/deploy.

Przykłady historyczne (przed kontraktem): GWO-IFG-0023, GWO-IFG-0024 — UX + build, bez obowiązkowego `LOCAL_REVIEW_REQUIRED` / ścieżki deploy.

---

## Miejsca standardu (do utrzymania)

| Artefakt | Rola |
|----------|------|
| `docs/guardian/core/GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md` | Kanoniczny kontrakt (ten dokument) |
| `.cursor/rules/rules_09_reporting.mdc` | Obowiązkowa sekcja w raportach Cursor |
| Raporty `docs/reports/*GWO-IFG*` | Każdy nowy raport aplikacyjny |

**Poza zakresem kontraktu v1:** zmiana `guardian ifg deploy`, Decision Engine, kod IFG, automatyczna bramka CI blokująca brak Release State (możliwy follow-up GWO).

---

## Kompatybilność wsteczna

| Obszar | Zasada |
|--------|--------|
| Stare raporty bez sekcji | Ważne historycznie; **nie wymaga się** masowej edycji |
| Nowe GWO IFG (app) | Sekcja Release State **obowiązkowa** od daty Active |
| Handoff / metadata YAML | Bez zmian schematu; Release State żyje w body raportu |
| Deploy mechanizm | Bez zmian |

---

## Powiązania

- **GDD-0020** Capability Lifecycle — Release State opisuje stan *wydania zmiany*; Capability lifecycle opisuje stan *całej możliwości* (osobna oś).
- **GDD-0018 / GDD-0019** — przyszła warstwa danych dashboardu podlega temu kontraktowi przy GWO implementacyjnym.
