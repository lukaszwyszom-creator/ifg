# Repository Target State — Standard zarządzania repozytoriami Guardian

**Status:** CANONICAL (docelowy standard)  
**Wersja:** 1.0-draft  
**Data:** 2026-07-06  
**Zakres:** wszystkie projekty Guardian (IFG, PSAG, kolejne)  
**Powiązane:** `docs/reports/2026-07-06_REPOSITORY_TARGET_STATE_DESIGN.md`

---

## 1. Cel i filozofia

Guardian jest **administratorem repozytorium i wdrożeń**, nie tylko wykonawcą poleceń SSH/Docker.

Standard definiuje:

1. **Jak** organizować kod, dokumentację i artefakty w repo.
2. **Jak** przepływać zmianami między branchami.
3. **Jak** wydawać wersje na produkcję z możliwością rollbacku.
4. **Jak** utrzymywać zdrowie repozytorium w czasie.
5. **Jak** Guardian automatycznie analizuje i doradza operatorowi.

> **Zasada nadrzędna:** `production` jest zawsze deployowalny. Wszystko inne jest przygotowaniem.

---

## 2. Struktura repozytorium

### 2.1 Drzewo katalogów (docelowe)

```
<project-root>/
├── app/                          # kod aplikacji (domena projektu)
├── frontend-*/                   # frontend(y) projektu
├── docker/                       # compose, obrazy
├── alembic/                      # migracje DB
├── scripts/
│   ├── guardian.py               # entrypoint CLI
│   └── <project>_guardian/       # profil operacyjny (np. ifg_guardian)
│       ├── core/                 # workflow, preflight, execution (profil)
│       └── plugins/              # workflow specyficzne dla projektu
├── tests/
├── docs/
│   ├── architecture/             # trwała architektura systemu
│   ├── standards/                # standardy operacyjne i developerskie
│   ├── runbooks/                 # procedury APPROVED (LIVE)
│   ├── specifications/           # specyfikacje funkcji (aktywne)
│   ├── decisions/                # ADR / decyzje architektoniczne
│   ├── reports/
│   │   ├── operational/          # deploy, recover, cutover (indeksowane)
│   │   ├── migrations/           # migracje infrastruktury
│   │   └── diagnostics/          # jednorazowe diagnozy
│   ├── templates/                # szablony raportów, runbooków
│   └── archive/                  # dokumenty zamknięte (read-only)
│       └── YYYY-MM/
├── .guardian.yml                 # konfiguracja profilu Guardian
├── .gitattributes                # EOL policy (LF)
└── .gitignore                    # generated + runtime
```

### 2.2 Rola katalogów dokumentacji

| Katalog | Rodzaj | Żywotność | Kto aktualizuje | W `production` |
|---------|--------|-----------|-----------------|------------------|
| `architecture/` | Kanoniczna | Wieloletnia | Architekt / ADR | ✅ |
| `standards/` | Kanoniczna | Wieloletnia | Guardian Canon | ✅ |
| `runbooks/` | Kanoniczna operacyjna | Do REVOKE | Operator + review | ✅ (tylko APPROVED) |
| `specifications/` | Projektowa | Do zamknięcia feature | Dev | ✅ gdy feature w prod |
| `decisions/` | ADR | Permanentna | Review | ✅ |
| `reports/operational/` | Raport operacyjny | Archiwizowalna | Guardian (auto) | ✅ (ostatni cykl) |
| `reports/migrations/` | Raport migracji | Archiwizowalna | Operator | ✅ po migracji |
| `reports/diagnostics/` | Jednorazowy | 90 dni → archive | Dev / Guardian | ❌ (po archiwizacji) |
| `templates/` | Szablony | Stabilna | Guardian | ✅ |
| `archive/` | Zamknięte | Read-only | Cleanup job | ✅ (historia) |

### 2.3 Artefakty runtime (poza Git)

| Artefakt | Lokalizacja | W Git |
|----------|-------------|-------|
| Transakcje workflow | `.guardian/workflows/` | ❌ |
| Ostatni snapshot | `.guardian/latest/` | ❌ |
| Raporty bieżące (generowane) | `docs/guardian/` lub `docs/reports/operational/` | ⚠️ tylko po review |
| Build frontend | `frontend-*/dist/` | ❌ |
| Env produkcyjny | `.env.production` | ❌ |
| Logi lokalne | `.logs/` | ❌ |

**Reguła:** Guardian zapisuje runtime do `.guardian/`. Promocja do `docs/reports/` wymaga świadomej akcji operatora lub workflow `release`.

---

## 3. Model branchy

### 3.1 Wybrany model: **Guardian Release Flow**

Hybryda Feature Branch + Release Branch + Production Trunk.

```
feature/<domain>-<topic>
        │
        ▼ (PR / merge when ready)
release/<YYYY-MM-DD>-<name>     ← integracja, QA, release plan
        │
        ▼ (approval + tag)
production                      ← DS723+ deploy target
        │
        └── tag: v<semver>      ← rollback anchor
```

**Odrzucone modele:**

| Model | Powód odrzucenia |
|-------|------------------|
| Git Flow (`develop`) | Zbyt ciężki dla małego zespołu; `main` już istnieje ale jest 76 commitów za `production` |
| GitHub Flow (tylko `main`) | Brak warstwy release; ryzyko bezpośredniego push na prod |
| Trunk Based (bez release) | Wymaga feature flags i CI na poziomie, którego IFG jeszcze nie ma |
| Tylko `main` + hotfix | Nie mapuje się na DS723+ `git pull` na `production` |

### 3.2 Definicje branchy

| Branch | Cel | Kto pushuje | Merge do |
|--------|-----|-------------|----------|
| `feature/*` | Rozwój funkcji, eksperymenty, WIP | Developer | `release/*` |
| `release/*` | Integracja, testy, release plan | Operator / Guardian | `production` |
| `production` | Stan faktycznie na DS723+ | Tylko po approval | — |
| `main` | **Docelowo:** mirror lub staging integracji | Po synchronizacji z `production` | — |

**Decyzja v1:** `production` pozostaje branch deployowy. `main` synchronizuje się z `production` po każdym release (nie odwrotnie).

### 3.3 Hotfix

```
production ──► hotfix/<id>-<topic> ──► production (fast-track)
                      │
                      └──► release/* (backport jeśli otwarty)
                      └──► feature/* (cherry-pick jeśli dotyczy)
```

Hotfix na `production` wymaga: tag, release notes, smoke test, Guardian `deploy check`.

---

## 4. Commit Policy

### 4.1 Format wiadomości

```
<type>(<scope>): <subject>

[optional body]

[optional footer: GWO-*, ADR-*, BREAKING]
```

**Typy:** `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `prep`, `revert`

**Scope:** domena (`guardian`, `ksef`, `warehouse`, `invoice`, `docker`, `ifg`)

### 4.2 Zasady wielkości

| Zasada | Opis |
|--------|------|
| **Atomowość logiczna** | Jeden commit = jeden temat (np. Preflight Engine, nie Preflight + Cutover + FV) |
| **Rozmiar** | Docelowo < 500 LOC diff; > 1000 LOC → podziel |
| **Testy** | Commit kodu bez testów dozwolony tylko na `feature/*`; na `release/*` i `production` wymagane testy |
| **Dokumentacja** | Runbook/ADR w tym samym release co kod, niekoniecznie w tym samym commicie |

### 4.3 Dozwolone i zabronione

| Akcja | `feature/*` | `release/*` | `production` |
|-------|-------------|-------------|--------------|
| WIP commit (`wip:`) | ✅ | ⚠️ tylko release branch | ❌ |
| Partial commit (`git add` ścieżki) | ✅ | ✅ | ✅ (preferowane) |
| Draft commit | ✅ | ❌ | ❌ |
| Squash merge | ✅ (feature→release) | ✅ | ❌ (zachowaj historię release) |
| Rebase feature | ✅ | ⚠️ przed merge | ❌ na production |
| Cherry-pick | ✅ | ✅ | ✅ (hotfix) |
| Revert | ✅ | ✅ | ✅ (preferowany rollback kodu) |
| `git commit -am` | ❌ | ❌ | ❌ |
| `git add .` | ❌ | ❌ | ❌ |

### 4.4 Rollback

1. **Infrastruktura:** Guardian workflow (`cutover rollback`, `prod recover`)
2. **Kod:** `git revert` na `production` + tag `v<x.y.z>-revert`
3. **Deploy:** poprzedni tag + `ifg deploy run` z znanym SHA

---

## 5. Release Management

### 5.1 Proces

```
feature/* ──merge──► release/<date>-<name>
                           │
                           ├── Guardian: ifg release plan
                           ├── Guardian: ifg doctor
                           ├── Guardian: repo audit / readiness
                           ├── pytest (unit + smoke)
                           ├── build frontend (jeśli zmieniony)
                           ├── review operatora
                           ├── approval (GO)
                           ├── merge → production
                           ├── tag vX.Y.Z
                           ├── release notes
                           ├── git push production + --tags
                           ├── DS723+: git pull
                           ├── Guardian: deploy run / cutover
                           └── smoke test produkcyjny
```

### 5.2 Checklist release (Guardian egzekwuje)

| # | Punkt | Guardian workflow |
|---|-------|-------------------|
| 1 | Working tree clean (local + remote) | `preflight` / `deploy check` |
| 2 | Na branchu `release/*` lub `production` | `git.branch` check |
| 3 | Doctor PASS | `ifg.doctor` |
| 4 | Release plan wygenerowany | `ifg.release.plan` |
| 5 | Testy PASS | `pytest` stage |
| 6 | Migracje Alembic ocenione | `release_plan.migration` |
| 7 | Frontend build świeży | `build_detector` |
| 8 | Brak mieszania tematów | Repository Intelligence |
| 9 | Approval operatora | `--yes` / Safety Gate GO |
| 10 | Tag + release notes | manual / Guardian helper |
| 11 | Deploy + smoke | `ifg.deploy.run` |
| 12 | Rollback point zapisany | transaction JSON |

### 5.3 Tagowanie

Format: `v<major>.<minor>.<patch>` (SemVer)

- **major:** breaking change (API, schema)
- **minor:** feature na production
- **patch:** hotfix

Tag tworzony na `production` po merge z `release/*`.

---

## 6. Repository Health

### 6.1 Definicja „clean"

| Obszar | Stan zdrowy |
|--------|-------------|
| `git status` (tracked) | Brak `M`, `D`, `A` poza świadomym partial staging |
| Untracked | Tylko pliki w `.gitignore` lub świadome WIP na `feature/*` |
| CRLF | Brak fałszywych `M` (`.gitattributes` + renormalize) |
| `dist/` | Nieśledzone (`git rm --cached` historycznych) |
| `.guardian/` | Ignorowane |
| Dokumentacja root `docs/*.md` | Przeniesione do podkatalogów |

### 6.2 Co może być na `production`

- Kod aplikacji w pełni działający
- Guardian workflows używane operacyjnie
- Runbooki APPROVED
- ADR i architektura
- Ostatnie raporty operacyjne (nie cała historia dry-runów)
- `docker-compose.prod.yml` i konfiguracja deploy

### 6.3 Co tylko na `feature/*`

- WIP kodu
- Eksperymenty
- Dokumentacja analiz i planów niewdrożonych
- `wip:` commity

### 6.4 Co ignorować (`.gitignore`)

```
.guardian/
.logs/
*.pyc, __pycache__/
.venv*/
frontend-*/dist/
.env
.env.production
.env.*.migration-test
.pytest_cache/
.DS_Store
```

### 6.5 Worktree

Dozwolone dla równoległej pracy bez stash:

```bash
git worktree add ../<project>_feature feature/<topic>
```

Guardian powinien wykrywać worktree i nie traktować ich jako „dirty production".

---

## 7. Klasy dokumentacji

### 7.1 Kanoniczne (źródło prawdy)

- `docs/architecture/`
- `docs/standards/` (w tym niniejszy dokument w `docs/guardian/core/`)
- `docs/runbooks/` (status: DRAFT | REVIEW | APPROVED | REVOKED)
- `docs/decisions/ADR-*.md`

### 7.2 Projektowe (żywot do wdrożenia)

- `docs/specifications/`
- Roadmapy w `docs/specifications/roadmap/`

### 7.3 Raporty

| Podklasa | Przykład | Retencja |
|----------|----------|----------|
| Operacyjny | `IFG_DEPLOY_RUN_*.md` | 12 mies. → archive |
| Migracja | `GWO_IFG_002*.md` | Permanentna po zamknięciu GWO |
| Diagnostyka | `KSEF_*_DIAG*.md` | 90 dni → archive |
| Audyt | `REPO_*_AUDIT*.md` | archive po wdrożeniu rekomendacji |

### 7.4 Archiwizacja

```
docs/archive/YYYY-MM/<original-path>
```

Guardian Cleanup Advisor (faza 2+) proponuje przeniesienie; operator zatwierdza.

---

## 8. Guardian jako administrator repo

### 8.1 Obowiązki

| Obszar | Komenda / workflow | Tryb |
|--------|-------------------|------|
| Dirty tree analysis | `repo audit` | read-only |
| Dependency grouping | Repository Intelligence | read-only |
| Commit plan proposal | `repo plan` (v3) | read-only |
| Release readiness | `ifg release plan` | read-only |
| Production readiness | `ifg doctor` + `preflight` | read-only |
| Deploy execution | `ifg deploy run` | mutating |
| Cutover | `ifg cutover run` | mutating |
| Rollback | `ifg cutover rollback` / `prod recover` | mutating |
| Doc compliance | `repo audit` extensions | read-only |
| Generated files control | `repo audit` classifier | read-only |
| Branch health | `deploy check` | read-only |

### 8.2 Warstwy Guardiana (docelowe)

```
┌─────────────────────────────────────────────┐
│  CLI (guardian.py)                          │
├─────────────────────────────────────────────┤
│  Profile Plugin (ifg, psag, …)              │
│  — workflows: doctor, release, deploy, …  │
├─────────────────────────────────────────────┤
│  Repository Intelligence (v3)               │
│  — classify, group, depend, advise          │
├─────────────────────────────────────────────┤
│  Guardian Core (frozen v1)                  │
│  — workflow engine, preflight, safety gate  │
├─────────────────────────────────────────────┤
│  Execution Backend                          │
│  — SSH, Docker, Compose, HTTP               │
└─────────────────────────────────────────────┘
```

---

## 9. Repository Intelligence (v3)

### 9.1 Wejście

- `git status --porcelain`
- `git diff --stat`
- Import graph (Python)
- Profile extension classifiers (IFG: invoice, ksef, warehouse, guardian)
- `.guardian.yml` rules

### 9.2 Wyjście (przykład)

```
Repository Intelligence Report
──────────────────────────────
Branch: production (⚠️ dirty — 17 tracked, 82 untracked)

Proposed commits (dependency order):

  1. feat(guardian): add Preflight Engine          [12 files]  ← no deps
  2. feat(guardian): add cutover workflow             [9 files]  ← depends: 1
  3. feat(guardian): add execution backend           [15 files]  ← optional
  4. docs(ifg): cutover runbook and GWO reports      [10 files]  ← depends: 2
  5. chore: gitignore guardian runtime                [2 files]  ← depends: 4

Isolate to feature/ksef-transmission-wip:
  - app/persistence/repositories/transmission_repository.py  [WIP, incomplete]

Ignore (generated):
  - .guardian/workflows/*  (287 files)

Release readiness: NO-GO (dirty tree, cutover not in HEAD)
```

### 9.3 Reguły wykrywania

| Sygnał | Detekcja |
|--------|----------|
| Mieszanie tematów | > 2 scope w jednym diff |
| CRLF-only | `line_ending_analysis` (istnieje) |
| Build artifact | path `dist/`, hash change only |
| Niedokończona funkcja | brak testów + TODO/FIXME + WIP scope |
| Zależność commitów | import graph + profile rules |
| Ryzyko production | mutating paths bez runbook |

---

## 10. Uniwersalność (IFG → PSAG → kolejne)

### 10.1 Wspólne (Guardian Core + Platform)

- Struktura `docs/` (§2)
- Model branchy (§3)
- Commit policy (§4)
- Release checklist (§5)
- Repository Intelligence engine
- `.guardian.yml` schema

### 10.2 Per-project (Profile Plugin)

| Element | IFG | PSAG |
|---------|-----|------|
| Workflow deploy | `ifg.deploy.run` | `psag.deploy.run` |
| Classifier paths | `app/`, `frontend-react/` | `psag_app/` (TBD) |
| Runbooks | Container Manager, KSeF | TBD |
| Remote host | DS723+ | TBD |
| Release scope | backend + frontend + mobile | TBD |

### 10.3 Repo Guardian vs repo projektu

| Repo | Rola |
|------|------|
| `guardian` (osobne) | Canon, ADR Core, wspólne standardy |
| `<project>` (IFG, PSAG) | Kod aplikacji + profil operacyjny |
| Docelowo | Standard kopiowany z szablonu `guardian new-project` |

---

## 11. Migracja z stanu obecnego

### Fazy

| Faza | Zakres |
|------|--------|
| **v1** | `.gitignore`, untrack `dist/`, commity cutover, branch `release/*` pierwszy |
| **v2** | Reorganizacja `docs/`, sync `main`←`production`, release checklist w Guardian |
| **v3** | Repository Intelligence CLI, automatyczny commit plan, archiwizacja docs |

Szczegóły: `docs/reports/2026-07-06_REPOSITORY_TARGET_STATE_DESIGN.md`

---

## 12. Słownik

| Termin | Znaczenie |
|--------|-----------|
| **GWO** | Guardian Work Order — zlecony pakiet prac operacyjnych |
| **Safety Gate** | GO/NO_GO przed operacją mutating |
| **Release** | Integracja feature branchy przed production |
| **Clean tree** | Brak niezacommitowanych tracked changes na production |
| **Repository Intelligence** | Warstwa analizy i doradztwa commit/release |

---

*Dokument kanoniczny. Zmiany wymagają ADR lub aktualizacji Guardian Canon.*
