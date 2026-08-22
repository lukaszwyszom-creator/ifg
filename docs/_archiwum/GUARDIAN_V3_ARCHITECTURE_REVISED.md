# Guardian v3 — architektura (REVISED)

**Data:** 2026-06-26  
**Status:** Dokument projektowy + **implementacja klasyfikacji CRLF w `ifg_guardian`** (2026-06-26)  
**Poprzednik:** [`GUARDIAN_V3_ARCHITECTURE.md`](GUARDIAN_V3_ARCHITECTURE.md)  
**Wersja docelowa:** Guardian Framework `3.x` + pluginy projektowe

Szczegóły klasyfikacji końców linii: [`GUARDIAN_CRLF_CLASSIFICATION.md`](GUARDIAN_CRLF_CLASSIFICATION.md).

---

## 0. Zmiana paradygmatu

| Aspekt | v3 (poprzedni dokument) | v3 REVISED |
|--------|---------------------------|------------|
| Tożsamość | „IFG Guardian” — narzędzie jednego repo | **Guardian Framework** — osobny produkt administracyjny |
| IFG | Właściciel całego kodu | **Pierwszy plugin** (`plugins/ifg/`) |
| Struktura | `ifg_guardian/modules/{ksef,warehouse,...}` | `guardian/core/` + `guardian/plugins/{ifg,ifgm,psag,generic}/` |
| Doctor | Agregat checków IFG w jednym pliku | **Główna komenda systemu** — core + wszystkie aktywne pluginy |
| Raporty | `docs/guardian/` w repo IFG | Core: `.guardian/` + opcjonalnie eksport MD/JSON per plugin |
| Zależności Core | Znał KSeF, React, DS723+, mobile | **Core nie zna żadnego projektu** |

**Cel:** Guardian może obsłużyć IFG, IFGM, PSAG i dowolny przyszły projekt bez modyfikacji core.

---

## 1. Guardian Core

### 1.1 Odpowiedzialność

Core dostarcza **infrastrukturę**, nie logikę biznesową.

```
guardian/
  __init__.py
  __main__.py              # entry: guardian
  core/
    cli/                   # parser, subcommands, global flags
    logger/                # structured logging, verbosity
    reporting/             # Report model, writers
    risk/                  # RiskLevel, agregacja, merge wyników pluginów
    plugins/               # discovery, loader, registry
    git/                   # porcelain, diff helpers, branch sync
    ssh/                   # remote exec, host resolution
    docker/                # compose ps, container state
    filesystem/            # safe read, path rules, .gitignore parsing
    config/                # global + project guardian.yaml
    output/
      terminal.py
      markdown.py
      json.py
    history/               # .guardian/ read/write/compare (design only)
    doctor/                # orchestrator doctor (core checks + plugin dispatch)
```

### 1.2 Dozwolone w Core

| Moduł | Zakres |
|-------|--------|
| **CLI** | Subcommands, `--format terminal\|markdown\|json`, `--yes`, `--dry-run`, globalne flagi |
| **Logger** | Poziomy, correlation id per run, plugin tag |
| **Reporting** | Wspólny model `CheckResult`, `Report`, `RecommendedAction` |
| **Risk engine** | `RiskLevel` enum, `max_risk()`, merge list wyników — **bez reguł domenowych** |
| **Plugin loader** | Discovery z `guardian.plugins.*`, entry points, `guardian.yaml` |
| **Git** | status, porcelain, fetch, ahead/behind, diff -w, **bez** reguł IFG |
| **SSH** | exec, capture, host z env/config |
| **Docker** | compose ps parsing, health predicates |
| **Filesystem** | read-only scan, **line-ending analysis** (HEAD/index/worktree), ignore patterns z `.gitignore` |
| **Config** | `~/.guardian/config.yaml`, `./.guardian/project.yaml` |
| **Output** | Trzy formaty z jednego modelu wyniku |

### 1.3 Zakazane w Core (hard boundary)

Core **nie importuje i nie referencjonuje**:

- KSeF, FA(3), faktur, NIP
- warehouse, PZ/WZ, inventory
- `frontend-react`, `mobile-expo`, npm, dist
- IFG, IFGM, PSAG jako nazwy domenowe (tylko string plugin id w loaderze)
- DS723+, Synology, Cloudflare — host może być w **config pluginu**, nie w core
- Ścieżek typu `app/api/routers/`

Reguły klasyfikacji plików (np. „zmiana frontend wymaga build”) należą do **pluginu**, nie core.

### 1.4 Core commands (wbudowane)

| Komenda | Opis |
|---------|------|
| `guardian version` | Wersja framework + lista pluginów |
| `guardian doctor` | Orchestrator (patrz §3) |
| `guardian repo status` | Git sync, ahead/behind, dirty |
| `guardian repo audit` | Klasyfikacja generyczna + merge risk z pluginów; **CRLF/line-ending verification** (patrz §1.5) |
| `guardian repo clean --dry-run` | Preview — **nigdy** auto-exec |
| `guardian plugins list` | Aktywne pluginy |
| `guardian plugins doctor` | Tylko core checks (bez pluginów) |

Komendy `deploy`, `ksef`, `warehouse`, `prod` **nie istnieją w core** — rejestruje je plugin.

### 1.5 Klasyfikacja końców linii (repo audit)

Implementacja tymczasowa w `ifg_guardian/core/line_endings.py` (docelowo: `guardian/core/filesystem/line_endings.py`).

**Zasada:** Core/plugin **nie może** oznaczyć pliku jako CRLF-only na podstawie samego `git diff -w` ani obecności CRLF w working tree.

Wymagane potwierdzenie trzech warstw (HEAD, index, worktree):

| Kategoria | Opis | Confidence |
|-----------|------|------------|
| `CRLF_ONLY` | Różnią się wyłącznie końce linii; symulacja restore: index ≠ worktree | HIGH |
| `UNKNOWN_LINE_ENDINGS` | Niejednoznaczne (np. identyczne bajty, fałszywy `M` w statusie) | LOW / MEDIUM |
| _(fallback)_ | Znormalizowana treść różna — klasyfikacja merytoryczna pluginu | HIGH |

**Restore:** rekomendacja `git restore` tylko gdy `CRLF_ONLY` **i** restore simulation positive. Guardian pozostaje read-only.

Raport zawiera sekcję **Verification** (diff --ignore-cr-at-eol, HEAD/index/worktree, ls-files --eol, file, restore simulation).

Pełna specyfikacja: [`GUARDIAN_CRLF_CLASSIFICATION.md`](GUARDIAN_CRLF_CLASSIFICATION.md).

---

## 2. Pluginy

### 2.1 Struktura katalogów

```
guardian/
  core/
  plugins/
    generic/               # fallback: podstawowy repo audit rozszerzony
    ifg/                   # Imperium Faktur G (pierwszy plugin produkcyjny)
    ifgm/                  # mobile + backend IFGM
    psag/                  # watchery, mail, cron
```

Plugin może żyć:
- **w repo Guardian** (monorepo frameworku), albo
- **w repo projektu** jako `guardian_plugin_ifg/` + entry point `pyproject.toml`

Discovery (kolejność):
1. Entry points `guardian.plugins`
2. `./.guardian/plugins/` (lokalne)
3. Built-in `guardian/plugins/{name}/`

Aktywacja per projekt — plik `./.guardian/project.yaml`:

```yaml
plugins:
  - ifg
  # - ifgm   # opcjonalnie w tym samym workspace
host: ds723                  # przekazywane do pluginu, nie hardcoded w core
reports_export: docs/guardian  # opcjonalny eksport MD poza .guardian/
```

### 2.2 Co definiuje plugin

| Element | Opis |
|---------|------|
| **commands()** | Własne subcommands (`ifg deploy check`, `ifg ksef check`, …) |
| **doctor_checks()** | Lista checków uruchamianych przez `guardian doctor` |
| **risk_checks()** | Reguły scoringu dla `repo audit` i doctor |
| **reports()** | Szablony / ścieżki eksportu raportów pluginu |
| **deploys()** | Scenariusze mutujące (jawnie, z `--yes`) |

Core **nie zna** implementacji — tylko wywołuje interfejs.

### 2.3 Plugin IFG (docelowy zakres)

Przeniesienie obecnej logiki z `ifg_guardian/modules/`:

| Obecny moduł | Docelowy plugin IFG |
|--------------|---------------------|
| `deploy.py` | `ifg/commands/deploy.py` |
| `ksef.py` | `ifg/commands/ksef.py` |
| `frontend.py` | `ifg/checks/frontend.py` |
| `warehouse.py` | `ifg/checks/warehouse.py` |
| `production.py` | `ifg/commands/prod.py` |
| `api_mobile.py` | `ifg/checks/mobile_api.py` |

Komendy użytkownika (po migracji):

```bash
guardian ifg deploy check
guardian ifg ksef check
guardian ifg frontend check
guardian ifg warehouse check
guardian ifg prod health
guardian ifg prod recover --yes    # mutujące
guardian ifg deploy run --yes      # mutujące (ex guardian2)
```

Alias kompatybilności: `guardian deploy check` → `guardian ifg deploy check` (deprecated).

### 2.4 Plugin IFGM

| Check | Zakres |
|-------|--------|
| mobile | Expo, apiClient vs backend |
| backend | Router registration (obecny `run_api_guardian`) |

### 2.5 Plugin PSAG

| Check | Zakres |
|-------|--------|
| watchers | Procesy, PID files |
| mail | Kolejka, ostatnie błędy |
| cron | crontab vs oczekiwany |

*(Szczegóły PSAG — poza scope IFG; plugin rezerwuje namespace.)*

### 2.6 Plugin generic

Minimalny plugin dla repo bez dedykowanego pluginu:
- rozszerza core `repo audit` o heurystyki uniwersalne (secrets, dist/, node_modules/)
- brak deploy/production

---

## 3. Doctor — główna komenda systemu

### 3.1 Przepływ

```
guardian doctor [--format terminal|markdown|json] [--plugin ifg] [--no-history]
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  CORE DOCTOR                                               │
│  • git (branch, dirty, ahead/behind)                      │
│  • repo (generic audit summary)                           │
│  • ssh (connectivity do host z project.yaml)                │
│  • docker (compose ps jeśli skonfigurowane)                 │
└───────────────────────────────────────────────────────────┘
        │
        ▼  dla każdego aktywnego pluginu (kolejność z config)
┌─────────────┬─────────────┬─────────────┐
│  IFG        │  IFGM       │  PSAG       │
│  frontend   │  mobile     │  watchers   │
│  warehouse  │  backend    │  mail       │
│  ksef       │             │  cron       │
│  production │             │             │
└─────────────┴─────────────┴─────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  AGREGACJA                                                 │
│  • Overall Health: OK | DEGRADED | FAIL                    │
│  • Overall Risk: LOW | MEDIUM | HIGH | CRITICAL            │
│  • Recommended Action: merged, deduplicated, priorytety   │
└───────────────────────────────────────────────────────────┘
        │
        ▼
  output (terminal / markdown / json)
  opcjonalnie: zapis .guardian/doctor.json + diff vs poprzedni
```

### 3.2 Overall Health

| Status | Warunek |
|--------|---------|
| **OK** | Wszystkie checki PASS, risk ≤ MEDIUM |
| **DEGRADED** | WARNING lub risk HIGH bez CRITICAL |
| **FAIL** | Jakikolwiek check ERROR lub risk CRITICAL |

### 3.3 Overall Risk

`max_risk(core_checks + all_plugin_checks)` — core dostarcza mechanizm, pluginy dostarczają wyniki.

### 3.4 Recommended Action

Lista obiektów:

```json
{
  "priority": 1,
  "source": "core.repo",
  "risk": "MEDIUM",
  "action": "Oczyść CRLF: git restore -- app/api/deps.py (ręcznie, tylko gdy Verification: restore simulation ✓)",
  "mutating": false
}
```

Core sortuje po `priority`, `risk`, deduplikuje. **Nigdy nie wykonuje** akcji z `mutating: true` bez osobnej komendy użytkownika.

---

## 4. Plugin API (projekt interfejsu)

### 4.1 Klasy bazowe (koncept)

```python
class GuardianPlugin(ABC):
    """Kontrakt pluginu — specyfikacja, nie implementacja."""

    @property
    def name(self) -> str: ...           # np. "ifg"
    @property
    def version(self) -> str: ...        # semver pluginu
    @property
    def description(self) -> str: ...

    def commands(self) -> list[GuardianCommand]: ...
    def doctor_checks(self) -> list[GuardianCheck]: ...
    def risk_checks(self) -> list[RiskCheck]: ...
    def report_templates(self) -> list[ReportTemplate]: ...
```

### 4.2 GuardianCommand

```python
class GuardianCommand(ABC):
    name: str                    # np. "deploy check"
    namespace: str               # np. "ifg" → guardian ifg deploy check
    mutating: bool = False       # True wymaga --yes
    supports_dry_run: bool = False

    def run(self, ctx: CommandContext) -> CommandResult: ...
```

`CommandContext` zawiera: `cwd`, `config`, `format`, `dry_run`, `yes`, `logger` — **bez** globalnych stałych IFG.

### 4.3 GuardianCheck (doctor)

```python
class GuardianCheck(ABC):
    id: str                      # np. "ifg.frontend.dist"
    label: str
    timeout_seconds: int = 60

    def run(self, ctx: CheckContext) -> CheckResult: ...
```

### 4.4 CheckResult (wspólny model — core)

```python
@dataclass
class CheckResult:
    check_id: str
    plugin: str
    status: Literal["pass", "warn", "fail", "skip"]
    risk: RiskLevel
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recommended_actions: list[RecommendedAction] = field(default_factory=list)
    duration_ms: int = 0
```

### 4.5 RiskCheck (repo audit extension)

```python
class RiskCheck(ABC):
    """Plugin ocenia ścieżki plików / stan projektu."""
    def classify_file(self, path: str, git_status: str, ctx: CheckContext) -> FileClassification | None: ...
    def post_audit(self, audit: RepoAuditState, ctx: CheckContext) -> list[RecommendedAction]: ...
```

Core uruchamia klasyfikację generyczną, potem każdy plugin może **nadpisać/rozszerzyć** wynik dla znanych ścieżek.

### 4.6 ReportTemplate

```python
class ReportTemplate(ABC):
    id: str                      # np. "repo_audit", "doctor"
    def render(self, report: Report, format: OutputFormat) -> str | dict: ...
```

### 4.7 Rejestracja

```python
# guardian/plugins/ifg/plugin.py
class IFGPlugin(GuardianPlugin):
    name = "ifg"
    version = "1.0.0"
    ...

# pyproject.toml (repo IFG, opcjonalnie później)
[project.entry-points."guardian.plugins"]
ifg = "guardian_plugin_ifg:IFGPlugin"
```

---

## 5. Output — terminal, markdown, json

### 5.1 Globalna flaga

```bash
guardian doctor --format json
guardian repo audit --format markdown -o docs/guardian/REPO_AUDIT.md
```

Domyślnie: `terminal`. Flaga `-o / --output` opcjonalna.

### 5.2 JSON schema (doctor — docelowy kontrakt dla AI)

```json
{
  "guardian_version": "3.1.0",
  "timestamp": "2026-06-26T12:00:00Z",
  "project_root": "/path/to/repo",
  "plugins_active": ["ifg"],
  "overall_health": "DEGRADED",
  "overall_risk": "HIGH",
  "core_checks": [ { "check_id": "core.git.branch", "status": "pass", "risk": "LOW", "message": "..." } ],
  "plugin_checks": {
    "ifg": [ { "check_id": "ifg.frontend.dist", "status": "fail", "risk": "HIGH", "message": "..." } ]
  },
  "recommended_actions": [
    { "priority": 1, "source": "ifg.frontend.dist", "risk": "HIGH", "action": "cd frontend-react && npm run build", "mutating": false }
  ],
  "history_delta": {
    "new_issues": ["ifg.frontend.dist"],
    "resolved_issues": [],
    "risk_change": "up"
  }
}
```

Pole `history_delta` wypełniane po porównaniu z `.guardian/doctor.json` (§6).

### 5.3 Markdown

Nagłówki stabilne (`## Overall Health`, `## RECOMMENDED ACTION`) — parsowalne przez AI i ludzi.

### 5.4 Terminal

Obecny UX (emoji, werdykty) — writer terminal, nie logika checków.

---

## 6. Historia — katalog `.guardian/`

### 6.1 Lokalizacja

```
<project_root>/.guardian/
  project.yaml              # aktywne pluginy, host, export paths
  history.json              # indeks ostatnich runów
  runs/
    2026-06-26T120000Z_doctor.json
    2026-06-26T120000Z_repo.json
  latest/
    doctor.json             # symlink lub kopia ostatniego
    repo.json
    deploy.json
```

**Core zarządza formatem**, pluginy dopisują sekcje w `plugin_checks`.

### 6.2 history.json (indeks)

```json
{
  "runs": [
    {
      "id": "2026-06-26T120000Z",
      "command": "doctor",
      "overall_health": "DEGRADED",
      "overall_risk": "HIGH",
      "path": "runs/2026-06-26T120000Z_doctor.json"
    }
  ]
}
```

### 6.3 Możliwości analityczne (przyszłe)

- „Co nowego od wczoraj?” → diff `latest/doctor.json` vs poprzedni run
- „Czy ryzyko rośnie?” → trend `overall_risk` w `history.json`
- „Czy deploy był po czystym doctor?” → korelacja `deploy.json` z `doctor.json`

**Na tym etapie:** tylko specyfikacja. **Brak zapisu.**

### 6.4 Relacja do `docs/guardian/`

| Cel | Lokalizacja |
|-----|-------------|
| Operacyjna historia, diff | `.guardian/` (gitignored) |
| Raporty do commita / review | `docs/guardian/` (eksport `--format markdown -o`) |

---

## 7. Roadmapa

```
Guardian Core
      ↓
Plugin API
      ↓
Plugin IFG          ← pierwszy consumer, największa baza kodu
      ↓
Plugin IFGM         ← reuse checków mobile/backend
      ↓
Plugin PSAG         ← osobny stack, mniejsza presja
      ↓
Automatyczne raporty  ← .guardian history + scheduled doctor
      ↓
CI/CD               ← guardian doctor --format json w pipeline
      ↓
Enterprise          ← multi-host, RBAC, centralny dashboard
```

### Uzasadnienie kolejności

| Faza | Dlaczego teraz |
|------|----------------|
| **Guardian Core** | Bez stabilnego core pluginy będą kopiować git/ssh/output — powtórka monolitu |
| **Plugin API** | Kontrakt musi być zamrożony zanim przeniesiemy IFG — inaczej double refactor |
| **Plugin IFG** | 100% obecnego użycia; backward compat; ROI natychmiastowy |
| **Plugin IFGM** | Wydzielenie mobile check z IFG; IFGM może być osobnym repo |
| **Plugin PSAG** | Inna domena; nie blokuje IFG; weryfikuje czy API jest wystarczająco generyczne |
| **Automatyczne raporty** | Wymaga stabilnego JSON + historii; sens dopiero gdy doctor jest kompletny |
| **CI/CD** | JSON contract + exit codes; niskie ryzyko po IFG plugin |
| **Enterprise** | Multi-tenant, auth — dopiero gdy framework sprawdzony w 3 projektach |

---

## 8. Kompatybilność wsteczna (bez Big Bang)

### 8.1 Zasada

`scripts/guardian.py` i `scripts/guardian2.py` **pozostają** jako cienkie shims przez całą migrację.

### 8.2 Mapowanie migracji

| Warstwa | Faza 0 (dziś) | Faza 1 | Faza 2 | Faza 3 |
|---------|---------------|--------|--------|--------|
| Entry | `guardian.py` → `ifg_guardian` | `guardian.py` → `guardian.core` + plugin ifg | entry point `guardian` CLI | opcjonalnie pip package |
| Flagi legacy | `--deploy-check` itd. | alias → `guardian ifg ...` | DeprecationWarning | usunięcie (1 release+) |
| guardian2 | deploy-ksef, recover-prod | delegate do `ifg` plugin mutating commands | logika w pluginie | guardian2.py = shim deprecated |

### 8.3 Exit codes (zachować)

| Kod | Znaczenie |
|-----|-----------|
| 0 | OK |
| 1 | WARNING / FAIL |
| 2 | ERROR (błąd wykonania) |

Dotyczy `--deploy-check`, `--repo-sync`, `doctor` — CI IFG zależy od tego.

### 8.4 Co NIE robić w migracji

- Nie usuwać `ifg_guardian/` dopóki plugin IFG nie przejmie 100% testów regresji
- Nie zmieniać outputu terminal legacy bez `--format json`
- Nie przenosić core do repo IFG na stałe — docelowo Guardian może być osobnym repo

---

## 9. Relacja do obecnego etapu 1 (ifg_guardian)

Obecna implementacja `scripts/ifg_guardian/` to **prototyp pluginu IFG w disguise** — moduły domenowe siedzą obok pseudo-core.

**Korekta kursu przed właściwą refaktoryzacją:**

1. **Zatrzymać** rozbudowę `ifg_guardian/modules/{ksef,warehouse,...}` w obecnej formie.
2. **Wyodrębnić** do przyszłego `guardian/core/` tylko: git, ssh, docker, risk enum, reporting, cli skeleton.
3. **Przenieść** resztę do `guardian/plugins/ifg/` (lub tymczasowo `ifg_guardian/` jako alias pluginu).
4. **Doctor** — przepisać z hardcoded listy checków na orchestrator plugin API.

Etap 1 nie jest stracony — to **donor code** dla pluginu IFG i proof-of-concept CLI.

---

## 10. Ocena ryzyka migracji (REVISED)

| Ryzyko | Poziom | Komentarz |
|--------|--------|-----------|
| Double refactor (ifg_guardian → core+plugin) | **Średnie–wysokie** | Etap 1 już zrobiony; wymaga dyscypliny — nie dokładać domeny do core |
| Rozjazd API pluginów | **Średnie** | Zamrozić Plugin API przed IFGM/PSAG |
| Regresja legacy flag | **Średnie** | Shims + testy golden output |
| Scope creep Enterprise | **Niskie** | Roadmapa odroczona świadomie |
| Guardian jako osobne repo vs monorepo IFG | **Średnie** | Decyzja przed IFGM; entry points umożliwiają oba |
| JSON schema breaking changes | **Średnie** | Wersjonować schema (`doctor_report_v1`) |
| `.guardian/` w gitignore | **Niskie** | Standardowy pattern |

**Ogólna ocena:** migracja **wykonalna etapowo**, ryzyko wyższe niż w poprzednim dokumencie (bo dodatkowy wymiar pluginów), ale **niższe długoterminowo** niż utrzymanie IFG-specific monolitu.

---

## 11. Rekomendowana kolejność implementacji

| # | Etap | Deliverable | Zależności |
|---|------|-------------|------------|
| 1 | **Spec freeze** | Ten dokument + Plugin API PR review | — |
| 2 | **Guardian Core skeleton** | cli, output (3 formaty), logger, risk merge, git/ssh/docker | Spec |
| 3 | **Plugin loader** | discovery, `project.yaml`, registry | Core |
| 4 | **Core doctor** | orchestrator + core checks only | Loader |
| 5 | **Plugin IFG (extract)** | przeniesienie z `ifg_guardian/` bez zmiany logiki | Loader + doctor |
| 6 | **Legacy shims** | `guardian.py` / `guardian2.py` → core + ifg plugin | Plugin IFG |
| 7 | **Repo audit v2** | core generic + ifg risk_checks | Plugin IFG |
| 8 | **History `.guardian/`** | zapis + delta w doctor JSON | Doctor |
| 9 | **Plugin IFGM** | mobile/backend checks | Stabilne API |
| 10 | **Plugin PSAG** | watchers/mail/cron | Stabilne API |
| 11 | **CI/CD** | `guardian doctor --format json` | IFG plugin stable |
| 12 | **Deprecation** | usuń legacy flagi | 1 release cycle |

**Nie zaczynać** od IFGM/PSAG ani Enterprise przed zamrożeniem Plugin API i przeniesieniem IFG.

---

## 12. Werdykt

Poprzedni dokument v3 opisywał **refaktoryzację monolitu IFG**.  
Ten dokument opisuje **framework administracyjny** z IFG jako pierwszym pluginem.

**Następny krok:** review Plugin API (§4) → implementacja Core skeleton (§11/#2) — **bez** dalszej rozbudowy obecnego `ifg_guardian` poza utrzymaniem backward compat.

---

*Dokument architektoniczny. Klasyfikacja CRLF zaimplementowana w `ifg_guardian` — patrz §1.5 i `GUARDIAN_CRLF_CLASSIFICATION.md`.*
