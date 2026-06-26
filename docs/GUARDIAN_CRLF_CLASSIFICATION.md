# Guardian — klasyfikacja końców linii (CRLF)

**Data:** 2026-06-26  
**Moduł:** `scripts/ifg_guardian/core/line_endings.py`  
**Konsument:** `scripts/ifg_guardian/modules/repo.py` → `repo audit`, `repo clean --dry-run`

---

## Problem (stara heurystyka)

Wcześniejsza klasyfikacja `crlf_noise` opierała się na dwóch warunkach:

1. `git diff -w -- <path>` zwraca pusty wynik
2. opcjonalnie: „CRLF w working tree”

To dawało **fałszywe pozytywy**, np. dla `app/api/deps.py`:

| Warstwa | Stan |
|---------|------|
| HEAD | CRLF |
| index | CRLF |
| working tree | CRLF (identyczne bajty) |
| `git diff -w` | pusty |
| `git restore` | **nic nie zmienia** |

### Przyczyna fałszywych pozytywów (implementacja)

Oprócz samej heurystyki `git diff -w`, wcześniejsze wersje odczytywały HEAD/index przez `git show` w trybie **tekstowym** (`text=True`). Git wtedy konwertuje CRLF→LF w stdout, więc index/worktree wyglądały na różne mimo identycznych bajtów w blobie i na dysku.

Od 2026-06-26 bloby są odczytywane binarnie (`git show` bez `text=True`).

---

## Nowa logika

Funkcja `analyze_line_endings(path)` porównuje **trzy warstwy** bajt-po-bajcie i po normalizacji LF:

- HEAD (`git show HEAD:<path>`)
- index (`git show :<path>`)
- working tree (plik na dysku)

Guardian **nigdy** nie wykonuje `git restore` — tylko symuluje, czy restore mógłby coś zmienić (`index raw ≠ worktree raw`).

### Kategorie

| Kategoria | Warunki | Confidence typowa |
|-----------|---------|-------------------|
| `CRLF_ONLY` | Znormalizowana treść identyczna we wszystkich trzech warstwach; surowe bajty różnią się; `git diff --ignore-cr-at-eol` i `git diff -w` czyste; **index ≠ worktree** (restore simulation ✓) | HIGH |
| `UNKNOWN_LINE_ENDINGS` | Nie można jednoznacznie stwierdzić CRLF-only | LOW / MEDIUM |
| `NOT_LINE_ENDING` | Znormalizowana treść różni się — zmiana merytoryczna | HIGH |

### Przypadki `UNKNOWN_LINE_ENDINGS`

| Scenariusz | Confidence | Restore |
|------------|------------|---------|
| HEAD == index == worktree (raw), lecz git status pokazuje `M` | LOW | **nie** |
| `git diff --ignore-cr-at-eol` lub `-w` niespójne z porównaniem bajtów | LOW | **nie** |
| Treść znormalizowana OK, ale index == worktree (raw) | MEDIUM | **nie** |
| Nie udało się odczytać HEAD/index/worktree | LOW | **nie** |

### Reguła restore

Rekomendacja `git restore -- <path>` pojawia się **wyłącznie** gdy:

- kategoria = `CRLF_ONLY`, **oraz**
- `restore_would_help = True` (symulacja: index raw ≠ worktree raw)

---

## Verification (sekcja raportu)

Dla każdego pliku z kategorią `crlf_only` lub `unknown_line_endings` raport `repo audit` zawiera sekcję **Verification** z wynikami testów:

```
✓ HEAD vs index vs working tree (normalized LF)
✓ HEAD vs working tree (raw bytes)
✓ HEAD vs index (raw bytes)
✓ index vs working tree (raw bytes)
✓ git diff --ignore-cr-at-eol
✓ git diff -w
✓ git ls-files --eol (i/crlf w/crlf attr/text eol=lf)
✓ file (Python script text executable, ASCII text, with CRLF line terminators)
✓ restore simulation (index raw ≠ worktree raw)
```

Przykład w raporcie:

```
### `app/api/deps.py` — unknown_line_endings (Confidence: LOW)
- Restore recommended: **no**
- ✓ HEAD vs index vs working tree (normalized LF)
- ✓ HEAD vs working tree (raw bytes)
- ...
```

---

## Mapowanie na `FileCategory`

| `LineEndingCategory` | `FileCategory` (repo audit) |
|----------------------|----------------------------|
| `CRLF_ONLY` | `crlf_only` |
| `UNKNOWN_LINE_ENDINGS` | `unknown_line_endings` |
| `NOT_LINE_ENDING` | _(klasyfikacja kontynuowana heurystykami IFG)_ |

Alias `crlf_noise` pozostaje w enumie wyłącznie dla kompatybilności parsowania starych raportów.

---

## Testy

Plik: `tests/unit/test_guardian_line_endings.py`

| Test | Scenariusz |
|------|------------|
| `test_crlf_only_high_confidence_when_only_eol_differs` | LF w HEAD/index, CRLF w worktree → CRLF_ONLY |
| `test_unknown_when_head_index_worktree_raw_identical` | Fałszywy alarm deps.py → UNKNOWN, LOW |
| `test_not_line_ending_when_content_differs` | Różna treść → NOT_LINE_ENDING |
| `test_unknown_when_git_diff_inconsistent` | Niespójne diffy → UNKNOWN |
| `test_unknown_medium_when_index_equals_worktree_but_head_differs` | restore bezużyteczny → UNKNOWN, MEDIUM |
| `test_real_crlf_only_restore_would_help` | Integracja: prawdziwy repo, LF→CRLF |
| `test_real_identical_crlf_unknown_not_crlf_only` | Integracja: identyczne CRLF po commicie |

---

## Uruchomienie

```bash
python3 scripts/guardian.py repo audit
python3 scripts/guardian.py repo clean    # dry-run, read-only
pytest tests/unit/test_guardian_line_endings.py -v
```
