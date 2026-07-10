# GWO-IFG-0045 — Isolate GWO-0042 Hotfix for Safe Deploy

**Data:** 2026-07-08  
**Status:** DONE (izolacja commita; deploy nie wykonywano)  
**Mechanizm:** osobny commit (bez stash, bez usuwania zmian)

---

## Stan repo przed operacją

| Pole | Wartość |
|------|---------|
| **Branch** | `production` |
| **HEAD** | `876900f6fac465859a72f58d091a99336fb85058` |
| **Ostatni commit** | `876900f` — `feat(guardian): GWO-IFG-0037 release engine quality` |

### Czy poprawka GWO-0042 była już w commicie?

**Nie.** Poprawka była wyłącznie w working tree:

- `app/services/auth_service.py` — brak guarda `UUID(str(user_id))` w HEAD
- `tests/unit/test_auth_service.py` — brak `test_invalid_subject_uuid_raises` w HEAD
- `docs/reports/2026-07-08_GWO-IFG-0042_TRANSMISSIONS_HTTP500_FIX.md` — plik untracked

---

## Wykonane kroki

1. Zweryfikowano `git status` — dirty tree z wieloma zmianami poza scope GWO-0042.
2. **Nie** użyto `git stash`.
3. **Nie** usunięto żadnych zmian.
4. Dodano do stage wyłącznie 3 pliki scope hotfixu.
5. Zweryfikowano `git diff --cached` przed commitem.
6. Utworzono izolowany commit.
7. Uruchomiono testy po commicie.
8. Zweryfikowano `git show --name-only -1` i pozostały dirty tree.

---

## Staged diff (przed commitem) — podsumowanie

```
 app/services/auth_service.py                       | 139 ++++++-------
 docs/reports/2026-07-08_GWO-IFG-0042_...md        | 219 +++++++++++++++++++++
 tests/unit/test_auth_service.py                    |   5 +
 3 files changed, 296 insertions(+), 67 deletions(-)
```

**Merytoryczna zmiana w `auth_service.py`:**

```python
try:
    user_uuid = UUID(str(user_id))
except (ValueError, TypeError, AttributeError) as exc:
    raise UnauthorizedError("Nieprawidlowy token dostepu.") from exc

user = self.user_repository.get_by_id(user_uuid)
```

(Uwaga: diff pokazuje też normalizację końcówek linii CRLF→LF w tym pliku.)

---

## Utworzony commit

| Pole | Wartość |
|------|---------|
| **Utworzono commit** | **TAK** |
| **Hash** | `f5215b0984dfc12b416e5057713ea8382940c0fd` |
| **Krótki hash** | `f5215b0` |
| **Message** | `fix(auth): map invalid JWT sub to 401 instead of HTTP 500` |

### Dokładna lista plików w commicie

1. `app/services/auth_service.py`
2. `docs/reports/2026-07-08_GWO-IFG-0042_TRANSMISSIONS_HTTP500_FIX.md`
3. `tests/unit/test_auth_service.py`

Potwierdzenie: `git show --name-only -1` — wyłącznie powyższe 3 pliki.

---

## Wynik testów (po commicie)

```bash
.venv/bin/python -m pytest tests/unit/test_auth_service.py
# 10 passed

.venv/bin/python -m pytest tests/unit/test_transmission_api.py tests/unit/test_transmission_service.py
# 44 passed
```

**Łącznie: 54/54 PASS**

---

## Pozostały dirty tree (po commicie)

Pliki GWO-0042 **nie są już** w dirty tree (zacommitowane).

Nadal zmodyfikowane względem HEAD (`f5215b0`):

- `app/persistence/mappers/invoice_mapper.py`
- `app/persistence/models/invoice.py`
- `app/persistence/repositories/transmission_repository.py`
- `app/services/invoice_number_policy.py`
- `app/services/payment_service.py`
- `frontend-react/src/api/invoices.js`
- `frontend-react/src/components/invoice/InvoiceActions.jsx`
- `frontend-react/vite.config.js`
- `pyproject.toml`
- `scripts/ds723.env`
- `scripts/ifg_guardian/**` (22 pliki modified)
- `tests/unit/test_guardian_*.py` (3 pliki)

Dodatkowo: **~126 plików untracked** (głównie `docs/**`, Guardian experiments, raporty).

**Podsumowanie:** 31 modified + 126 untracked (bez plików z commita hotfixu).

---

## Rekomendacja: czy można ponowić GWO-0043?

**TAK — warunkowo.**

| Aspekt | Ocena |
|--------|-------|
| Izolacja hotfixu w git | ✅ Commit `f5215b0` zawiera wyłącznie scope GWO-0042 |
| Deploy backend-only | ✅ Możliwy deploy samego commita `f5215b0` (push + rebuild api) |
| Guardian dirty-tree gate | ⚠️ Lokalny working tree nadal dirty — Guardian może zablokować deploy z Maca |
| Bezpieczna ścieżka | Push `f5215b0` → deploy z czystego stanu na serwerze lub scoped deploy z jawnym targetem commita |

**Rekomendacja operacyjna:**

1. `git push origin production` (tylko jeśli operator zatwierdza push całego brancha z nowym commitem).
2. Ponowić **GWO-IFG-0043** z deployem **backend-only** commita `f5215b0`.
3. Guardian: użyć deploy scope `backend-auth-hotfix` lub `--allow-dirty-build` świadomie, jeśli deploy uruchamiany lokalnie przy pozostałym dirty tree (zgodnie z GWO-IFG-0044).
4. Po deploy: wymusić logout/login użytkowników (odświeżenie JWT w LocalStorage).

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Izolowany commit hotfixu GWO-0042 utworzony (`f5215b0`).
- Scope commita: dokładnie 3 wymagane pliki.
- Testy auth + transmissions: 54/54 PASS.
- Pozostałe zmiany working tree nietknięte.

### ⚠️ Znane problemy

- Working tree nadal dirty (31 M + 126 ??) — może blokować Guardian deploy z lokalnej maszyny.

### ❌ Co nie działa

- Brak — izolacja zakończona pomyślnie.

---

## A. Root cause (dlaczego izolacja była potrzebna)

GWO-0043 zatrzymał deploy, bo dirty tree nie pozwalał na bezpieczne wdrożenie. GWO-0045 rozdziela hotfix od pozostałych zmian przez dedykowany commit.

## B. Zmienione pliki (w tym zadaniu)

- `app/services/auth_service.py` (commit)
- `tests/unit/test_auth_service.py` (commit)
- `docs/reports/2026-07-08_GWO-IFG-0042_TRANSMISSIONS_HTTP500_FIX.md` (commit)
- `docs/reports/2026-07-08_GWO-IFG-0045_ISOLATE_0042_HOTFIX.md` (ten raport)

## C. Deploy

Nie wykonano (zgodnie z poleceniem).

## D. Testy

54/54 PASS po commicie.

## E. Następny krok

GWO-IFG-0043 (ponowienie): deploy commita `f5215b0` + runtime verification Monitora KSeF.

---

## Aktualizacja pre-push (weryfikacja względem `origin/production`)

Wykonane polecenia:

```bash
git log origin/production..HEAD --oneline
git log HEAD..origin/production --oneline
```

### Wynik 1: `git log origin/production..HEAD --oneline`

```
f5215b0 fix(auth): map invalid JWT sub to 401 instead of HTTP 500
876900f feat(guardian): GWO-IFG-0037 release engine quality
2fff98c fix(ksef): GWO-IFG-0036 monitor UI remnants
a8410f3 GWO-IFG-0036: fix KSeF monitor and production integrity policy
```

### Wynik 2: `git log HEAD..origin/production --oneline`

```
(brak wpisów)
```

### Jednoznaczne potwierdzenie

- Czy jedynym lokalnym commitem oczekującym na push jest `f5215b0`? **NIE**.
- Czy na branchu `production` istnieją inne lokalne commity niewysłane na `origin`? **TAK**.
- Liczba lokalnych commitów oczekujących na push: **4** (`f5215b0`, `876900f`, `2fff98c`, `a8410f3`).
