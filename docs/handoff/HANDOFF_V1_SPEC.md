# HANDOFF v1.0 — Kanoniczna specyfikacja (ZAMROŻONA)

**Status:** ZAMROŻONY (GWO-GUARDIAN-0075B + GWO-GUARDIAN-0075C)  
**Schema:** `handoff_schema: 1`  
**Artifact format:** `artifact_format_version: 1`

Każda przyszła zmiana wymaga `handoff_schema: 2` i osobnego GWO migracyjnego.

---

## Numeracja (źródło prawdy)

Jedynym źródłem numeracji podczas normalnej pracy jest:

`docs/handoff/index.json`

```json
{
  "schema_version": 1,
  "next_handoff_id": 4,
  "latest_handoff_id": 3,
  "count": 3
}
```

| Pole | Znaczenie |
|------|-----------|
| `next_handoff_id` | Numer kolejnego handoffu do przydzielenia |
| `latest_handoff_id` | Ostatni zatwierdzony handoff (lub `null`) |
| `count` | Liczba zatwierdzonych handoffów |

Reguły:

- `HANDOFF-0001` może powstać **tylko raz**
- Generator **nie** pobiera numeru z promptu, czasu ani skanowania katalogu
- Skanowanie katalogu wyłącznie w: `rebuild-index`, `doctor`, recovery
- Handoffy są **append-only** — brak nadpisywania istniejących plików
- Konflikt pliku → `HANDOFF_ID_CONFLICT`, operacja FAILED

---

## Lokalizacja

```
docs/handoff/
├── index.json
├── latest.md              # byte-identyczna kopia ostatniego HANDOFF-XXXX.md
├── HANDOFF-0001.md
└── ...
```

---

## YAML front matter

```yaml
---
kind: handoff
handoff_schema: 1
handoff_id: HANDOFF-0002
previous_handoff: HANDOFF-0001
parent_handoff: null
project_id: IFG
workflow: GWO-GUARDIAN-0075C
workflow_type: IMPLEMENTATION
status: SUCCESS
created_at: 2026-07-11T13:30:00Z
artifact_format_version: 1
handoff_generator: guardian
source_reports:
  - docs/reports/2026-07-11_GWO-EXAMPLE_A.md
generated_artifacts:
  - docs/handoff/HANDOFF-0002.md
  - docs/handoff/latest.md
---
```

### Semantyka pól

**`source_reports`** — raporty istniejące przed generowaniem handoffu, scalone/przeanalizowane.

**`generated_artifacts`** — wyłącznie artefakty utworzone przez operację generowania handoffu (minimum: `HANDOFF-NNNN.md` + `latest.md`). Raporty GWO **nie** trafiają do `generated_artifacts`.

**`handoff_generator`** — `guardian` | `manual` | `api` | `gui` (Guardian CLI wpisuje `guardian`).

**Zakazane w v1:** `project`, `generated_reports`, `cursor_format_version`

---

## workflow_type

`IMPLEMENTATION`, `REVIEW`, `DEPLOY`, `DIAGNOSTICS`, `RESEARCH`, `ARCHITECTURE`, `HOTFIX`

---

## Treść po YAML

1. Nagłówek `# HANDOFF-XXXX`
2. `## Wynik workflow` → `IMPLEMENTED` / `PARTIAL` / `FAILED`
3. `## Streszczenie`
4. `## Co wymaga decyzji ChatGPT`
5. `## Źródła` — `### ścieżka` + **jednoznaczne zdanie** (nie samo „Brak.”)
6. `## Następny oczekiwany krok` — obowiązkowe (`Brak.` gdy nieznane)
7. Stopka `END OF HANDOFF` + `HANDOFF-XXXX` (bez tekstu po)

---

## Handoff Gate (SUCCESS)

Workflow SUCCESS wyłącznie gdy:

1. Raport źródłowy istnieje
2. Handoff otrzymał kolejny numer z index
3. `HANDOFF-NNNN.md` zapisany (bez konfliktu)
4. `latest.md` byte-identyczny
5. Index zaktualizowany **po** walidacji
6. Schowek zaktualizowany (gdy włączony)
7. `guardian handoff validate` → kod 0

---

## Komendy recovery

```bash
guardian handoff rebuild-index   # skan HANDOFF-*.md, odtwarza index
guardian handoff rebuild-latest  # byte-copy ostatniego handoff
guardian handoff doctor          # diagnostyka + next expected ID
guardian handoff validate
```

---

## Legacy

- `handoff-NNNN.md`, `CHATGPT HANDOFF` → `LEGACY_FORMAT` (notice)
- Legacy nie wpływa na numerację v1 index (rebuild skanuje tylko `HANDOFF-*.md`)
- Brak auto-migracji
