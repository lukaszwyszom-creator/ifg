# Plan sprzątania repo IFG — audyt decyzyjny

**Data audytu:** 2026-06-26  
**Autor:** audyt automatyczny + review architektury  
**Status:** PLAN ONLY — bez wykonania `rm` / `mv` / `git rm`  
**Poprzednie raporty:** `docs/REPO_HOUSEKEEPING_AUDIT_2026_06.md`, `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md`

---

## 1. Executive summary

Po sprintach IFG/Guardian (M1–M3 Platform, magazyn, KSeF) repo zawiera **~155 plików w docs/** (132 w root `docs/`, 23 w podkatalogach), **duplikaty dokumentacji incydentów** (`*DIAG*`, `*FIX*`, sprinty), **artefakty lokalne** (`__pycache__`, `.pytest_cache`, `dist/`, `.logs/`), oraz **trzy warstwy Guardiana** (legacy `guardian.py`, `ifg_guardian/`, `guardian_platform/`).

### Liczba kandydatów (205 pozycji)

| Klasyfikacja | Liczba | Udział |
|--------------|--------|--------|
| **DELETE** | 10 | 4% |
| **ARCHIVE** | 130 | 61% |
| **KEEP** | 33 | 15% |
| **REVIEW** | 32 | 15% |

*Uwaga: pliki w grupie `__pycache__` liczone jako 1 kandydat (68 katalogów, ~759 plików).*

### Wzorce w docs/ (132 pliki `.md` w root)

| Wzorzec | Pliki |
|---------|-------|
| `*FIX*` | 39 |
| `*DIAG*` | 12 |
| `*DEPLOY*` | 19 |
| `*IMPLEMENTATION*` | 14 |
| `*PROGRESS*` | 1 |
| `*SPRINT*` (Guardian) | 7 |

### Werdykt

**TAK — można przejść do dry-run cleanup** dla Fazy 0 (artefakty lokalne) i Fazy 1 (ARCHIVE docs).  
**NIE** dla Fazy 2 (DELETE skryptów / legacy testów) bez domknięcia review REVIEW (32 pozycji) i bez M4 entrypoint migration.

---

## 2. Zakres i ograniczenia

### W scope audytu
1. `docs/` · 2. `scripts/` · 3. `tests/` · 4. `scripts/guardian_platform/` · 5. `scripts/ifg_guardian/` · 6. `frontend-react/` · 7. `app/` · 8. `alembic/` · 9. root repo · 10. cache/logi/artefakty

### Poza scope (nie ruszać)
- Bazy danych, wolumeny, produkcja DS723+
- Migracje Alembic (apply/rollback)
- Działające entrypointy: `scripts/guardian.py`, `scripts/guardian2.py`, `python -m scripts.guardian_platform`
- `scripts/guardian_platform/core/` (core Platform)
- Profil IFG (`scripts/guardian_platform/profiles/ifg/`) — tylko opis problemów

### Klasyfikacja
| Etykieta | Znaczenie |
|----------|-----------|
| **DELETE** | Bezpieczne usunięcie (artefakt / deprecated / duplikat) |
| **ARCHIVE** | Przeniesienie do `docs/archive/2026-06/` — wartość historyczna |
| **KEEP** | Aktywny kod / kanoniczna dokumentacja |
| **REVIEW** | Wymaga decyzji człowieka przed akcją |

---

## 3. Docelowa struktura `docs/`

```
docs/
  README.md                          # mapa dokumentacji
  REPO_CLEANUP_PLAN.md               # ten raport
  architecture/
    WORKFLOW.md                      # po konsolidacji
    GUARDIAN_PLATFORM_ARCHITECTURE.md
  guardian/
    platform/                        # M1–M3, tests, workflow engine
    legacy/                          # guardian.py, ifg_guardian (do M4)
    operations/                      # deploy-check, sync, recovery
  ifg/
    backend/
    frontend/
  ksef/
    reference/                       # utrzymane docs operacyjne po review
  warehouse/
    WAREHOUSE_READY_AUDIT_2026_06.md
  mobile/
    IFGM_*.md                        # po weryfikacji aktualności
  operations/
    DS723_SUDO_DOCKER_SETUP.md
    migracja_mac_mini.md
    deploy-runbooks/
  reports/                           # bieżące raporty Guardian (auto-generowane)
  archive/
    2026-06/
      guardian/                      # sprinty, stare GUARDIAN_*, runtime reports
      guardian2/
      ksef/                          # incydenty *FIX*/*DIAG*
      warehouse/
      incidents/
      artifacts/                     # .patch, .xlsx, zipy
      worktree/                      # REPO_CLEANUP_PLAN_2026_06_26, housekeeping
  rules/
    rules_09_amount_formatting.md
```

**Migracja:** Faza 1 = `git mv` do `archive/2026-06/` (bez usuwania). Faza 2 = reorganizacja KEEP do podkatalogów + aktualizacja linków w README.

---

## 4. Największe ryzyka

| # | Ryzyko | Poziom | Mitigacja |
|---|--------|--------|-----------|
| 1 | Usunięcie `scripts/guardian.py` / `ifg_guardian/` przed M4 | **Krytyczne** | KEEP; 104 legacy testów |
| 2 | Usunięcie skryptów `repair_*` / `backfill_*` potrzebnych na prod | **Wysokie** | REVIEW + runbook w operations |
| 3 | Archiwizacja docs KSeF używanych jako runbook | **Średnie** | Review 16 docs REVIEW przed ARCHIVE |
| 4 | `frontend-react/dist/` w worktree — deploy bez rebuild | **Średnie** | Zawsze `npm run build` przed rsync |
| 5 | Duplikat architektury `GUARDIAN_V3_ARCHITECTURE` vs `_REVISED` | **Niskie** | Scal → 1 plik w architecture/ |
| 6 | `.guardian/workflows/` — utrata historii lokalnej sesji | **Niskie** | Backup przed czyszczeniem |
| 7 | Niezcommitowany WIP magazynu (git status) | **Wysokie** | Commit feature przed cleanup repo |
| 8 | `docs/zipy/ifg_repo_20260502.zip` (506 KB) — snapshot repo | **Niskie** | ARCHIVE; nie potrzebny na co dzień |

---

## 5. Audyt obszar po obszarze

### 5.1 Artefakty lokalne (cache, logi, build)

| Ścieżka | Klasyf. | Powód | Ryzyko | Akcja |
|---------|---------|-------|--------|-------|
| `**/__pycache__/` (68 dir, ~759 .pyc) | DELETE | Regenerowany bytecode | Niskie | Faza 0 dry-run |
| `.pytest_cache/` | DELETE | Cache testów | Niskie | Faza 0 |
| `ksef_backend.egg-info/` | DELETE | pip install artefact | Niskie | Faza 0 |
| `.DS_Store` | DELETE | macOS metadata | Niskie | Faza 0 |
| `frontend-react/dist/` | DELETE | Build artefact | Niskie | Faza 0 + rebuild |
| `frontend-react/node_modules/` | DELETE | npm deps | Niskie | Nie commitować |
| `tmp/*.html` | DELETE | Mockupy; tmp/ gitignored | Niskie | Faza 0 |
| `.logs/*.log` | DELETE | Dev logs ~3 MB | Niskie | Faza 0 |
| `doc/` + PNG | DELETE | Zły katalog (singular) | Niskie | PNG→archive, rm doc/ |
| `.guardian/workflows/` | REVIEW | Cache Platform | Średnie | .gitignore + opcjonalny purge |

### 5.2 `docs/` — podsumowanie

| Klasyf. | Liczba plików |
|---------|---------------|
| ARCHIVE | 129 |
| KEEP | 10 |
| REVIEW | 16 |

**Duplikaty / konflikty do review:**
- `GUARDIAN_V3_ARCHITECTURE.md` vs `GUARDIAN_V3_ARCHITECTURE_REVISED.md` — scalić
- `REPO_HOUSEKEEPING_AUDIT_2026_06.md` vs ten raport — archive poprzedni po akceptacji
- `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md` — plan worktree CRLF; superseded
- `docs/repo_audit.md` — sprawdzić vs `ifg repo audit` output

**Kanoniczne KEEP (10 + ten raport):**
- `GUARDIAN_PLATFORM_ARCHITECTURE.md`, `GUARDIAN_PLATFORM_TESTS.md`
- `GUARDIAN_IFG_PROFILE_M1/M2/M3_*.md`
- `GUARDIAN_V1_RELEASE.md`, `GUARDIAN_WORKFLOW_ENGINE.md`
- `IFG_GUARDIAN_SYNC_REPORT.md`, `GUARDIAN_DEPLOY_CHECK.md`
- `WAREHOUSE_READY_AUDIT_2026_06.md`

**Pliki 0 B w repo (poza node_modules):** `app/integrations/nbp/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py` — **KEEP** (prawidłowe puste `__init__.py`).

### 5.3 `scripts/`

| Ścieżka | Klasyf. | Powód | Ryzyko | Akcja |
|---------|---------|-------|--------|-------|
| `guardian.py`, `guardian2.py` | KEEP | Aktywne entrypointy | Wysokie | Do M4 |
| `ifg_guardian/` (97 pl.) | KEEP | Legacy + testy | Wysokie | Do M4 |
| `guardian_platform/` (90 pl.) | KEEP | Platform M1–M3 | Wysokie | — |
| `deploy-ds723.sh`, `deploy_prod.sh` | KEEP | Deploy DS723+ | Wysokie | operations/ |
| `deploy_ds723.sh` | DELETE | Deprecated wrapper | Niskie | Po grep |
| `ksef_metadata_probe.py`, `test_ksef_auth.py` | REVIEW | Diagnostyka KSeF | Średnie | scripts/dev/ |
| `repair_*.py`, `backfill_*.py` | REVIEW | Ops jednorazowe | Wysokie | Runbook |
| `seed_*.py`, `export_invoices_xlsx.py` | KEEP/REVIEW | Dev/eksport | Niskie | KEEP |

### 5.4 `scripts/guardian_platform/` (≠ root `guardian_platform/`)

Brak katalogu `guardian_platform/` w root — platforma lives under `scripts/guardian_platform/`.

| Element | Klasyf. | Akcja |
|---------|---------|-------|
| `core/` | KEEP | Nie ruszać (constraint) |
| `profiles/ifg/` | KEEP | Profil produkcyjny |
| `profiles/psag_scaffold/` | KEEP | Aktywny w `.guardian.yml` |
| `profiles/ifg_scaffold/` | REVIEW | Usunąć jeśli martwy |

### 5.5 `scripts/ifg_guardian/`

Całość: **KEEP** — wymagane do M4 entrypoint migration; 97 modułów; duplikuje część logiki Platform (świadomy dług techniczny).

### 5.6 `tests/`

| Element | Testy | Klasyf. | Uwagi |
|---------|-------|---------|-------|
| `tests/guardian_platform/` | 223 | KEEP | Kanoniczna suite |
| `tests/unit/test_guardian_*.py` | 8 plików (~104 testy legacy) | REVIEW | Duplikat do M4 |
| `tests/unit/` (pozostałe) | ~70 plików | KEEP | Aplikacja IFG |
| `tests/e2e_mvp.py` | 1 | REVIEW | CI? |

**Duplikaty testów (świadome, nie bug):** doctor, repo_audit, deploy_run, workflow_engine — testowane w obu suite do migracji M4.

### 5.7 `frontend-react/`

| Ścieżka | Klasyf. | Akcja |
|---------|---------|-------|
| `src/` | KEEP | — |
| `dist/` | DELETE | Artefakt build |
| `node_modules/` | DELETE | Regenerowany |
| `package.json`, `vite.config.js` | KEEP | — |

### 5.8 `app/` + `alembic/`

| Ścieżka | Klasyf. | Akcja |
|---------|---------|-------|
| `app/` (committed) | KEEP | Brak cleanup |
| Warehouse WIP (untracked) | REVIEW | Commit przed cleanup |
| `alembic/versions/` (25 migracji) | KEEP | Constraint — nie ruszać |

### 5.9 Root repo

| Plik/katalog | Klasyf. | Akcja |
|--------------|---------|-------|
| `README.md`, `.guardian.yml` | KEEP | — |
| `agent/`, `local_ai/` | REVIEW | tools/ lub archive |
| `mobile-expo/` | KEEP | docs/mobile/ |
| `docker/`, `pyproject.toml` | KEEP | — |
| `.cursorignore` | REVIEW | Commit? |

---

## 6. Plan fazowy (do dry-run)

### Faza 0 — Artefakty lokalne (DELETE, bez commita)
```bash
# DRY-RUN — tylko listowanie
find . -name '__pycache__' -not -path './.venv*/*' -not -path './node_modules/*' -print
find . -name '.DS_Store' -print
ls -la frontend-react/dist/ .pytest_cache/ ksef_backend.egg-info/ .logs/
```
Po akceptacji: usuń cache/dist/logs lokalnie. **Zero zmian w git.**

### Faza 1 — ARCHIVE docs (commit `git mv`)
1. Utwórz `docs/archive/2026-06/{guardian,ksef,warehouse,incidents,artifacts,worktree}/`
2. Przenieś 130 pozycji ARCHIVE (+ podkatalogi guardian/reports/guardian2/zipy)
3. Zostaw 11 KEEP w root docs/ (tymczasowo)
4. Zaktualizuj `.guardian.yml` `reports_dir` jeśli potrzeba

### Faza 2 — REORGANIZACJA KEEP
1. Przenieś kanoniczne docs do `architecture/`, `guardian/platform/`, `operations/`
2. Scal duplikaty V3 architecture
3. IFGM docs → `mobile/` po review

### Faza 3 — REVIEW resolution (przed DELETE)
1. `repair_*`, `backfill_*`, probes → `scripts/dev/` lub archive
2. `deploy_ds723.sh` → DELETE
3. `ifg_scaffold` → DELETE jeśli martwy
4. Legacy `test_guardian_*.py` → po M4

### Faza 4 — Opcjonalnie agent/local_ai
Decyzja produktowa: KEEP w `tools/` vs ARCHIVE.

---

## 7. Dry-run checklist

- [ ] `git status` — commit/stash warehouse WIP
- [ ] `pytest tests/guardian_platform/ -q` — 223 green
- [ ] `pytest tests/unit/test_guardian*.py -q` — 104 green
- [ ] Faza 0: dry-run find (bez rm)
- [ ] Faza 1: `git mv` docs → archive (pojedynczy commit)
- [ ] Grep linków do przeniesionych docs w README / .cursor/rules
- [ ] `python3 -m scripts.guardian_platform ifg doctor --dry-run`
- [ ] Deploy check: dist rebuild po Faza 0

---

## 8. Appendix A — pełna lista `docs/` (155 plików)

| Ścieżka | Klasyf. | Powód | Ryzyko | Rekomendowana akcja |
|---------|---------|-------|--------|---------------------|
| `docs/DS723_DEPLOYMENT_CHECKLIST.md` | REVIEW | Dokument bez jednoznacznej klasyfikacji | Średnie | Ręczna weryfikacja |
| `docs/DS723_SUDO_DOCKER_SETUP.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/FV_GROSS_PRICE_CALCULATION_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/FV_LAYOUT_AND_BANK_ACCOUNT_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/FV_NUMBERING_RENUMBERING_BUG.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/FV_WZ_AUTO_SYNC_ANALYSIS.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/GUARDIAN2_DEPLOY.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/GUARDIAN2_RECOVERY_DS723.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/GUARDIAN_CORE_PROFILE_SPLIT.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_CRLF_CLASSIFICATION.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_DEPLOY_CHECK.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_DEPLOY_ORCHESTRATOR.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_FRONTEND_BUILD_CHECK.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_IFG_PROFILE_M1_READONLY.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_IFG_PROFILE_M2_NATIVE.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_IFG_PROFILE_M3_MUTATING.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_PLATFORM_ARCHITECTURE.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_PLATFORM_CORE_IMPLEMENTATION.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/GUARDIAN_PLATFORM_TESTS.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_PRICE_MODE_RESTORE.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_PZ_DRAFT_DEPLOY_DIAG.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/GUARDIAN_SPRINT1_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_SPRINT2_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_SPRINT3_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_SPRINT4_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_SPRINT5A_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_SPRINT5B_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_SPRINT5C_IMPLEMENTATION.md` | ARCHIVE | Raport sprintu Guardiana (historyczny) | Niskie | → docs/archive/2026-06/guardian/sprints/ |
| `docs/GUARDIAN_V1_RELEASE.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_V3_ARCHITECTURE.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_V3_ARCHITECTURE_REVISED.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/GUARDIAN_WORKFLOW_ENGINE.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/GUARDIAN_WORKTREE_CLEANUP_PZ_PRICE_MODE.md` | ARCHIVE | Stara dokumentacja Guardiana (pre-Platform M3) | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/IFGM_404_FIX_REPORT.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/IFGM_API_REQUIREMENTS_V1.md` | REVIEW | Spec mobile — sprawdzić vs mobile-expo/ | Średnie | → docs/mobile/ jeśli aktualne |
| `docs/IFGM_BACKEND_GAP_ANALYSIS_V1.md` | REVIEW | Spec mobile — sprawdzić vs mobile-expo/ | Średnie | → docs/mobile/ jeśli aktualne |
| `docs/IFGM_MOBILE_BACKEND_ENDPOINT_REPORT.md` | REVIEW | Spec mobile — sprawdzić vs mobile-expo/ | Średnie | → docs/mobile/ jeśli aktualne |
| `docs/IFGM_P1_1_IMPLEMENTATION.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/IFGM_PHU_BER_INVOICE_ITEMS_DIAGNOSIS.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/IFGM_PILOT_DEPLOYMENT_PLAN.md` | REVIEW | Spec mobile — sprawdzić vs mobile-expo/ | Średnie | → docs/mobile/ jeśli aktualne |
| `docs/IFGM_SPEC_V1.md` | REVIEW | Spec mobile — sprawdzić vs mobile-expo/ | Średnie | → docs/mobile/ jeśli aktualne |
| `docs/IFGM_USER_FLOW_V1.md` | REVIEW | Spec mobile — sprawdzić vs mobile-expo/ | Średnie | → docs/mobile/ jeśli aktualne |
| `docs/IFG_GUARDIAN_SYNC_REPORT.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/KK_CREATION_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KK_DETAIL_UI_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_ASYNC_SYNC_E2E_DIAGNOSTIC.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_ASYNC_SYNC_STATE_ALIGNMENT.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_BANK_ACCOUNT_DATA_LINEAGE_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_BANK_ACCOUNT_XML_DIAG_2026_06.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_BANK_ACCOUNT_XML_VERIFY_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_CONNECT_BUTTON_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_EMPTY_SYNC_HANDLING.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_FA3_SALE_DATE_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_FORCE_ASYNC_PURCHASE_SYNC.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_METADATA_PAGINATION_FIX_2026_06_23.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_METADATA_PAGINATION_ROOT_CAUSE.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_METADATA_PROBE.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_METADATA_PROBE_COMMANDS_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_MISSING_PURCHASES_AFTER_2026_06_05.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_OFFICIAL_API_AUDIT_2026-06-10.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PAGINATION_COMMIT_STATE.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PERMANENTSTORAGE_VS_INVOICING_TEST.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_POLL_SESSION_LOOKUP_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PROD_PURCHASE_SYNC_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PROD_RESUME_RETEST_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PROD_SYNC_VERIFICATION_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PURCHASE_API_INVESTIGATION.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PURCHASE_DIAGNOSTICS.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_INVOICE_NUMBER_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_ITEMS_ZERO_REPAIR.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_METADATA_50_LIMIT_DIAG_2026_06_23.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_METADATA_PAGINATION_FIX_2026_06.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_MISSING_INVOICES_ROOT_CAUSE.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_NO_NEW_INVOICES_DIAG_2026_06.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_ADD_ISSUE_DATE_2026_06_23.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PURCHASE_SYNC_BROKEN_DIAG_2026_06.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_MANUAL_VS_INCREMENTAL.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PURCHASE_SYNC_METADATA_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_METADATA_P0_PATCH.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_PATCH_CHECK.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_PROGRESS_DIAG.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_RESUME_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_SYNC_V1.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_PURCHASE_TOTALS_ZERO_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_PURCHASE_TOTALS_ZERO_FIX_IMPLEMENTATION.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_RATE_LIMIT_429_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_RESUME_AUDIT_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_RESUME_DEPLOY_READY_2026_06.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_RESUME_VERIFICATION.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_RETRYABLE_STATUS_STUCK_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_SYNC_PURCHASE_REQUEST_BODY_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_SYNC_REFRESH_UX_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_SYNC_TRIGGER_AND_PURCHASE_UI_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/KSEF_WORKER_QUEUE_BLOCKING_ANALYSIS.md` | ARCHIVE | Dokumentacja incydentu / sync KSeF | Niskie | → docs/archive/2026-06/ksef/ |
| `docs/KSEF_WORKER_QUEUE_BLOCKING_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/MOBILE_UI_PENPOT.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/PURCHASE_PDF_BANK_ACCOUNT_FIX_2026_06_24.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_CARTOTEKA_FV_PRICE_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_DRAFT_AS_REAL_STOCK_ANALYSIS.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/PZ_DRAFT_DEPLOY_STAGE2_DIAG.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/PZ_DRAFT_EDIT_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_DRAFT_EDIT_FIX_DEPLOY_REPORT.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_DRAFT_IMPLEMENTATION_AUDIT_2026_06.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_DRAFT_IMPLEMENTATION_REPORT.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/REPO_HOUSEKEEPING_AUDIT_2026_06.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/SALE_FA3_P11A_REJECTION_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/SALE_INVOICE_NUMBER_LOCAL_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/SALE_INVOICE_NUMBER_LOCAL_FIX_DEPLOY_STATUS.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/SUGGESTED_SALE_PRICE_MODE_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/UI_DEPLOY_DIAG_2026_06_19.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_BALANCE_AVERAGE_PRICE_UI_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_BALANCE_COST_PENDING_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_BALANCE_DEPLOY_STATE_DIAG.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_BALANCE_GROUP_BY_PRICE_DEPLOY.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/WAREHOUSE_BALANCE_GROUP_BY_PRICE_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_DOCUMENTS_ITEM_COLUMN_DEPLOY.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/WAREHOUSE_DOCUMENTS_ITEM_COLUMN_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_DOCUMENT_LIST_QTY_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WAREHOUSE_READY_AUDIT_2026_06.md` | KEEP | Dokumentacja kanoniczna Guardian Platform / profil IFG | Brak | Przenieść do docs/guardian/ w fazie 2 |
| `docs/WAREHOUSE_STOCK_AGGREGATION_UI_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WIP_DIFF_BEFORE_KSEF_ITEMS_FIX_20260612.patch` | ARCHIVE | Artefakt incydentu (patch / eksport) | Niskie | → docs/archive/2026-06/artifacts/ |
| `docs/WIP_STATUS_BEFORE_KSEF_ITEMS_FIX_20260612.txt` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WORKER_PENDING_JOBS_NOT_CLAIMED_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WORKFLOW.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/WZ_CREATION_BUG.md` | ARCHIVE | Dokumentacja feature/fix magazynu lub FV | Niskie | → docs/archive/2026-06/warehouse/ |
| `docs/WZ_CREATION_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/WZ_DETAIL_UI_FIX.md` | ARCHIVE | Dokument zamkniętego incydentu / fix | Niskie | → docs/archive/2026-06/incidents/ |
| `docs/guardian/IFG_DEPLOY_RUN_2026_06_26.md` | ARCHIVE | Raport runtime / analiza w docs/guardian/ | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/guardian/IFG_DOCTOR_2026_06_26.md` | ARCHIVE | Raport runtime / analiza w docs/guardian/ | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/guardian/IFG_RELEASE_PLAN_2026_06_26.md` | ARCHIVE | Raport runtime / analiza w docs/guardian/ | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/guardian/REPO_AUDIT_2026_06_26.md` | ARCHIVE | Raport runtime / analiza w docs/guardian/ | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md` | ARCHIVE | Raport runtime / analiza w docs/guardian/ | Niskie | → docs/archive/2026-06/guardian/ |
| `docs/guardian2/FRONTEND_DEPLOY_GUARD.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/FRONTEND_DIST_DEPLOY_VALIDATION.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/KSEF_PURCHASE_NUMBERING_AUDIT.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/PURCHASE_NUMBER_TRUNCATION_UI.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/PURCHASE_SELLER_TOOLTIP_UI.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/PURCHASE_TABLE_LAYOUT_REBALANCE.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/PURCHASE_UI_NUMBERING_PRODUCTION_ANALYSIS.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/guardian2/SEQUENCE_NUMBER_VALIDATION.md` | ARCHIVE | Raport runtime / analiza w docs/guardian2/ | Niskie | → docs/archive/2026-06/guardian2/ |
| `docs/invoices_export.xlsx` | ARCHIVE | Artefakt incydentu (patch / eksport) | Niskie | → docs/archive/2026-06/artifacts/ |
| `docs/migracja_mac_mini.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/repo_audit.md` | REVIEW | Operacyjna / architektoniczna — wymaga konsolidacji | Średnie | Scalić lub archive po review |
| `docs/reports/guardian_deploy_20260626_2026.md` | ARCHIVE | Raport runtime / analiza w docs/reports/ | Niskie | → docs/archive/2026-06/reports/ |
| `docs/reports/guardian_deploy_20260626_2027.md` | ARCHIVE | Raport runtime / analiza w docs/reports/ | Niskie | → docs/archive/2026-06/reports/ |
| `docs/reports/guardian_recover_20260626_2026.md` | ARCHIVE | Raport runtime / analiza w docs/reports/ | Niskie | → docs/archive/2026-06/reports/ |
| `docs/reports/guardian_recover_20260626_2027.md` | ARCHIVE | Raport runtime / analiza w docs/reports/ | Niskie | → docs/archive/2026-06/reports/ |
| `docs/reports/guardian_recover_20260626_2028.md` | ARCHIVE | Raport runtime / analiza w docs/reports/ | Niskie | → docs/archive/2026-06/reports/ |
| `docs/rules/rules_09_amount_formatting.md` | REVIEW | Dokument bez jednoznacznej klasyfikacji | Średnie | Ręczna weryfikacja |
| `docs/zipy/ifg_repo_20260502_230915.zip` | ARCHIVE | Raport runtime / analiza w docs/zipy/ | Niskie | → docs/archive/2026-06/zipy/ |

---

## 9. Appendix B — pozostałe kandydaci (poza docs/)

| Ścieżka | Klasyf. | Powód | Ryzyko | Rekomendowana akcja |
|---------|---------|-------|--------|---------------------|
| `**/__pycache__/ (68 katalogów, ~759 plików .pyc)` | DELETE | Bytecode Python; regenerowany; w .gitignore | Niskie | Usunąć lokalnie (dry-run: find … -print) |
| `.pytest_cache/` | DELETE | Cache pytest | Niskie | rm -rf .pytest_cache |
| `ksef_backend.egg-info/` | DELETE | Artefakt pip install -e . | Niskie | rm -rf ksef_backend.egg-info |
| `.DS_Store (root i podkatalogi)` | DELETE | Metadane macOS; w .gitignore | Niskie | find . -name .DS_Store -delete |
| `frontend-react/dist/ (12 plików)` | DELETE | Build frontend; odtwarzalny | Niskie | rm -rf + npm run build przed deployem |
| `frontend-react/node_modules/` | DELETE | Zależności npm; odtwarzalne | Niskie | npm ci — nie commitować |
| `tmp/*.html (2 mockupy)` | DELETE | Mockupy UI; tmp/ w .gitignore | Niskie | rm tmp/*.html |
| `.logs/*.log (~3 MB)` | DELETE | Lokalne logi dev-bootstrap | Niskie | truncate / rm |
| `doc/ (katalog + 1 PNG)` | DELETE | Pomyłkowy singular doc/; docs/ jest kanoniczne | Niskie | Archiwizuj PNG → usuń doc/ |
| `scripts/deploy_ds723.sh` | DELETE | Deprecated wrapper → deploy-ds723.sh | Niskie | Usunąć po grep referencji |
| `.guardian/workflows/ (151 plików)` | REVIEW | Lokalny cache workflow Platform | Średnie | Dodać .guardian/ do .gitignore; wyczyścić lokalnie |
| `.guardian/latest/` | REVIEW | Ostatni stan workflow | Średnie | KEEP lokalnie; nie commitować |
| `scripts/guardian.py` | KEEP | Legacy entrypoint; M4 pending | Wysokie | Nie usuwać |
| `scripts/guardian2.py` | KEEP | Deploy/recovery DS723+ | Wysokie | Nie usuwać |
| `scripts/ifg_guardian/ (97 plików)` | KEEP | Legacy Guardian + 104 testy | Wysokie | Archiwizacja dopiero po M4 |
| `scripts/guardian_platform/ (90 plików)` | KEEP | Guardian Platform + profil IFG M1–M3 | Wysokie | docs/guardian/platform/ |
| `scripts/guardian_platform/profiles/ifg_scaffold/` | REVIEW | Scaffold; możliwa redundancja vs profiles/ifg/ | Niskie | Usunąć po potwierdzeniu braku użycia |
| `scripts/guardian_platform/profiles/psag_scaffold/` | KEEP | Aktywny profil w .guardian.yml | Średnie | Zachować |
| `scripts/deploy-ds723.sh` | KEEP | Główny skrypt deploy DS723+ | Wysokie | docs/operations/ |
| `scripts/deploy_prod.sh` | KEEP | Deploy produkcyjny | Wysokie | docs/operations/ |
| `scripts/preflight-ds723.sh` | KEEP | Preflight deploy | Średnie | Zachować |
| `scripts/healthcheck.sh` | KEEP | Healthcheck kontenerów | Średnie | Zachować |
| `scripts/smoke_test.sh` | KEEP | Smoke test | Średnie | Zachować |
| `scripts/test-ifg.sh` | KEEP | Test runner IFG | Średnie | Zachować |
| `scripts/logs-api.sh` | KEEP | Ops: logi API | Niskie | Zachować |
| `scripts/logs-worker.sh` | KEEP | Ops: logi worker | Niskie | Zachować |
| `scripts/open_login.sh` | KEEP | Ops: otwarcie loginu | Niskie | Zachować |
| `scripts/ksef_metadata_probe.py` | REVIEW | Probe diagnostyczny KSeF | Średnie | → scripts/dev/ lub archive |
| `scripts/test_ksef_auth.py` | REVIEW | Probe auth KSeF | Średnie | → scripts/dev/ lub archive |
| `scripts/repair_purchase_items_from_ksef.py` | REVIEW | Jednorazowa naprawa danych | Wysokie | Runbook w docs/operations/ |
| `scripts/repair_purchase_totals_from_items.py` | REVIEW | Jednorazowa naprawa danych | Wysokie | Runbook w docs/operations/ |
| `scripts/backfill_pz_draft_layers.py` | REVIEW | Backfill magazyn; ma test unit | Średnie | KEEP jeśli prod potrzebuje |
| `scripts/seed_demo_april_2026.py` | REVIEW | Seed demo | Niskie | KEEP dla dev/demo |
| `scripts/seed_monthly_invoices.py` | REVIEW | Seed; ma test unit | Niskie | KEEP |
| `scripts/export_invoices_xlsx.py` | KEEP | Eksport; ma test unit | Niskie | Zachować |
| `tests/guardian_platform/ (223 testy, 14 plików)` | KEEP | Kanoniczna suite Platform | Wysokie | Zachować |
| `tests/unit/test_guardian_*.py (8 plików)` | REVIEW | Legacy Guardian; duplikat do M4 | Średnie | Usunąć po M4 |
| `tests/e2e_mvp.py` | REVIEW | E2E MVP — brak w guardian_platform/ | Średnie | KEEP lub tests/e2e/ |
| `tests/unit/ (~70 plików pozostałych)` | KEEP | Testy aplikacji IFG | Wysokie | Zachować |
| `app/ (backend IFG)` | KEEP | Kod produkcyjny | Wysokie | Brak cleanup kodu |
| `app/** (untracked warehouse WIP w git status)` | REVIEW | Feature magazyn niezcommitowany | Wysokie | Commit/stash — poza cleanup |
| `alembic/ + alembic/versions/ (25 migracji)` | KEEP | Constraint: nie ruszać migracji | Wysokie | KEEP |
| `frontend-react/src/` | KEEP | Kod frontendu | Wysokie | KEEP |
| `mobile-expo/` | KEEP | Aplikacja mobilna IFGM | Średnie | docs/mobile/ |
| `agent/ (12 plików)` | REVIEW | Lokalny agent diagnostyczny v1 | Niskie | tools/agent/ lub archive |
| `local_ai/ask_ifg.py` | REVIEW | Helper AI bez README/CI | Niskie | archive lub scripts/dev/ |
| `README.md` | KEEP | Entrypoint repo | Niskie | Zaktualizować linki po reorganizacji |
| `.guardian.yml` | KEEP | Konfiguracja Platform | Wysokie | KEEP |
| `.cursorignore` | REVIEW | Nieśledzony plik | Niskie | Commit lub .gitignore |
| `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md` | ARCHIVE | Poprzedni plan worktree; zastąpiony tym raportem | Niskie | → docs/archive/2026-06/guardian/ |

---

## 10. Podsumowanie końcowe

| Metryka | Wartość |
|---------|---------|
| Kandydaci łącznie | **205** |
| DELETE | **10** |
| ARCHIVE | **130** |
| KEEP | **33** |
| REVIEW | **32** |
| Pliki docs | 155 |
| __pycache__ dirs | 68 |
| Guardian Platform tests | 223 |
| Legacy Guardian tests | 104 |

**Rekomendacja:** Rozpocznij od **Fazy 0 dry-run** (artefakty lokalne, zero git diff), następnie **Faza 1** (ARCHIVE 130 pozycji docs) jako jeden reviewable commit. Pozycje REVIEW (32) wymagają 1–2h review przed Fazą 3.
