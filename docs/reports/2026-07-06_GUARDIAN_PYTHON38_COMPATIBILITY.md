# Guardian — kompatybilność Python 3.8 (DS723+)

**Data:** 2026-07-06  
**Kontekst:** dry-run na DS723+ zatrzymany błędem:

```
ImportError: cannot import name 'UTC' from 'datetime'
```

**Środowisko DS723+:** Python **3.8**  
**Zakres analizy:** `scripts/ifg_guardian/` (128 plików `.py`)  
**Zmiany w kodzie:** nie wykonano (raport read-only)

---

## 1. Werdykt

# Problem ogranicza się wyłącznie do `datetime.UTC` (Python 3.11+).

W katalogu `scripts/ifg_guardian` **nie znaleziono** innych konstrukcji wymagających Python ≥3.11 (ani ≥3.9/3.10 w użyciu runtime).

Błąd występuje **przy imporcie modułu** (przed wykonaniem logiki dry-run), więc każde uruchomienie Guardiana na Python 3.8 kończy się natychmiastowym `ImportError`.

---

## 2. Niekompatybilne miejsca — `datetime.UTC`

Stała `datetime.UTC` została dodana w **Python 3.11** ([PEP 615](https://peps.python.org/pep-0615/) alias `datetime.timezone.utc`).

W Python 3.8 poprawny odpowiednik: `datetime.timezone.utc`.

### 2.1 Pliki z `from datetime import UTC`

| # | Plik | Użycie |
|---|------|--------|
| 1 | `core/preflight/engine.py` | `datetime.now(UTC)` — `started_at`, `finished_at` |
| 2 | `core/preflight/models.py` | `default_factory=lambda: datetime.now(UTC)` |
| 3 | `core/preflight/report.py` | timestamp raportu |
| 4 | `core/workflow/engine.py` | timestamp artefaktów workflow |
| 5 | `core/workflow/transaction.py` | `started_at`, `ended_at` transakcji |
| 6 | `core/repo_audit/report.py` | timestamp raportu |
| 7 | `reporting.py` | `default_report_path()` — suffix daty |
| 8 | `plugins/ifg/doctor/report.py` | timestamp raportu |
| 9 | `plugins/ifg/release_plan/report.py` | timestamp raportu |
| 10 | `plugins/ifg/deploy_run/report.py` | timestamp raportu |

**Łącznie:** 10 plików, **14 wystąpień** `datetime.now(UTC)` / import `UTC`.

### 2.2 Ścieżka importu przy cutover dry-run

Typowy łańcuch (pierwszy napotkany moduł z `UTC` zależy od kolejności importów):

```
python3 -m ifg_guardian ifg cutover run --dry-run
  → cli.py
  → modules/ifg_container_cutover.py
  → plugins/ifg/container_cutover/stages.py
  → core/preflight/engine.py          ← ImportError: UTC
```

Alternatywnie:

```
  → core/workflow/engine.py             ← ImportError: UTC
```

Żaden etap workflow nie jest wykonywany — awaria na **load module**.

---

## 3. Przeszukane konstrukcje ≥3.9 / ≥3.10 / ≥3.11

| Konstrukcja | Min. Python | Wynik w `ifg_guardian` |
|-------------|-------------|-------------------------|
| `datetime.UTC` | **3.11** | **10 plików — JEDYNY BLOKER** |
| `match` / `case` | 3.10 | brak |
| `tomllib` | 3.11 | brak |
| `ExceptionGroup` | 3.11 | brak |
| `typing.Self` | 3.11 | brak |
| `StrEnum` | 3.11 | brak (`str, Enum` — OK na 3.8) |
| `functools.cache` | 3.9 | brak |
| `str.removeprefix` / `removesuffix` | 3.9 | brak |
| `Path.is_relative_to` | 3.9 | brak |
| `zoneinfo` | 3.9 | brak |
| `dict \| dict` merge | 3.9 | brak (tylko `\|` w stringach markdown) |
| `async def` / `TaskGroup` | 3.11 | brak async w guardian |

### 3.1 `str | None`, `list[str]` (PEP 604 / 585)

Występują szeroko, ale **prawie wszystkie** pliki mają:

```python
from __future__ import annotations
```

Dzięki temu adnotacje nie są ewaluowane w runtime — **kompatybilne z Python 3.8**.

Pliki bez `__future__` to wyłącznie puste `__init__.py`, `__main__.py`, `compat.py` — bez składni `X | Y`.

### 3.2 Inne zależności stdlib używane przez Guardiana

| API | Min. Python | Status 3.8 |
|-----|-------------|-------------|
| `subprocess.run(..., capture_output=, text=)` | 3.7 | OK |
| `subprocess.run(..., timeout=)` | 3.3+ | OK |
| `dataclasses` | 3.7 | OK |
| `typing.Literal`, `typing.Protocol` | 3.8 | OK |
| `pathlib.Path` | 3.4+ | OK |
| `enum.Enum` + mixin `str` | 3.4+ | OK |

---

## 4. Minimalny zakres zmian

### Rekomendacja: jeden moduł kompatybilności + podmiana importów

**Nowy plik** (propozycja):

```python
# scripts/ifg_guardian/core/time_compat.py
from __future__ import annotations

from datetime import datetime, timezone

# Semantycznie identyczne z datetime.UTC (Python 3.11+).
UTC = timezone.utc

__all__ = ["UTC", "datetime", "timezone"]
```

**W każdym z 10 plików** zamienić:

```python
# było:
from datetime import UTC, datetime

# ma być:
from datetime import datetime
from ifg_guardian.core.time_compat import UTC
```

**Nie zmieniać** wywołań `datetime.now(UTC)` — po imporcie aliasu działają bez zmian.

### Alternatywa (bez nowego modułu)

W każdym pliku:

```python
from datetime import datetime, timezone
UTC = timezone.utc
```

Większy diff (10× duplikacja), gorsza utrzymywalność — **niezalecane**.

### Pliki poza zakresem `ifg_guardian` (informacyjnie)

Ten sam wzorzec `datetime.UTC` występuje też w:

- `scripts/guardian2.py`
- `scripts/guardian_platform/**` (kilka reportów)

Jeśli na DS723+ uruchamiane są wyłącznie `python3 -m ifg_guardian`, wystarczy poprawka w `ifg_guardian`. Jeśli operator używa `guardian2.py` lub `guardian_platform` lokalnie na NAS — wymagana analogiczna poprawka.

---

## 5. Ocena ryzyka

| Aspekt | Ocena |
|--------|--------|
| Ryzyko regresji funkcjonalnej | **Bardzo niskie** — `timezone.utc` ≡ `UTC` |
| Ryzyko regresji na Python 3.11+ | **Brak** — alias działa identycznie |
| Złożoność zmiany | **Niska** — 10 plików + 1 helper |
| Testowanie | Uruchomienie `python3.8 -m ifg_guardian ifg cutover run --dry-run` na DS723+ lub lokalnie z pyenv 3.8 |
| Ryzyko ukrytych problemów 3.8 | **Niskie** po tej poprawce — brak innych blockerów w analizie statycznej |

**Uwaga operacyjna:** Guardian na DS723+ wymaga także dostępności `npm` (cutover frontend build) — to osobny wymóg, niezwiązany z Pythonem.

---

## 6. Rekomendowana poprawka (kolejność)

1. Dodać `core/time_compat.py` z `UTC = timezone.utc`.
2. Zaktualizować 10 plików z tabeli w §2.1.
3. Dodać test jednostkowy:

   ```python
   def test_utc_importable_on_legacy_alias():
       from ifg_guardian.core.time_compat import UTC
       from datetime import datetime, timezone
       assert UTC is timezone.utc
       assert datetime.now(UTC).tzinfo is not None
   ```

4. Zweryfikować na DS723+:

   ```bash
   cd /volume1/docker/ifg_v2/ifg_standalone
   PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --dry-run
   ```

5. (Opcjonalnie) Udokumentować minimum Python **3.8+** w README/runbook Guardiana.

---

## 7. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy problem to tylko `datetime.UTC`? | **TAK** (w `scripts/ifg_guardian`) |
| Ile plików? | **10** |
| Czy są inne blockery ≥3.11? | **NIE** (w analizie statycznej) |
| Minimalna poprawka? | `UTC = timezone.utc` w jednym module + podmiana importów |
| Czy deploy/cutover LIVE wymagany do weryfikacji? | **NIE** — wystarczy import + dry-run |

---

*Raport analityczny. Bez zmian w kodzie, deployu i LIVE cutover.*
