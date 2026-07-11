# GWO-GUARDIAN-0075 — Workflow Artifact Engine (Handoff Journal)

**Data:** 2026-07-11  
**Branch:** production  
**Werdykt:** IMPLEMENTED

---

## 1. Architektura

Workflow Artifact Engine v1 wprowadza trwały dziennik handoff w `docs/handoff/`.

```
docs/handoff/
├── index.json          # stan numeracji (bez skanowania katalogu przy publish)
├── latest.md           # byte-for-byte kopia ostatniego handoff-NNNN.md
├── handoff-0001.md
├── handoff-0002.md
└── ...
```

Moduły:

| Warstwa | Plik | Rola |
|---------|------|------|
| Modele | `core/handoff_journal/models.py` | YAML metadata, index |
| Store | `core/handoff_journal/store.py` | Atomowy zapis plików |
| Integrity | `core/handoff_journal/integrity.py` | validate, parse, rebuild, doctor |
| Service | `core/handoff_journal/service.py` | publish, lock, allocate ID |
| Gate | `core/handoff_journal/workflow_gate.py` | wymagane kroki SUCCESS |
| CLI | `modules/handoff_journal.py` | validate / rebuild / doctor |
| Integracja | `modules/ifg_handoff.py` | `ifg handoff latest` → journal |

Przepływ publish (`HandoffJournalService.publish`):

1. REPORT_SAVED (raporty źródłowe istnieją)
2. HANDOFF_GENERATED
3. HANDOFF_SAVED (`handoff-NNNN.md` + YAML)
4. LATEST_UPDATED (`latest.md` identyczny bajtowo)
5. INDEX_UPDATED (`index.json`)
6. CLIPBOARD_UPDATED (gdy włączone)

Awaria przed krokiem 6 → exit code 1 (workflow FAILED).  
`next_handoff_id` inkrementowane **tylko** po pełnym zapisie index (krok 5).

---

## 2. Zmienione moduły

| Plik | Zmiana |
|------|--------|
| `scripts/ifg_guardian/core/handoff_journal/*` | **NOWY** — Artifact Engine v1 |
| `scripts/ifg_guardian/modules/handoff_journal.py` | **NOWY** — CLI |
| `scripts/ifg_guardian/modules/ifg_handoff.py` | Integracja journal + gate FAILURE |
| `scripts/ifg_guardian/cli.py` | `guardian handoff validate/rebuild-index/rebuild-latest/doctor` |
| `docs/handoff/index.json` | **NOWY** — stan początkowy |
| `docs/handoff/latest.md` | **NOWY** — pusty do pierwszego handoff |
| `tests/unit/test_guardian_handoff_journal.py` | **NOWY** |
| `tests/unit/test_guardian_handoff_clipboard.py` | Clipboard failure → exit 1 |

---

## 3. Testy

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/unit/test_guardian_handoff_journal.py \
  tests/unit/test_guardian_handoff_clipboard.py -q
# 12 passed
```

Pokrycie wymagań:

| Scenariusz | Status |
|------------|--------|
| Pierwszy handoff | ✅ |
| Kolejne handoff / previous_handoff | ✅ |
| latest byte-identical | ✅ |
| index.json | ✅ |
| rebuild-index / rebuild-latest | ✅ |
| validate | ✅ |
| parent_handoff | ✅ |
| source_reports | ✅ |
| doctor (zły latest) | ✅ |
| Awaria schowka → FAILED | ✅ |
| Awaria latest → brak inkrementacji next_id | ✅ |

---

## 4. Nowe komendy

```bash
guardian handoff validate
guardian handoff rebuild-index
guardian handoff rebuild-latest
guardian handoff doctor
```

Generowanie (istniejące, rozszerzone):

```bash
guardian ifg handoff latest
guardian ifg handoff latest --no-clipboard
```

---

## 5. Migracja

- Istniejące `reports/CHATGPT_HANDOFF_*.md` **zachowane** (zgodność wsteczna).
- Journal startuje od `handoff-0001` (`index.json`: `next_handoff_id: 1`, `count: 0`).
- Historyczne handoffy w `reports/` nie są migrowane automatycznie.
- Odbudowa: `guardian handoff rebuild-index` skanuje `handoff-*.md`.

---

## 6. Zgodność wsteczna

- Mechanizm schowka (`pbcopy` + weryfikacja) bez zmian semantyki — ale failure przerywa workflow.
- `.state/handoff.json` (sent_reports) nadal używany.
- Raporty źródłowe w `docs/reports/` nietknięte.
- `ifg handoff latest` bez raportów → legacy pusty handoff, **bez** wpisu journal.

---

## 7. Ograniczenia

- Gate workflow engine podpięty do `run_ifg_handoff_latest`; inne workflow nie generują handoff automatycznie.
- Clipboard wymagany tylko gdy `--clipboard` (domyślnie włączone).
- `rebuild-index` nie odtwarza brakujących plików handoff — tylko metadane index.
- Brak deployu / zmian runtime IFG.

---

## 8. Walidacja końcowa

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli handoff validate
# Handoff journal valid.
# exit 0
```

---

## Decyzje dla ChatGPT

Brak.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- `docs/handoff/` z `index.json` + `latest.md`
- Numerowane `handoff-NNNN.md` z YAML front matter
- `guardian handoff validate` → exit 0
- `ifg handoff latest` publikuje do journal; clipboard failure → exit 1
- 12/12 testów journal OK

⚠️ Znane problemy
- Historyczne handoffy w `reports/` poza journal (świadoma migracja manualna)
- Auto-gate nie podpięty do wszystkich workflow Guardiana (tylko ścieżka handoff latest)

❌ Co nie działa
- Brak regresji w zakresie GWO-0075

A. Root cause  
Brak trwałego artefaktu handoff — workflow SUCCESS bez journal i utrata schowka.

B. Zmienione pliki  
Patrz sekcja 2.

C. Deploy  
Nie wykonano (narzędzie + docs).

D. Testy  
12/12 journal + clipboard tests OK.

E. Następny krok  
Opcjonalnie: podpięcie `workflow_gate` do workflow generujących raporty GWO.

## Wygenerowane raporty

- `docs/reports/2026-07-11_GWO-GUARDIAN-0075_WORKFLOW_ARTIFACT_ENGINE.md`

## Wygenerowane handoffy

- `docs/handoff/index.json`
- `docs/handoff/latest.md`

(Numerowane `handoff-NNNN.md` powstają przy pierwszym `guardian ifg handoff latest` z raportami źródłowymi.)
