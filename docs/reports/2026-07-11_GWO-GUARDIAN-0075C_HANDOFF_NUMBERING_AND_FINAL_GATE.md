# GWO-GUARDIAN-0075C — HANDOFF V1.0: NUMERACJA, SEMANTYKA ARTEFAKTÓW I FINALNY GATE

**Data:** 2026-07-11  
**Branch:** production  
**Werdykt:** IMPLEMENTED

---

## 1. Stan początkowy katalogu handoff

```
docs/handoff/
├── index.json      # next_handoff_id: 1, latest_handoff_id: null, count: 0
├── latest.md       # pusty
└── (brak HANDOFF-*.md)
```

**HEAD przed zmianą:** `6be84ac` (GWO-GUARDIAN-0075)  
**Zmiany 0075A/0075B:** niezacommitowane lokalnie w working tree.

---

## 2. Index przed zmianą

```json
{
  "schema_version": 1,
  "next_handoff_id": 1,
  "latest_handoff_id": null,
  "count": 0
}
```

---

## 3. Potwierdzony root cause ciągłego HANDOFF-0001

| Przyczyna | Dowód |
|-----------|-------|
| **Index nigdy nie był inkrementowany** | `count: 0`, brak plików `HANDOFF-*.md` w kanonicznym journal |
| **0075A/0075B nie były na production** | HEAD = 0075; format v1 tylko w working tree |
| **Każdy test/demo startuje od świeżego index** | `_init_journal()` ustawia `next_handoff_id: 1` w tmp_path |
| **Brak udanego publish do repo** | `guardian ifg handoff latest` nie wykonany na realnym journal po 0075B |
| **Lock na globalnym ROOT** | `HandoffJournalLock` używał `ROOT/.state/` zamiast `root` serwisu (naprawione) |

**Nie było** hardcoded `HANDOFF-0001` w generatorze produkcyjnym — numer pochodził z index, który pozostawał na 1.

---

## 4. Poprawiony model alokacji ID

- Jedyny source of truth: `docs/handoff/index.json`
- ID alokowane wyłącznie w `HandoffJournalService.publish()` pod lockiem
- `_build_handoff_metadata()` nie przyjmuje numeru — placeholder `handoff_id: 0`
- Index aktualizowany **po** walidacji projected state, nie przed clipboard/validate
- Konflikt: `target.exists()` → `HANDOFF_ID_CONFLICT`, FAILED, index bez zmian

---

## 5. Transakcyjność i blokada

Przepływ publish:

1. Lock (`{root}/.state/handoff_journal.lock`)
2. Odczyt index → `next_handoff_id`
3. Sprawdzenie konfliktu pliku
4. Generacja dokumentu w pamięci
5. Atomowy zapis `HANDOFF-NNNN.md`
6. Atomowy zapis `latest.md`
7. Unlock
8. Schowek (opcjonalnie)
9. Walidacja z `index_override` (projected)
10. Lock → zapis index → unlock
11. Pełna walidacja; rollback index przy fail

---

## 6. Semantyka `source_reports`

Raporty GWO istniejące **przed** generowaniem handoffu. Pozostają wyłącznie w `source_reports`.

---

## 7. Semantyka `generated_artifacts`

Wyłącznie artefakty utworzone przez transakcję:

- `docs/handoff/HANDOFF-NNNN.md`
- `docs/handoff/latest.md`

Raporty źródłowe **nie** są dodawane automatycznie. Walidator wykrywa nakładanie się `source_reports ∩ generated_artifacts`.

---

## 8. `handoff_generator`

Pole YAML: `handoff_generator: guardian`  
Dozwolone: `guardian`, `manual`, `api`, `gui`  
Guardian CLI (`ifg handoff latest`) zawsze wpisuje `guardian`.

---

## 9. Zmiany walidatora

- `HANDOFF_ID_CONFLICT`, `INVALID_HANDOFF_GENERATOR`, `SOURCE_GENERATED_OVERLAP`, `INVALID_SOURCE_DESCRIPTION`
- `index_override` dla walidacji przed commit index
- `parent_handoff` — walidacja formatu, nie wymaga istnienia w journal
- Sekcja `## Źródła` — opis nie może być samym „Brak.”

---

## 10. rebuild-index

`rebuild_index_from_files_strict()`:

- Skan tylko `HANDOFF-[0-9]{4}.md`
- Weryfikacja YAML vs nazwa pliku
- Wykrywanie luk i `FILENAME_ID_MISMATCH`
- FAILED przy konfliktach (bez zgadywania)

---

## 11. rebuild-latest

Byte-for-byte kopia ostatniego `HANDOFF-NNNN.md` → `latest.md` z weryfikacją identyczności.

---

## 12. doctor

Rozszerzony output:

```
count=0, latest=None, next=HANDOFF-0001, latest_status=EMPTY_JOURNAL, clipboard=AVAILABLE
```

---

## 13. Testy i wyniki

```bash
python3 -m pytest tests/unit/test_guardian_handoff_journal.py \
  tests/unit/test_guardian_ifg_handoff.py \
  tests/unit/test_guardian_handoff_clipboard.py -q
# 40 passed
```

Pokrycie: numeracja 1→2→3, restart index, konflikt ID, paralelne ID, semantyka artifacts, gate, rebuild, doctor, legacy.

---

## 14. Wynik końcowej walidacji

```bash
python3 scripts/guardian.py handoff validate
# Handoff journal valid.

python3 scripts/guardian.py handoff doctor
# next=HANDOFF-0001, count=0, latest_status=EMPTY_JOURNAL
```

---

## 15. Następny poprawnie wyliczony numer handoffu

**HANDOFF-0001** (pierwszy realny publish po merge) → index `next_handoff_id: 2`.

---

## 16. Zmienione pliki

| Plik |
|------|
| `scripts/ifg_guardian/core/handoff_journal/models.py` |
| `scripts/ifg_guardian/core/handoff_journal/service.py` |
| `scripts/ifg_guardian/core/handoff_journal/integrity.py` |
| `scripts/ifg_guardian/core/handoff_journal/store.py` |
| `scripts/ifg_guardian/core/handoff_journal/workflow_gate.py` |
| `scripts/ifg_guardian/modules/ifg_handoff.py` |
| `scripts/ifg_guardian/modules/handoff_journal.py` |
| `docs/handoff/HANDOFF_V1_SPEC.md` |
| `tests/unit/test_guardian_handoff_journal.py` |
| `tests/unit/test_guardian_ifg_handoff.py` |
| `tests/unit/test_guardian_handoff_clipboard.py` |

---

## 17. Ograniczenia

- Schema 1 zamrożona — zmiany wymagają `handoff_schema: 2`
- Orphan handoff (zapisany plik, index nie zaktualizowany po fail validate) wymaga `rebuild-index` lub ręcznej interwencji
- Historyczne `reports/CHATGPT_HANDOFF_*` pozostają w repo

---

## 18. Elementy niewykonane

- Deploy DS723+ / runtime IFG (zakaz)
- Auto-migracja legacy handoffów
- Usunięcie historycznych `reports/CHATGPT_HANDOFF_*`

---

## Decyzje dla ChatGPT

1. Czy orphan handoff po failed validate powinien być automatycznie usuwany w v2, czy zawsze wymaga operatora?
2. Czy `parent_handoff` wskazujący na handoff spoza journal powinien generować notice (nie error)?

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Trwała numeracja z `index.json`
- Transakcyjna alokacja + `HANDOFF_ID_CONFLICT`
- Semantyka `source_reports` / `generated_artifacts` / `handoff_generator`
- Handoff Gate z walidacją przed commit index
- 40 testów PASS

⚠️ Znane problemy
- Journal pusty do pierwszego realnego `ifg handoff latest`
- 0075A/0075B/0075C w jednym commicie (nie były wcześniej na production)

❌ Co nie działa
- Brak w zakresie 0075C

---

## WYGENEROWANE RAPORTY

- `docs/reports/2026-07-11_GWO-GUARDIAN-0075C_HANDOFF_NUMBERING_AND_FINAL_GATE.md`
- `docs/handoff/HANDOFF_V1_SPEC.md` (zaktualizowana)

## WYGENEROWANE HANDOFFY

- Brak (journal pusty; następny: `HANDOFF-0001`)

## KROKI DLA OPERATORA

1. Pull/merge commit na `production`
2. `python3 scripts/guardian.py handoff doctor` — sprawdź `next=HANDOFF-0001`
3. `python3 scripts/guardian.py ifg handoff latest` — pierwszy realny handoff
4. Potwierdź: `validate` OK, `latest.md` == `HANDOFF-0001.md`, index `next_handoff_id: 2`

## ZAKAZY (przestrzegane)

- ❌ Stałe HANDOFF-0001 w generatorze
- ❌ Reset index przy uruchomieniu
- ❌ Nadpisywanie istniejącego handoffu
- ❌ Skan katalogu przy normalnym generowaniu
- ❌ Source report w generated_artifacts
- ❌ Runtime IFG / deploy DS723+
