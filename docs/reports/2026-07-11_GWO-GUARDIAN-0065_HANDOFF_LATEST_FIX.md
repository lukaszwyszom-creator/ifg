---
kind: gwo
project: IFG
workflow: GWO-GUARDIAN-0065
handoff: true
created_at: 2026-07-11
---

# GWO-GUARDIAN-0065 — Handoff Latest Regression Fix

**Data:** 2026-07-11  
**Cel:** Naprawić regresję `guardian ifg handoff latest` — zwracać wyłącznie raport ostatnio zakończonego zadania GWO.

---

## Problem

Po GWO-IFG-0064 komenda:

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli ifg handoff latest
```

wygenerowała handoff z **10 historycznymi** plikami (`repository_*.md`, `guardian_recover_*.md`) zamiast raportu `GWO-IFG-0064`.

**Objaw w `reports/CHATGPT_HANDOFF_2026-07-11.md` (przed fixem):**

- Liczba raportów: 10
- Zakres GWO: brak jawnych identyfikatorów GWO
- Preferencja raportów z dzisiaj: NIE
- Brak `2026-07-10_GWO-IFG-0064_RELEASE_GATE_UNBLOCK.md`

---

## Analiza root cause

### 1. Filtrowanie po dacie (główna przyczyna)

`select_latest_reports()` szukało plików z prefiksem **dzisiejszej daty** (`2026-07-11_`):

```python
todays = [p for p in candidates if p.name.startswith(stamp)]
```

Raport GWO-0064 ma nazwę `2026-07-10_GWO-IFG-0064_...` — **nie pasował** do 2026-07-11.

### 2. Fallback bez filtra GWO

Gdy brak raportów z dzisiaj, brano `candidates[:limit]` (limit=10) — **wszystkie** pliki `docs/reports/*.md` posortowane po `mtime`, bez rozróżnienia GWO vs artefakty.

### 3. Stan `sent_reports` w `.state/handoff.json`

Wszystkie raporty GWO z 2026-07-09 i 2026-07-10 były już oznaczone jako wysłane. Po odfiltrowaniu sent, w puli unsent zostały głównie artefakty repo/guardian z commita `90afcb9` (świeży `mtime` ~00:05).

### 4. Raport GWO-0064

Plik **istniał** (`docs/reports/2026-07-10_GWO-IFG-0064_RELEASE_GATE_UNBLOCK.md`, mtime 00:10) i **nie był** w `sent_reports`, ale:

- nie pasował do filtra daty „dzisiaj”,
- w fallbacku przegrał z 10 innymi unsent plikami — bo `limit=10` i brak filtra GWO w discovery.

### 5. Mtime vs workflow

Mechanizm nie śledził „ostatniego workflow” — tylko datę w nazwie (batch dzienny) lub mtime wszystkich `.md`.

---

## Naprawa

**Pliki:** `scripts/ifg_guardian/modules/ifg_handoff.py`, `scripts/ifg_guardian/cli.py`, `tests/unit/test_guardian_ifg_handoff.py`

| Zmiana | Opis |
|---|---|
| `GWO_TASK_REPORT_NAME` | Regex `^\d{4}-\d{2}-\d{2}_GWO[-_]` — tylko raporty zadań GWO |
| `_discover_report_candidates()` | Skanuje wyłącznie pliki GWO, sortuje po `mtime` malejąco |
| `select_latest_reports()` | Usunięto batch „wszystkie z dzisiaj”; zwraca `[:limit]` najnowszych unsent GWO |
| Domyślny `limit` | `10` → `1` (jeden raport = ostatnie zadanie) |
| Testy regresji | `test_handoff_latest_ignores_non_gwo_artifacts`, `test_handoff_latest_selects_yesterday_gwo_when_no_today_report` |

---

## Walidacja po naprawie

```bash
PYTHONPATH=scripts python3 -m pytest tests/unit/test_guardian_ifg_handoff.py -q
# 14 passed

PYTHONPATH=scripts python3 -m ifg_guardian.cli ifg handoff latest --no-clipboard
```

**Wynik:**

```
Handoff report: reports/CHATGPT_HANDOFF_2026-07-11.md
Merged reports: 1
```

**Zawartość handoff:**

- Liczba raportów: **1**
- Zakres GWO: **GWO-IFG-0064**
- Scalono: `docs/reports/2026-07-10_GWO-IFG-0064_RELEASE_GATE_UNBLOCK.md`
- Brak `repository_*` / `guardian_recover_*`

---

🩷 STATUS KOŃCOWY

✅ Co działa
- `handoff latest` zwraca 1 raport GWO-IFG-0064 (dowód: `Merged reports: 1`, treść handoff)
- Artefakty non-GWO ignorowane
- Raport z wczoraj (2026-07-10) wybierany gdy brak dzisiejszego GWO
- 14/14 testów unit handoff

⚠️ Znane problemy
- Kolejne uruchomienie `handoff latest` zwróci pusty handoff (0064 już w `sent_reports`) — oczekiwane
- Raporty bez prefiksu `YYYY-MM-DD_GWO-` (np. `GUARDIAN_RELEASE_ADVISOR`) nie są obsługiwane przez `latest`

❌ Co nie działa
- Brak regresji w mechanizmie latest

---

A. Root cause  
Batchowy filtr daty „dzisiaj” + fallback na 10 dowolnych `.md` bez filtra GWO.

B. Zmienione pliki  
- `scripts/ifg_guardian/modules/ifg_handoff.py`  
- `scripts/ifg_guardian/cli.py`  
- `tests/unit/test_guardian_ifg_handoff.py`

C. Deploy  
Nie dotyczy (narzędzie lokalne Guardian).

D. Testy  
`tests/unit/test_guardian_ifg_handoff.py` — 14 passed; handoff produkcyjny na repo — 1 raport GWO-0064.

E. Następny krok  
Commit fixu; przy kolejnym zadaniu GWO nowy raport pojawi się automatycznie w `handoff latest`.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-11_GWO-GUARDIAN-0065_HANDOFF_LATEST_FIX.md`
- `reports/CHATGPT_HANDOFF_2026-07-11.md` (po naprawie — tylko GWO-IFG-0064)
