# Guardian Report Metadata Standard

**Version:** 1  
**Status:** Active (GDD-0011)

## Cel

Jawne metadane raportów zamiast heurystyk nazw plików (`YYYY-MM-DD_GWO-*`) w narzędziach Guardiana (m.in. `guardian ifg handoff latest`).

## Format

YAML front matter na początku pliku Markdown:

```markdown
---
kind: gwo
project: IFG
workflow: GWO-IFG-0064
handoff: true
created_at: 2026-07-10T22:10:00Z
---

# Tytuł raportu
...
```

## Pola wymagane (minimalny zestaw)

| Pole | Typ | Opis |
|---|---|---|
| `kind` | string | Typ raportu: `gwo`, `adr`, `fd`, `rfc`, `review`, `guardian`, `report`, `lamus` |
| `project` | string | Projekt: np. `IFG`, `Guardian` |
| `workflow` | string | Identyfikator zadania: np. `GWO-IFG-0064`, `ADR-0065` |
| `handoff` | bool | `true` — raport kwalifikuje się do `handoff latest`; `false` — pomijany |
| `created_at` | string | Data lub ISO datetime do sortowania (opcjonalne, fallback: mtime pliku) |

## Kompatybilność wsteczna

Raporty **bez** front matter nadal są obsługiwane przez fallback:

- nazwa pliku pasuje do `^\d{4}-\d{2}-\d{2}_GWO[-_]`
- sortowanie po `mtime`

Raporty **z** front matter wymagają kompletu pól (`kind`, `project`, `workflow`, `handoff`). Brak któregoś pola → traktowane jak brak metadanych (fallback).

## Handoff latest

1. Skan `docs/reports/*.md`
2. Parsuj front matter
3. Jeśli `handoff: true` → kandydat (dowolny `kind`)
4. Jeśli brak front matter → fallback regex GWO
5. Sortuj po `created_at`, potem `mtime`
6. Zwróć najnowszy unsent raport (`limit` domyślnie 1)

## Przykłady

### GWO task report

```yaml
kind: gwo
project: IFG
workflow: GWO-GUARDIAN-0065
handoff: true
created_at: 2026-07-11
```

### ADR (bez konwencji nazwy GWO)

```yaml
kind: adr
project: IFG
workflow: ADR-0065
handoff: true
created_at: 2026-07-11T12:00:00Z
```

### Raport wewnętrzny (bez handoffu)

```yaml
kind: guardian
project: Guardian
workflow: GUARDIAN-DEPLOY-20260711
handoff: false
created_at: 2026-07-11
```
