# GWO-GUARDIAN-0075A — HANDOFF FORMAT V1.0 FINALIZATION

**Data:** 2026-07-11  
**Branch:** production  
**Bazuje na:** GWO-GUARDIAN-0075 (Workflow Artifact Engine)  
**Werdykt:** IMPLEMENTED

---

## 1. Porównanie starego i nowego formatu

| Aspekt | Format 0075 (legacy) | Format v1.0 (kanoniczny) |
|--------|----------------------|---------------------------|
| Lokalizacja pliku | `docs/handoff/handoff-0001.md` | `docs/handoff/HANDOFF-0001.md` |
| Równoległy output | `reports/CHATGPT_HANDOFF_YYYY-MM-DD.md` | **brak** — tylko journal |
| YAML `handoff_id` | `0001` (numeryczny) | `HANDOFF-0001` (pełny ref) |
| `previous_handoff` / `parent_handoff` | numery lub null | pełne `HANDOFF-XXXX` lub null |
| Pola schema | brak | `handoff_schema: 1`, `cursor_format_version: 1` |
| `generated_reports` | brak | lista wszystkich artefaktów workflow |
| Nagłówek po YAML | `# CHATGPT HANDOFF YYYY-MM-DD` | `# HANDOFF-XXXX` + blok Projekt/Workflow/Typ/Status/Data |
| Stopka | brak | `END OF HANDOFF` + `HANDOFF-XXXX` (bez tekstu po) |
| `latest.md` | kopia ostatniego handoff | **byte-identyczna** kopia `HANDOFF-XXXX.md` |

Przykład YAML v1.0:

```yaml
---
kind: handoff
handoff_schema: 1
handoff_id: HANDOFF-0001
previous_handoff: null
parent_handoff: null
project: IFG
workflow: GWO-IFG-9001
workflow_type: IMPLEMENTATION
status: SUCCESS
created_at: 2026-07-11T12:24:08Z
cursor_format_version: 1
source_reports:
  - docs/reports/2026-07-11_GWO-IFG-9001_A.md
generated_reports:
  - docs/handoff/HANDOFF-0001.md
  - docs/handoff/latest.md
  - docs/reports/2026-07-11_GWO-IFG-9001_A.md
---
```

`cursor_format_version` dotyczy wyłącznie artefaktu Workflow Engine — nie wersji Cursor IDE.

---

## 2. Zmienione moduły

| Plik | Zmiana |
|------|--------|
| `scripts/ifg_guardian/core/handoff_journal/models.py` | `HANDOFF-XXXX` refs, `handoff_schema`, `cursor_format_version`, `generated_reports`, title block, footer `END OF HANDOFF` |
| `scripts/ifg_guardian/core/handoff_journal/store.py` | Ścieżki `HANDOFF-XXXX.md` |
| `scripts/ifg_guardian/core/handoff_journal/integrity.py` | Walidacja v1 + `LEGACY_FORMAT` notices; legacy filename vs v1 rozróżnienie po `path.name` |
| `scripts/ifg_guardian/core/handoff_journal/service.py` | Normalizacja metadata przy publish (`generated_reports`) |
| `scripts/ifg_guardian/modules/ifg_handoff.py` | Usunięto `reports/CHATGPT_HANDOFF_*`; publish tylko do journal; pusty selection → komunikat, brak zapisu |
| `scripts/ifg_guardian/modules/handoff_journal.py` | Import `ROOT`; prefiksy `[HANDOFF-XXXX]` w validate/doctor |
| `tests/unit/test_guardian_handoff_journal.py` | Testy v1.0 + legacy + CHATGPT detection |
| `tests/unit/test_guardian_ifg_handoff.py` | Ścieżki journal zamiast `reports/CHATGPT_HANDOFF_*` |
| `tests/unit/test_guardian_handoff_clipboard.py` | Inicjalizacja journal w testach clipboard |

**Bez zmian:** runtime IFG, deploy DS723+, rdzeń Workflow Engine (kroki publish, gate, index lock).

---

## 3. Migracja

- Istniejące pliki `handoff-NNNN.md` i `reports/CHATGPT_HANDOFF_*.md` **nie są automatycznie konwertowane**.
- Nowy format obowiązuje wyłącznie dla handoff generowanych po wdrożeniu 0075A.
- Operator może ręcznie zarchiwizować stare `reports/CHATGPT_HANDOFF_*` — nie są już produkowane przez `guardian ifg handoff latest`.

---

## 4. Zgodność wsteczna

| Zachowanie | Status |
|------------|--------|
| Odczyt legacy `handoff-NNNN.md` | ✅ skanowany przez journal |
| Walidacja legacy | ✅ `LEGACY_FORMAT` jako **notice**, walidacja nie przerywa (`valid=True`) |
| CHATGPT header w legacy | ✅ notice `LEGACY_CHATGPT_HEADER` |
| CHATGPT header w v1 `HANDOFF-XXXX.md` | ❌ błąd walidacji |
| Stare `reports/CHATGPT_HANDOFF_*` w repo | pozostają jako artefakty historyczne |

---

## 5. Testy

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/unit/test_guardian_handoff_journal.py \
  tests/unit/test_guardian_ifg_handoff.py \
  tests/unit/test_guardian_handoff_clipboard.py -q
# 31 passed
```

| Scenariusz ETAP 10 | Status |
|--------------------|--------|
| `HANDOFF-XXXX` filename + YAML | ✅ |
| `previous_handoff` pełny ref | ✅ |
| `parent_handoff` pełny ref | ✅ |
| `generated_reports` | ✅ |
| `cursor_format_version` | ✅ |
| `handoff_schema` | ✅ |
| `latest.md` byte-identical | ✅ |
| legacy compatibility (`LEGACY_FORMAT`) | ✅ |
| `END OF HANDOFF` footer | ✅ |
| wykrywanie `CHATGPT HANDOFF` w v1 | ✅ |

---

## 6. Walidacja

```bash
python3 scripts/guardian.py handoff validate
# Handoff journal valid.
```

Rozszerzone sprawdzenia `guardian handoff validate`:

- `handoff_schema` == 1
- `cursor_format_version` == 1
- pełne identyfikatory `HANDOFF-XXXX` w YAML i nazwie pliku
- `parent_handoff` / `previous_handoff` (pełne refs lub null)
- `generated_reports` niepuste dla v1
- stopka `END OF HANDOFF` + ref bez trailing content
- `latest.md` == ostatni `HANDOFF-XXXX.md` (bajtowo)
- brak `# CHATGPT HANDOFF` w plikach v1
- legacy: notice `LEGACY_FORMAT`, bez fail

---

## 7. Ograniczenia

- `docs/handoff/latest.md` w repo jest pusty do czasu pierwszego handoff v1.0 po deploy zmian lokalnych.
- Historyczne `reports/CHATGPT_HANDOFF_*.md` nie zostały usunięte z repozytorium (świadoma decyzja: brak auto-migracji/usuwania).
- Pamięć wysłanych raportów (`.state/handoff.json`) bez zmian — nadal steruje kolejnością `ifg handoff latest`.
- `cursor_format_version` nie wersjonuje treści body handoff — tylko envelope YAML/title/footer.

---

## Decyzje dla ChatGPT

1. Czy historyczne `reports/CHATGPT_HANDOFF_*.md` przenieść do `docs/handoff/archive/` w osobnym GWO housekeeping, czy pozostawić w `reports/` jako read-only legacy?
2. Czy przy pierwszym handoff v1.0 na produkcji ustawić `previous_handoff: null` mimo istnienia legacy `handoff-0001.md`, czy wymagać ręcznego wpisu łańcucha?

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Kanoniczny format HANDOFF v1.0 w `docs/handoff/HANDOFF-XXXX.md`
- `latest.md` jako identyczna kopia ostatniego handoff
- `generated_reports` + pełne refs `HANDOFF-XXXX`
- Walidacja v1 + legacy notices
- 31 testów jednostkowych PASS
- `guardian handoff validate` → OK

⚠️ Znane problemy
- Stare pliki `reports/CHATGPT_HANDOFF_*` nadal leżą w repo (nie generowane przez nowy workflow)
- `docs/handoff/latest.md` pusty do pierwszego publish v1

❌ Co nie działa
- Brak — zakres 0075A zamknięty bez zmian runtime IFG

**A. Root cause**  
0075 wprowadził journal, ale zachował format przejściowy (`handoff-NNNN`, `CHATGPT HANDOFF`, równoległy `reports/`). 0075A stabilizuje jeden kanoniczny envelope bez przebudowy silnika kroków.

**B. Zmienione pliki**  
Patrz sekcja 2.

**C. Deploy**  
Nie wykonano (zakaz DS723+ / runtime IFG).

**D. Testy**  
`31 passed` — patrz sekcja 5.

**E. Następny krok**  
Uruchomić `guardian ifg handoff latest` po merge — pierwszy handoff v1.0 wypełni `HANDOFF-0001.md` i `latest.md`.

---

## WYGENEROWANE RAPORTY

- `docs/reports/2026-07-11_GWO-GUARDIAN-0075A_HANDOFF_FORMAT_V1.md` (ten dokument)

## WYGENEROWANE HANDOFFY

- Brak nowego handoff v1.0 w tej sesji (zmiana tylko generatora/walidatora; `docs/handoff/latest.md` pusty).

## KROKI DLA OPERATORA

1. Merge zmian 0075A na `production`.
2. `python3 scripts/guardian.py handoff validate` — oczekiwane: `Handoff journal valid.`
3. `python3 scripts/guardian.py ifg handoff latest` — pierwszy handoff v1.0 → `docs/handoff/HANDOFF-0001.md` + `latest.md`.
4. Opcjonalnie: ręczna archiwizacja starych `reports/CHATGPT_HANDOFF_*` (po decyzji ChatGPT).

## ZAKAZY (przestrzegane)

- ❌ Zmiana runtime IFG
- ❌ Deploy DS723+
- ❌ Przebudowa Workflow Engine poza formatem
- ❌ Auto-migracja starych handoffów
- ❌ Generowanie `reports/CHATGPT_HANDOFF_*` dla nowych handoff
- ❌ Dwa równoległe formaty dla nowych handoff
- ❌ Tekst po `END OF HANDOFF`
