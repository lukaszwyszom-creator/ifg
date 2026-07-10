# GWO-GUARDIAN-GDD_CORE — Guardian Deferred Decisions (GDD)

**Data:** 2026-07-09  
**Status:** DONE

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Dodano capability **Guardian Deferred Decisions (GDD)** w Guardian Core.
- Trwały rejestr: `docs/guardian/deferred_decisions.json` (JSON, wersjonowany w git).
- Model danych obejmuje wymagane pola: ID, projekt, moduł, typ, priorytet, status, powód odłożenia, opis, kiedy wrócić, źródło, daty utworzenia/zamknięcia.
- CLI:
  - `guardian deferred add`
  - `guardian deferred list`
  - `guardian deferred show <ID>`
  - `guardian deferred done <ID>`
  - `guardian deferred cancel <ID>`
  - `guardian deferred review`
- Review generuje raport otwartych GDD: `docs/guardian/GDD_REVIEW_YYYY-MM-DD.md`.
- Dokumentacja kanoniczna: `docs/guardian/core/GUARDIAN_DEFERRED_DECISIONS.md`.
- Migracja: utworzono 9 początkowych wpisów GDD-0001..GDD-0009 na podstawie review GWO-0053..0059 i analizy handoff.

⚠️ ZNANE PROBLEMY
- Komenda `guardian` w PATH wymaga wrappera repo (`PYTHONPATH=scripts python3 -m ifg_guardian.cli` lub `python3 scripts/guardian.py`) — zgodnie z istniejącym stanem CLI Guardiana.

❌ CO NIE DZIAŁA
- Brak.

## FORMAT PRZECHOWYWANIA (UZASADNIENIE)

**Wybrano:** JSON w `docs/guardian/deferred_decisions.json`

| Kryterium | JSON (wybrane) | Markdown | YAML | `.state/*.json` |
|-----------|----------------|----------|------|-----------------|
| CRUD z CLI | ✅ | ❌ | ⚠️ | ✅ |
| Diff w git | ✅ | ✅ | ✅ | ⚠️ |
| Filtrowanie po statusie/priorytecie | ✅ | ❌ | ✅ | ✅ |
| Czytelność bez narzędzi | ⚠️ | ✅ | ✅ | ⚠️ |
| Trwałość między sesjami | ✅ (w repo) | ✅ | ✅ | ❌ (runtime) |

JSON w `docs/guardian/` łączy trwałość (git), prostotę operacji CLI i spójność z ekosystemem Guardiana. Markdown jest generowany na żądanie przez `deferred review`.

## ARCHITEKTURA

- `scripts/ifg_guardian/core/deferred_decisions/models.py` — typy, enums, serializacja
- `scripts/ifg_guardian/core/deferred_decisions/store.py` — load/save JSON
- `scripts/ifg_guardian/core/deferred_decisions/service.py` — logika CRUD + review markdown
- `scripts/ifg_guardian/modules/deferred_decisions.py` — runnery CLI
- `scripts/ifg_guardian/cli.py` — subparser `deferred`

## MIGRACJA (GDD-0001..0009)

| ID | Moduł | Typ | Priorytet | Źródło |
|----|-------|-----|-----------|--------|
| GDD-0001 | Guardian Handoff | Process | High | GWO-0059 + handoff analysis |
| GDD-0002 | KSeF Monitor | Refactor | Medium | GWO-0059 |
| GDD-0003 | KSeF Monitor | Performance | Low | GWO-0056/0057/0059 |
| GDD-0004 | KSeF Monitor | UX | Low | GWO-0057 |
| GDD-0005 | KSeF Monitor | Technical Debt | Medium | GWO-0058 |
| GDD-0006 | Frontend | Performance | Medium | GWO-0059 (bundle ~898 kB) |
| GDD-0007 | KSeF Monitor / API | Architecture | High | GWO-0053 debt standard |
| GDD-0008 | KSeF Monitor | UX | Low | GWO-0054A |
| GDD-0009 | Guardian Reporting | Process | Medium | GWO-GUARDIAN-STANDARD |

## A. ROOT CAUSE

Brak centralnego rejestru odłożonych decyzji powodował, że obserwacje z Debt raportów GWO i review (np. handoff parser, backend grouping) były rozproszone w plikach markdown i mogły zostać pominięte przy planowaniu kolejnych iteracji.

## B. ZMIENIONE PLIKI

- `scripts/ifg_guardian/core/deferred_decisions/__init__.py` (nowy)
- `scripts/ifg_guardian/core/deferred_decisions/models.py` (nowy)
- `scripts/ifg_guardian/core/deferred_decisions/store.py` (nowy)
- `scripts/ifg_guardian/core/deferred_decisions/service.py` (nowy)
- `scripts/ifg_guardian/modules/deferred_decisions.py` (nowy)
- `scripts/ifg_guardian/cli.py`
- `docs/guardian/deferred_decisions.json` (nowy — rejestr + migracja)
- `docs/guardian/core/GUARDIAN_DEFERRED_DECISIONS.md` (nowy)
- `tests/unit/test_guardian_deferred_decisions.py` (nowy)
- `docs/guardian/GDD_REVIEW_2026-07-09.md` (wygenerowany przez review)

## C. DEPLOY

Nie wykonywano deployu (zgodnie z wymaganiem).

## D. TESTY

Uruchomiono:

```bash
PYTHONPATH=scripts python3 -m unittest tests.unit.test_guardian_deferred_decisions -v
```

Wynik: **10/10 OK**

Smoke CLI:

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli deferred list --project IFG
PYTHONPATH=scripts python3 -m ifg_guardian.cli deferred show GDD-0001
PYTHONPATH=scripts python3 -m ifg_guardian.cli deferred review --project IFG
```

Wynik: **PASS** (9 otwartych wpisów IFG, raport review zapisany)

## E. NASTĘPNY KROK

- Używać `guardian deferred review` przed planowaniem kolejnego release.
- Promować istotne wpisy Debt z raportów GWO do GDD (GDD-0009).
- Osobny GWO na naprawę parsera handoff (GDD-0001).

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-09_GWO-GUARDIAN-GDD_CORE.md`
- `docs/guardian/GDD_REVIEW_2026-07-09.md`
