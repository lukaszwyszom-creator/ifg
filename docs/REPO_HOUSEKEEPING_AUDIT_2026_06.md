# Repo housekeeping audit — IFG Guardian (2026-06-26)

**Cel:** ustalić, czy istnieje projektowe narzędzie do audytu/porządkowania repo zamiast ręcznego sprzątania w Cursorze.  
**Kod:** bez zmian — tylko odczyt i raport.

---

## 1. Co istnieje w repo

| Plik | Rola |
|------|------|
| `scripts/guardian.py` | Guardian MVP — read-only audyt API, deploy, repo sync, frontend dist |
| `scripts/guardian2.py` | Deploy/recovery DS723+ (commit allowlist, build, SSH) — **nie** housekeeping |
| `docs/IFG_GUARDIAN_SYNC_REPORT.md` | Dokumentacja `--repo-sync` |
| `docs/GUARDIAN_DEPLOY_CHECK.md` | Dokumentacja `--deploy-check` |
| `docs/GUARDIAN_WORKTREE_CLEANUP_PZ_PRICE_MODE.md` | **Ręczna** procedura CRLF (git diff), nie skrypt |
| `.cursor/rules/rules_10_guardian.mdc` | Reguła: uruchamiaj Guardian przed deployem |

---

## 2. Mapowanie wymagań → Guardian (stan obecny)

| Wymaganie | Guardian obsługuje? | Jak |
|-----------|---------------------|-----|
| Repo status / audit | **Częściowo** | `--repo-sync` (branch, HEAD, ahead/behind, dirty) |
| Wykrywanie brudnego worktree | **Tak** | `--repo-sync`, `--deploy-check` (`git status --porcelain`) |
| Wykrywanie nieśledzonych plików | **Częściowo** | Porcelain `??` liczy się jako dirty; **brak klasyfikacji** commit/ignore/delete |
| CRLF / LF | **Nie** | Tylko ręcznie (`docs/GUARDIAN_WORKTREE_CLEANUP_*.md`) |
| `.gitignore` / `.gitattributes` | **Nie** | Brak dedykowanego checku |
| Deploy-blockery | **Tak** | `--deploy-check` (HEAD vs DS723+, dist vs src, kontenery) |
| Frontend wymaga builda | **Tak** | `--deploy-check`, `--ksef-async-check` (`check_frontend_*`) |
| Raport markdown | **Nie** | Tylko stdout; brak `--report` |

**Werdykt:** Guardian **nie ma** trybu `repo-housekeeping-audit`. Najbliższe są **3 osobne komendy** (poniżej).

---

## 3. Komendy do uruchomienia na Mac mini (dziś, bez zmian kodu)

```bash
cd /Users/lukasz/projekty/ifg_standalone

# 1) Sync repo: gałąź, ahead/behind, dirty (Mac mini + opcjonalnie DS723+)
python3 scripts/guardian.py --repo-sync --fetch
python3 scripts/guardian.py --repo-sync --fetch --remote ds723

# 2) Deploy-blockery: HEAD vs prod, dist vs src, kontenery
python3 scripts/guardian.py --deploy-check

# 3) Frontend/KSeF bundle check
python3 scripts/guardian.py --ksef-async-check
```

**Guardian2** (`python3 scripts/guardian2.py deploy-ksef --dry-run`) — deploy, nie housekeeping.

---

## 4. Snapshot worktree (2026-06-26, Mac mini)

### 4.1 Zmodyfikowane (`M`) — 14 plików

| Plik | Klasyfikacja | Uwagi |
|------|--------------|-------|
| `app/api/deps.py` | **CRLF-only** — nie commitować osobno | `git diff -w` pusty; `\r\n` w working copy |
| `app/domain/enums.py` | **CRLF-only** | j.w. |
| `app/persistence/mappers/invoice_mapper.py` | **CRLF-only** | j.w. |
| `app/persistence/models/invoice.py` | **CRLF-only** | j.w. |
| `app/persistence/repositories/transmission_repository.py` | **CRLF-only** | j.w. |
| `app/services/invoice_number_policy.py` | **CRLF-only** | j.w. |
| `app/services/payment_service.py` | **CRLF-only** | j.w. |
| `frontend-react/src/api/invoices.js` | **CRLF-only + wymaga build** | po commicie merytorycznym: `npm run build` |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | **CRLF-only + wymaga build** | j.w. |
| `frontend-react/vite.config.js` | **CRLF-only + wymaga build** | j.w. |
| `docs/KSEF_METADATA_PAGINATION_FIX_2026_06_23.md` | **Do commita** (jeśli zamierzone) | diff merytoryczny |
| `docs/KSEF_PURCHASE_SYNC_ADD_ISSUE_DATE_2026_06_23.md` | **Do commita** | diff merytoryczny |
| `docs/PURCHASE_PDF_BANK_ACCOUNT_FIX_2026_06_24.md` | **Do commita** | diff merytoryczny |
| `frontend-react/dist/index.html` | **Do ignorowania** | w `.gitignore`: `frontend-react/dist/` — nie powinno być śledzone |

### 4.2 Nieśledzone (`??`) — 36 plików

| Grupa | Pliki | Klasyfikacja |
|-------|-------|--------------|
| Raporty diag KSeF/PZ/warehouse (35× `docs/*.md`) | m.in. `KSEF_*`, `PZ_DRAFT_*`, `WAREHOUSE_*`, `FV_*` | **Do commita** (wybrane) lub **archiwum** — decyzja człowieka; nie ignorować globalnie |
| Test frontend | `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | **Do commita** (jeśli feature aktywny) |

**Uwaga:** `?? backups/` na DS723+ jest neutralne w `--repo-sync` (`_porcelain_is_dirty` pomija). Lokalnie brak `backups/`.

### 4.3 CRLF / LF

- `.gitattributes`: `* text=auto eol=lf`, `*.py/js/jsx/md text eol=lf`
- **10 plików `M`** to wyłącznie szum CRLF↔LF (`git diff -w` pusty)
- Procedura ręczna (bez Guardian): `docs/GUARDIAN_WORKTREE_CLEANUP_PZ_PRICE_MODE.md` → `git restore` po zgodzie

### 4.4 Frontend — wymaga builda po deployu

Zmiany w `frontend-react/src/` (3 pliki + test) → po merge/deploy na DS723+:

```bash
cd frontend-react && npm run build
```

Guardian `--deploy-check` wykryje rozjazd dist vs commit src.

---

## 5. Propozycja: minimalne rozszerzenie Guardiana

**Nowa flaga (tylko odczyt):**

```bash
python3 scripts/guardian.py --repo-housekeeping-audit [--report docs/REPO_HOUSEKEEPING_AUDIT_YYYY_MM.md]
```

**Implementacja:** jedna funkcja `run_repo_housekeeping_audit()` w `scripts/guardian.py` (~120–150 linii), bez nowych zależności.

| Krok | Źródło | Akcja |
|------|--------|-------|
| Status git | `git status --porcelain`, `branch`, `rev-parse` | istniejące `_git()` |
| Klasyfikacja `M` | `git diff -w --name-only` vs pełny diff | CRLF-only vs substantive |
| Klasyfikacja `??` | `Path.match` vs `.gitignore` + heurystyki (`docs/*_DIAG*.md`, `dist/`, `.env`) | commit / ignore / review |
| CRLF | `\r\n` w bytes + diff -w | lista podejrzanych |
| Frontend build | reuse `check_frontend_worktree_requires_build()`, `check_frontend_dist_freshness()` | deploy-blocker |
| Deploy | opcjonalnie wywołanie logiki z `--deploy-check` (bez SSH lub z `--remote-host`) | blocker summary |
| Raport | zapis markdown | **tylko zapis pliku**, bez git operacji |

**Zabronione w trybie:** `git restore`, `git clean`, `git commit`, `git push`, kasowanie plików.

**Szacunek diff:** 1 plik (`guardian.py`) + 1 krótki akapit w `docs/IFG_GUARDIAN_SYNC_REPORT.md`.

---

## 6. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy Guardian ma pełny housekeeping? | **Nie** |
| Co uruchomić teraz? | `--repo-sync --fetch`, `--deploy-check`, `--ksef-async-check` |
| Czy warto rozszerzyć? | **Tak** — tryb `--repo-housekeeping-audit` (read-only + raport MD) |
