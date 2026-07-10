---
kind: gwo
project: IFG
workflow: GWO-GUARDIAN-0066
handoff: true
created_at: 2026-07-11T00:16:00Z
---

# GWO-GUARDIAN-0066 — Report Metadata Standard (GDD-0011)

**Data:** 2026-07-11  
**LAMUS:** GDD-0011 — DONE  
**Cel:** Przejście `handoff latest` z regexów nazw plików na jawne metadane raportów.

---

## LAMUS GDD-0011 — Problem

Regex `^\d{4}-\d{2}-\d{2}_GWO[-_]` rozwiązał regresję z GWO-0065, ale nie skaluje się na ADR, FD, RFC, Review i inne typy raportów bez konwencji nazwy GWO.

## Rozwiązanie

### Standard metadanych

Dokument: `docs/guardian/core/GUARDIAN_REPORT_METADATA_STANDARD.md`

Format: **YAML front matter** na początku Markdown:

```yaml
---
kind: gwo
project: IFG
workflow: GWO-GUARDIAN-0066
handoff: true
created_at: 2026-07-11T00:16:00Z
---
```

| Pole | Rola |
|---|---|
| `kind` | Typ raportu (`gwo`, `adr`, `fd`, `rfc`, `review`, …) |
| `project` | Projekt (`IFG`, `Guardian`) |
| `workflow` | Id zadania (`GWO-IFG-0064`, `ADR-0065`) |
| `handoff` | `true` → kwalifikuje do `handoff latest` |
| `created_at` | Sortowanie (ISO date/datetime); fallback: mtime |

### Implementacja

| Plik | Zmiana |
|---|---|
| `scripts/ifg_guardian/core/report_metadata.py` | Parser front matter (bez PyYAML) |
| `scripts/ifg_guardian/modules/ifg_handoff.py` | Selekcja po `handoff: true` + sort `created_at` |
| `docs/guardian/deferred_decisions.json` | GDD-0011 → `DONE` |
| `tests/unit/test_guardian_report_metadata.py` | 7 testów parsera |
| `tests/unit/test_guardian_ifg_handoff.py` | +3 testy regresji metadanych |

### Kompatybilność wsteczna

- Brak front matter → fallback regex `YYYY-MM-DD_GWO-*`
- Front matter niekompletny → fallback
- `handoff: false` → raport wykluczony nawet przy nazwie GWO

### Walidacja

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/unit/test_guardian_report_metadata.py \
  tests/unit/test_guardian_ifg_handoff.py -q
# 24 passed
```

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Parser metadanych YAML front matter
- `handoff latest` wybiera raporty po `handoff: true` i `created_at`
- Fallback legacy GWO filename bez zmian zachowania
- GDD-0011 oznaczony DONE
- 24/24 testów unit

⚠️ Znane problemy
- Istniejące raporty bez front matter nadal używają fallbacku (migracja stopniowa)

❌ Co nie działa
- Brak

---

A. Root cause  
Heurystyka nazw plików nie obsługuje nowych typów raportów poza konwencją GWO.

B. Zmienione pliki  
- `scripts/ifg_guardian/core/report_metadata.py` (nowy)  
- `scripts/ifg_guardian/modules/ifg_handoff.py`  
- `docs/guardian/core/GUARDIAN_REPORT_METADATA_STANDARD.md` (nowy)  
- `docs/guardian/deferred_decisions.json`  
- `docs/reports/2026-07-11_GWO-GUARDIAN-0065_HANDOFF_LATEST_FIX.md` (front matter)  
- testy metadata + handoff

C. Deploy  
Nie dotyczy (narzędzie lokalne Guardian).

D. Testy  
24 passed (metadata + handoff, w tym regresja ADR/review bez nazwy GWO).

E. Następny krok  
Stopniowo dodawać front matter do nowych raportów GWO/ADR/RFC.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-11_GWO-GUARDIAN-0066_REPORT_METADATA_STANDARD.md`
- `docs/guardian/core/GUARDIAN_REPORT_METADATA_STANDARD.md`
