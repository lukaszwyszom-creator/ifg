# GWO-GUARDIAN-0074 — GDD Registry Integrity Gate

**Data:** 2026-07-11  
**Branch:** production  
**Werdykt:** IMPLEMENTED

---

## 1. Stan początkowy

| Parametr | Wartość |
|----------|---------|
| Branch | `production` @ `17d5ef5` (lokalnie +1 commit względem `origin/production` @ `d46be0c`) |
| Plik rejestru | `docs/guardian/deferred_decisions.json` |
| `schema_version` | 1 |
| `next_id` | 16 (deklarowany; poprawny po naprawie) |
| Liczba wpisów przed naprawą | 19 (16 unikalnych ID + 3 techniczne duplikaty) |
| Liczba wpisów po naprawie | 16 |
| Walidacja przed naprawą | FAIL — `DUPLICATE_ID` × 3 |

Potwierdzone duplikaty:

- `GDD-0013` — 2 wpisy (identyczna treść)
- `GDD-0014` — 2 wpisy (różnica w polu `source`)
- `GDD-0015` — 2 wpisy (różnica w polu `source`)

---

## 2. Root cause

**Dowód Git:** `git show d46be0c:docs/guardian/deferred_decisions.json` → 13 wpisów, brak duplikatów.

Duplikaty powstały w **niezacommitowanych zmianach** podczas GWO-IFG-0073 (rejestracja LAMUS): ręczna/podwójna edycja JSON w working tree (append drugiego bloku wpisów 0013–0015), **nie** przez `DeferredDecisionService.add()` ani równoległe procesy.

Wcześniejszy `store.py` (bez walidacji, `write_text` bez atomowości) ułatwiał regresję, ale nie był bezpośrednią przyczyną tych trzech duplikatów.

---

## 3. Analiza ścieżek zapisu GDD

| Ścieżka | Zapis | Status po GWO-0074 |
|---------|-------|-------------------|
| `store.py` → `save_store()` | Atomowy JSON + walidacja + backup | **Kanoniczna** |
| `service.py` → `add/done/cancel/repair` | Lock + load-modify-save | **Kanoniczna** |
| `modules/deferred_decisions.py` | CLI wrapper | **Kanoniczna** |
| `cli.py` → `deferred *` | Dispatch | **Kanoniczna** |
| Ręczna edycja JSON (LAMUS GWO-0073) | Bezpośredni zapis pliku | **Zdeprecjonowana** — dokumentacja wymaga `guardian deferred add` |

Brak innych modułów zapisujących do `deferred_decisions.json`.

---

## 4. Model integralności

Zaimplementowano w `scripts/ifg_guardian/core/deferred_decisions/integrity.py`:

1. Wymagane pola niepuste (`id`, `project`, `module`, `type`, `priority`, `status`, `defer_reason`, `description`, `review_when`, `source`, `created_at`)
2. Unikalność `id`
3. Format standardowy `GDD-NNNN` lub namespaced `GDD-XXX-NNNN`
4. `next_id` = pierwszy wolny numer w sekwencji standardowej (namespaced ignorowane)
5. Status ∈ {OPEN, DONE, CANCELLED}
6. DONE wymaga `closed_at`; OPEN nie może mieć `closed_at`
7. Nieznane pola zachowywane (`extra_fields`, np. `lamus_status`)
8. Wykrywanie duplikatów logicznych (klucz: project + module + type + normalized description)

---

## 5. Naprawa danych

- Usunięto drugie wystąpienia `GDD-0013`, `GDD-0014`, `GDD-0015` (zachowano pierwsze, pełniejsze wpisy)
- Statusy i semantyka decyzji **niezmienione**
- `next_id: 16` — poprawne (GDD-0001..0015 zajęte, GDD-MAC-0001 nie wpływa)
- Kopia zapasowa: mechanizm `.state/gdd_backups/` (poza git)

---

## 6. Idempotencja

`DeferredDecisionService.add()` zwraca:

| Wynik | Zachowanie |
|-------|------------|
| `CREATED` | Nowy wpis |
| `ALREADY_EXISTS` | Ten sam klucz logiczny — zwrócone istniejące ID |
| `ID_CONFLICT` | To samo ID, inna treść — przerwanie |
| `DUPLICATE_DECISION` | Ten sam klucz pod innym ID — przerwanie |

---

## 7. Atomowy zapis

`save_store()`:

1. Walidacja stanu wynikowego
2. Backup do `.state/gdd_backups/deferred_decisions_YYYYMMDD_HHMMSS.json`
3. `mkstemp` + `write` + `flush` + `fsync`
4. `os.replace` (atomowy)
5. Przy błędzie — oryginalny plik nietknięty

---

## 8. Blokada współbieżności

`GddRegistryLock` — `fcntl.flock` na `.state/gdd_registry.lock`, timeout 10s, polling 50ms.

Operacje `add`, `done`, `cancel`, `repair` — pełny load-modify-save pod lockiem.

---

## 9. Komendy validate / repair

```bash
guardian deferred validate          # exit 0 = OK
guardian deferred repair --dry-run  # propozycje bez zapisu
guardian deferred repair --yes      # naprawa jednoznacznych przypadków
```

Repair automatycznie:

- usuwa techniczne duplikaty ID (zachowuje pełniejszy wpis),
- koryguje `next_id`,
- naprawia `closed_at` vs status.

**Nie scala** semantycznie różnych wpisów.

---

## 10. Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `docs/guardian/deferred_decisions.json` | Usunięcie duplikatów 0013–0015 |
| `scripts/ifg_guardian/core/deferred_decisions/integrity.py` | **NOWY** — walidacja, repair, klucz logiczny |
| `scripts/ifg_guardian/core/deferred_decisions/locking.py` | **NOWY** — blokada plikowa |
| `scripts/ifg_guardian/core/deferred_decisions/store.py` | Atomowy zapis, backup, walidacja |
| `scripts/ifg_guardian/core/deferred_decisions/service.py` | Idempotencja, lock, `ensure_registry_valid()` |
| `scripts/ifg_guardian/core/deferred_decisions/models.py` | `extra_fields` dla nieznanych pól |
| `scripts/ifg_guardian/core/deferred_decisions/__init__.py` | Eksporty |
| `scripts/ifg_guardian/modules/deferred_decisions.py` | validate, repair, obsługa `AddDecisionResponse` |
| `scripts/ifg_guardian/cli.py` | `deferred validate`, `deferred repair` |
| `tests/unit/test_guardian_gdd_integrity.py` | **NOWY** — 17 testów integralności |
| `tests/unit/test_guardian_deferred_decisions.py` | Aktualizacja pod nowe API |
| `docs/guardian/core/GUARDIAN_DEFERRED_DECISIONS.md` | Sekcja modelu integralności |

---

## 11. Testy i wyniki

```bash
PYTHONPATH=scripts python3 -m unittest \
  tests.unit.test_guardian_gdd_integrity \
  tests.unit.test_guardian_deferred_decisions -v
# Ran 27 tests in 0.289s — OK
```

Pokrycie wymagań GWO (skrót):

| # | Wymaganie | Status |
|---|-----------|--------|
| 1 | Poprawny rejestr przechodzi walidację | ✅ |
| 2 | Powielone ID odrzucane | ✅ |
| 3 | GDD-0013/14/15 po naprawie ×1 | ✅ |
| 4 | `next_id` przeliczane | ✅ |
| 5 | Namespaced nie psuje `next_id` | ✅ |
| 6 | Ponowne dodanie → ALREADY_EXISTS | ✅ |
| 7 | To samo ID, inna treść → ID_CONFLICT | ✅ |
| 8 | Ten sam klucz, inne ID → DUPLICATE_DECISION | ✅ (walidacja + add) |
| 9 | Atomowy zapis przy błędzie | ✅ |
| 10 | Blokada serializuje zapisy | ✅ |
| 11 | Timeout blokady | ✅ |
| 12–14 | repair dry-run / yes / brak scalania | ✅ |
| 15–16 | DONE/OPEN + closed_at | ✅ |
| 17 | Nieznane pola zachowane | ✅ |
| 18 | LAMUS idempotentne przez add | ✅ (dokumentacja + hook) |
| 19 | review/list regresja | ✅ |
| 20 | Pełny zestaw deferred tests | ✅ |

---

## 12. Walidacja końcowa

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli deferred validate
# GDD registry valid.
# exit 0
```

---

## 13. Commit i push

Commit zakresu GWO-GUARDIAN-0074 (bez cudzych raportów/auto-artefaktów).  
Push do `origin/production`.

---

## 14. Ryzyka i ograniczenia

| Ryzyko | Poziom | Opis |
|--------|--------|------|
| Ręczna edycja JSON | MEDIUM | Nadal możliwa — Integrity Gate wykrywa przy `validate` / zapisie przez CLI |
| Brak auto-validate w każdym workflow | LOW | `ensure_registry_valid()` dostępny; LAMUS wymaga świadomego wywołania |
| Lock tylko lokalny (Mac mini) | LOW | Zgodne z wymaganiami GWO |
| Duplikaty logiczne pod różnymi ID | MEDIUM | Wykrywane, wymagają ręcznej naprawy (bez auto-scalania) |

---

## 15. Elementy niewykonane

- Automatyczny hook `ensure_registry_valid()` w każdym workflow Guardiana (brak workflow LAMUS w kodzie — tylko dokumentacja + API)
- Wydzielenie `guardian_core` (poza zakresem GWO-0074)
- Deploy IFG na DS723+ (wykluczony)

---

## 16. Decyzje wymagające ChatGPT

Brak.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Rejestr GDD bez duplikatów ID; `guardian deferred validate` → exit 0
- Atomowy store z walidacją pre/post, backupem i blokadą flock
- Idempotentne `deferred add` (ALREADY_EXISTS / ID_CONFLICT / DUPLICATE_DECISION)
- CLI: `deferred validate`, `deferred repair --dry-run`, `deferred repair --yes`
- 27 testów jednostkowych GDD — OK

⚠️ Znane problemy
- Ręczna edycja JSON nadal możliwa poza Integrity Gate (wykrywana przy validate/zapisie CLI)
- `ensure_registry_valid()` nie jest jeszcze podpięty do wszystkich workflow (brak kodu LAMUS workflow)

❌ Co nie działa
- Brak regresji w zakresie GWO-0074

A. Root cause  
Podwójna ręczna edycja `deferred_decisions.json` podczas GWO-IFG-0073 LAMUS w dirty working tree.

B. Zmienione pliki  
Patrz sekcja 10.

C. Deploy  
Nie wykonano (zmiana narzędzia + rejestru repo; bez wpływu na runtime DS723+).

D. Testy  
`27/27 OK` — `test_guardian_gdd_integrity` + `test_guardian_deferred_decisions`.

E. Następny krok  
Podpięcie `ensure_registry_valid()` do przyszłego workflow LAMUS; rozważyć pre-commit hook `deferred validate` na `production`.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-11_GWO-GUARDIAN-0074_GDD_REGISTRY_INTEGRITY.md`
