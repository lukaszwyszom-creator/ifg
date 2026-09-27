---
kind: gwo
project: IFG
workflow: GWO-GUARDIAN_IFG_RELEASE_STATE_CONTRACT
handoff: true
created_at: 2026-07-20T15:25:00Z
---

# GWO-GUARDIAN — IFG Release State Contract

**Data:** 2026-07-20  
**STATUS:** SUCCESS  
**VERDICT:** STANDARD_ACTIVE  

---

## STATUS

| Gate | Wynik |
|------|-------|
| Kanoniczny kontrakt Release State | PASS |
| Aktualizacja `rules_09_reporting.mdc` | PASS |
| Analiza luk workflow (implementacja+build bez decyzji) | PASS |
| Brak zmian deploy / Guardian Deploy / kodu IFG | PASS |
| GDD-0020 | OPEN (osobna oś Capability lifecycle; bez implementacji) |

---

## Opis nowego modelu

Każdy GWO **zmieniający aplikację IFG** musi zakończyć się dokładnie jednym **Release State**:

| Stan | Opis |
|------|------|
| `LOCAL_REVIEW_REQUIRED` | Implementacja + build OK; brak deploy; review lokalny (Mac mini) |
| `READY_FOR_DEPLOY` | Zaakceptowane; gotowe do deploy; jeszcze nie wdrożone |
| `DEPLOYED_TO_DS723` | Na produkcji DS723+ |
| `PRODUCTION_VERIFIED` | Deploy + health/smoke PASS — zamknięcie |

**Zakaz:** kończenie workflow samym `SUCCESS` + build PASS bez Release State.

### Diagram przejść

```text
(implementacja + build PASS)
            │
            ▼
 LOCAL_REVIEW_REQUIRED  ←── domyślnie dla UX/UI
            │
   (akceptacja operatora)
            ▼
    READY_FOR_DEPLOY
            │
       (deploy GWO)
            ▼
    DEPLOYED_TO_DS723
            │
   (weryfikacja produkcji)
            ▼
   PRODUCTION_VERIFIED
```

### Sekcja raportu (obowiązkowa)

```markdown
## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED
```

Dokładnie jedno `[x]`.

UX: dodatkowo URL lokalny + checklista + „następny krok = Deploy GWO”.

---

## Kontrola jakości — luki w dotychczasowym procesie

| Obserwacja | Przykład | Werdykt |
|------------|----------|---------|
| UX + build + STATUS SUCCESS bez ścieżki review/deploy | GWO-IFG-0023, GWO-IFG-0024 | **Niekompletne** wg nowego kontraktu (powinny kończyć się `LOCAL_REVIEW_REQUIRED`) |
| Raporty docs/GDD bez Release State | GDD-0018/0019/0020 registration | Dopuszczalne historycznie; od teraz zalecane `READY_FOR_DEPLOY` dla standardów |
| `rules_09_reporting.mdc` wymagał STATUS A–E, nie Release State | Cursor alwaysApply | **Luka** — naprawiona w tym GWO |
| Mechanizm deploy | bez zmian | Celowo poza zakresem |

**Wniosek:** dotychczasowy standard raportowania **pozwalał** na zamknięcie GWO w stanie pośrednim (zaimplementowane, niewdrożone, nieprzejrzane). Kontrakt zamyka tę lukę na poziomie workflow/raportowania — **bez** zmiany silnika deploy.

---

## Miejsca wymagające zmian (v1)

| Miejsce | Zmiana | Status |
|---------|--------|--------|
| `docs/guardian/core/GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md` | Nowy kanoniczny standard | **DONE** |
| `.cursor/rules/rules_09_reporting.mdc` | Obowiązkowa sekcja RELEASE STATE | **DONE** |
| Nowe raporty GWO-IFG (app) | Wypełnianie sekcji przez agenta/operatora | **Obowiązuje od teraz** |
| Automatyczna walidacja (Guardian CLI / CI) | Opcjonalny follow-up | **Nie w v1** |
| Guardian Deploy / Decision Engine | Brak | Świadomie |

---

## Lista zmodyfikowanych standardów

1. **NOWY:** `docs/guardian/core/GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md`  
2. **ZAKTUALIZOWANY:** `.cursor/rules/rules_09_reporting.mdc`  

Bez zmian: `GUARDIAN_REPORT_METADATA_STANDARD.md` (front matter), `GUARDIAN_RELEASE_WORKFLOW.md` (silnik release IFG), kod deploy.

---

## Ocena kompatybilności wstecznej

| Aspekt | Ocena |
|--------|--------|
| Stare raporty bez sekcji | Zachowane; bez masowej migracji |
| Handoff / journal | Bez zmian schematu |
| Deploy tooling | Bez zmian |
| Nowe GWO IFG app | Breaking **process** (wymaga sekcji) — zamierzone |
| GWO docs-only | Soft requirement (`READY_FOR_DEPLOY` zalecane) |

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

**Uzasadnienie:** GWO wyłącznie standardów (docs + Cursor rule). Brak artefaktu aplikacyjnego do DS723. Stan = standard gotowy do stosowania w kolejnych GWO IFG.

---

## Powiązanie z GDD-0020

GDD-0020 (Capability Lifecycle) pozostaje **OPEN** — osobna oś (stan Capability vs stan wydania pojedynczego GWO). Ten kontrakt **nie** implementuje GDD-0020.

---

🩷 STATUS KOŃCOWY

✅ Kontrakt Active; reguła raportowania zaktualizowana; luki zidentyfikowane  
⚠️ Brak automatycznej egzekucji w CLI/CI (v1 = standard procesowy)  
❌ Brak

A. Root cause — proces pozwalał kończyć GWO na implementacji+build bez decyzji wydania  
B. Zmienione pliki — `GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md`, `rules_09_reporting.mdc`, ten raport  
C. Deploy — nie dotyczy (standard)  
D. Testy — n/a (docs); walidacja treści kontraktu ręczna  
E. Następny krok — kolejne GWO IFG app z obowiązkową sekcją RELEASE STATE; opcjonalnie follow-up: walidator raportów

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md`
- `docs/guardian/core/GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md` (standard kanoniczny)

## Wygenerowane artefakty

- `.cursor/rules/rules_09_reporting.mdc` (zaktualizowany)
- `docs/handoff/HANDOFF-0011.md`
- `docs/handoff/latest.md` → HANDOFF-0011

### Handoff

| Pole | Wartość |
|------|---------|
| Przygotowany? | **TAK** |
| HANDOFF ID | HANDOFF-0011 |
| source_reports | `docs/reports/2026-07-20_GWO-GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md` |
| status | SUCCESS |