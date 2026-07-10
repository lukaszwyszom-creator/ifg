# Guardian Canon Review — 2026-07-06

**Scope:** Pełna analiza Canona Guardiana po formalnym zamrożeniu **Guardian Core v1 (Frozen)**.  
**Repozytoria:** Canon w `/Users/lukasz/projekty/guardian`; status operacyjny Core także w `ifg_standalone/docs/guardian/core/GUARDIAN_CORE_STATUS.md`.  
**Metoda:** Odczyt wszystkich plików Canona + ADR + Architecture (Intelligence Model, Design Evolution) + Profile IFG + istniejące Reviews; analiza przed zmianami; minimalne uzupełnienia tylko tam, gdzie praktyka wymagała promocji do Canona.

---

## 1. Executive summary

Guardian Core v1 osiągnął dojrzałość operacyjną (warstwa execution, preflight, status semantics, plan migracji produkcyjnej IFG). **Freeze** był udokumentowany wyłącznie w repozytorium Profile (`GUARDIAN_CORE_STATUS.md`), **nie** w Canonie repozytorium Core.

Pozostałe zasady z checklisty użytkownika **istniały pośrednio** w Canonie (Repository/Documentation First, realne problemy operacyjne, brak omijania Guardiana w IFG Profile), ale **nie jako nazwane, jednoznaczne wpisy** wiążące całą platformę.

**Wykonane zmiany (minimalne, bez duplikacji treści):**

| Zmiana | Uzasadnienie |
|--------|--------------|
| **ADR-0001** — Guardian Core v1 Frozen | Jedyny właściwy mechanizm zmian Core po v1; potwierdzone GWO-G-003, GWO-IFG-002A, status Frozen |
| **CONSTITUTION** § Change control — bullet o Freeze | Wiązanie governance z ADR |
| **PRINCIPLES** — H-006, H-007 | Promocja praktyki do heurystyk (Production-driven evolution, Operations through Guardian) |
| **GLOSSARY** — 4 terminy z odnośnikami | Nazewnictwo operacyjne bez tworzenia równoległych zasad |
| **GUARDIAN_CANON_V1** — wiersz w Related docs | Cross-link do ADR-0001 |
| **README** — status Core v1 Frozen | Spójność z ADR-0001 |
| **GUARDIAN_CORE_STATUS.md** — link do ADR-0001 | Jedno źródło prawdy |

**Nie dodano** osobnych „fundamentalnych zasad” Production First / Guardian First / Zero Theory — są to **aliasy i heurystyki** wskazujące na istniejące §3 Canon V1, §10 PRINCIPLES, Profile IFG § Guardian binding.

Canon pozostaje **spójny** po Core v1; znane niedociągnięcia z EXP-0001 (trzy modele procesu, PL/EN split) **nie zostały rozwiązane** — nie wynikają z Freeze i wymagałyby osobnego GWO housekeeping.

---

## 2. Przeglądany korpus (pełny Canon + powiązane)

### 2.1 Pliki Canona (`guardian/Canon/` — 6 plików)

| Plik | Rola |
|------|------|
| `GUARDIAN_CANON_V1.md` | Kotwica (PL): misja, 9 zasad, Context Bootstrap, 7-krokowy proces |
| `CONSTITUTION.md` | Governance, precedencja dokumentów, change control, ograniczenia agentów |
| `PRINCIPLES.md` | Repository / Documentation / Knowledge First + 10 zasad, anti-patterns, heurystyki H-001–H-007 |
| `VISION.md` | North star, success criteria, non-goals |
| `MANIFEST.md` | Zobowiązania i odmowy, fazy pracy |
| `GLOSSARY.md` | Terminy platformy, procesu, intelligence model |

### 2.2 Powiązane artefakty wiążące (poza folderem Canon/)

| Plik | Rola w analizie |
|------|-----------------|
| `ADR/ADR-0000-development-philosophy.md` | Filozofia bootstrap; docs before code |
| `ADR/ADR-0001-guardian-core-v1-freeze.md` | **Nowy** — decyzja o Freeze |
| `Architecture/GUARDIAN_INTELLIGENCE_MODEL.md` | Repository/Documentation/Knowledge First, Context Compression, Learning Promotion |
| `Architecture/DESIGN_EVOLUTION.md` | Granice promocji (DEV vs ADR vs Heuristic vs Workflow) |
| `Profiles/IFG.md` | Guardian binding, no silent bypass, deploy principles |
| `Reviews/FOUNDATION_REVIEW_V1.md` | EXP-0001 — spójność, duplikacje, luki |
| `ifg_standalone/docs/guardian/core/GUARDIAN_CORE_STATUS.md` | Status Frozen v1.0 (downstream) |

**Uwaga:** Pluginy i backends **nie mają** dedykowanych wpisów w Canonie Core. Backends deploymentu opisane są w **Profile repo** (`docs/guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md`) — zgodnie z granicą Core vs Profile.

---

## 3. Mapa tematów — istniejące wpisy

### 3.1 Rozwój Core

| Źródło | Treść |
|--------|-------|
| GUARDIAN_CANON_V1 §3 | Nowe funkcje tylko przy rzeczywistym problemie operacyjnym |
| PRINCIPLES §10 | Self-improving platform — z dowodów, nie spekulacji |
| CONSTITUTION § Scope | Core = orchestration + knowledge; nie domain apps |
| ADR-0000 | Bootstrap order; Guardian designed inside Guardian |
| ADR-0001 | **Core v1 Frozen; zmiany przez ADR + evidence** |
| H-003 | Speculative architecture = debt przed runtime |
| H-006 | Core evolves from production evidence |

### 3.2 Rozwój architektury

| Źródło | Treść |
|--------|-------|
| GUARDIAN_CANON_V1 §6–7 | Decyzje architektoniczne udokumentowane; workflow testowalne |
| CONSTITUTION § Document precedence | Constitution → Canon → ADR → Architecture → Capabilities → Profiles → Workflows |
| Intelligence Model | Warstwa intelligence nad Components; ADR before architectural change |
| DESIGN_EVOLUTION | DEV = reasoning history; ADR = binding decision |
| MANIFEST | Shadow architecture refused |

### 3.3 Sposób implementacji

| Źródło | Treść |
|--------|-------|
| PRINCIPLES §2 Documentation First | Design before code |
| Intelligence Model | Sekwencja: Problem → Research → ADR → Capability/Workflow → GWO → Implementation → Review |
| GUARDIAN_CANON_V1 §9 | Dokumentacja przed implementacją |
| ADR-0000 §4 | Bootstrap order bez business logic w Core |
| Anti-patterns (PRINCIPLES) | AI-only decision, dual sync paths, lessons only in Review |

### 3.4 Production First

**Przed review:** Brak terminu „Production First”.  
**Istniejące odpowiedniki:**

- PRINCIPLES §8 Operational realism (failure modes, LRO)
- MANIFEST § Commitment to operators — operational pain → structured knowledge
- VISION — measured operational pain, not hype
- GUARDIAN_CANON_V1 §3 — realne problemy operacyjne
- Profile IFG § Verification before promote

**Ocena:** Zasada **istnieje pośrednio**. „Production First” w sensie „Core rozwija się z produkcji/Profile, nie z teorii” = **H-006 + ADR-0001 + §3 Canon V1**. Nie tworzono osobnej zasady fundamentalnej — dodano termin **Production-driven evolution** w GLOSSARY z synonimem *Production First*.

### 3.5 Repository First

| Źródło |
|--------|
| PRINCIPLES §1 |
| CONSTITUTION § Authority |
| GLOSSARY |
| Intelligence Model § Repository First |
| README, ADR-0000 |
| H-001 |

**Ocena:** Pełna, spójna; **bez zmian**.

### 3.6 Documentation First

| Źródło |
|--------|
| PRINCIPLES §2 |
| GUARDIAN_CANON_V1 §9 |
| CONSTITUTION § Documentation precedes implementation |
| Intelligence Model § Documentation First |
| GLOSSARY |

**Ocena:** Pełna; **bez zmian**.

### 3.7 Knowledge First

| Źródło |
|--------|
| PRINCIPLES §3 |
| Intelligence Model § Knowledge First, Learning Promotion |
| GLOSSARY (Learning Promotion, Distilled Learning, Promotion Target) |

**Ocena:** Pełna; **bez zmian**.

### 3.8 Workflow

| Źródło | Treść |
|--------|-------|
| GUARDIAN_CANON_V1 | 7-krokowy proces (Bootstrap → Execute) |
| MANIFEST | Discover → Decide → Plan → Execute → Verify → Improve |
| Intelligence Model | 7-krokowa sekwencja operacyjna |
| CONSTITUTION | Workflows na pozycji 7 precedencji |
| PRINCIPLES §7 | Testable workflows |
| GLOSSARY | Workflow = testable procedure |

**Ocena:** Trzy modele procesu (EXP-0001 §2) — **nadal nierozwiązane**; nie blokuje Freeze; wymaga osobnego GWO mapowania kroków.

### 3.9 GWO (Guardian Work Orders)

| Źródło |
|--------|
| GLOSSARY (GWO, Work Order) |
| CONSTITUTION § Agent constraints §4 |
| MANIFEST § How we work |
| H-004 Bounded GWO |
| Templates/TEMPLATE_WORK_ORDER.md |

**Ocena:** Dobra definicja; Reviews jako mandatory output — **bez zmian**.

### 3.10 Pluginy

**Brak wpisów w Canonie Core.**  
Modularność i wymienialność komponentów: GUARDIAN_CANON_V1 §4, PRINCIPLES §5–6, GLOSSARY **Component**.  
Plugin jako termin **nie jest zdefiniowany** — świadomie: praktyka nie wymagała osobnej zasady; integracja open-source jest pokryta przez „Integration over reinvention”.

### 3.11 Backends

**Brak w Canonie Core.**  
ADR-0001 wspomina backends w kontekście zakazu spekulacyjnej architektury.  
Implementacja backendów (SSH, Docker Compose, HTTP, Local) — **Profile/downstream** + Architecture v1.0 w IFG — zgodnie z Profile-first execution assets.

**Rekomendacja odroczona:** Capability + Workflow w Core po udowodnieniu migracji produkcyjnej (GWO-IFG-002A obecnie PLANNING / NOT PRODUCTION PROVEN).

### 3.12 Operacje administracyjne

| Źródło | Treść |
|--------|-------|
| PRINCIPLES §8 | Operational realism |
| Profile IFG § Deployment principles | Branch gate, verification, no silent bypass |
| Profile IFG § Guardian binding | GWO/ADR/Review dla significant work |
| MANIFEST | Operational pain → Workflows/ADR |
| H-007 | Operations go through Guardian |
| GLOSSARY | LRO, defer, resume, HWM |

**Ocena:** Reguły operacyjne są w **Profile + Principles**; Core Canon nie duplikuje runbooków — **poprawne** per Learning Promotion.

---

## 4. Checklist pięciu zasad — przed i po review

### 4.1 Guardian Core Freeze

| Stan przed | Stan po |
|------------|---------|
| Tylko `ifg_standalone/docs/guardian/core/GUARDIAN_CORE_STATUS.md` | **ADR-0001** + CONSTITUTION § Change control + GLOSSARY + README + cross-link w status file |

**Ocena przed:** Brak w Canonie Core — **luka krytyczna** po formalnym Frozen.  
**Doprecyzowanie:** ADR definiuje housekeeping vs ADR-required changes.

### 4.2 Production First

| Stan przed | Stan po |
|------------|---------|
| Pośrednio (§3 Canon V1, §8 operational realism, MANIFEST operators) | GLOSSARY **Production-driven evolution** (*Production First*); **H-006** |

**Ocena:** Nie wymaga osobnej zasady fundamentalnej — **alias + heurystyka** wystarczą.

### 4.3 Guardian First (nie omijamy Guardiana)

| Stan przed | Stan po |
|------------|---------|
| Profile IFG § „No silent bypass”, § Guardian binding; CONSTITUTION emergency → Review | GLOSSARY **Guardian First**; **H-007** wskazuje Profile IFG |

**Ocena:** Wiążące dla IFG; H-007 uogólnia wzorzec na Profiles bez duplikowania runbooków w Canonie.

### 4.4 Zero Theory Rule

| Stan przed | Stan po |
|------------|---------|
| GUARDIAN_CANON_V1 §3; PRINCIPLES §10; MANIFEST refuses shadow architecture; H-003 | GLOSSARY **Zero Theory Rule** z odnośnikami; wzmocnione ADR-0001 |

**Ocena:** Istniała jako treść, nie jako nazwa — **glossary entry wystarczy**; explicite: „Not a license to skip ADR”.

### 4.5 Zmiany Core wyłącznie przez ADR lub wymaganie eksploatacyjne

| Stan przed | Stan po |
|------------|---------|
| CONSTITUTION constitutional changes → ADR; Intelligence Model ADR before code; status file „Only by ADR” | ADR-0001 szczegółowo; CONSTITUTION bullet; H-006 (production evidence jako driver ADR) |

**Ocena:** Po ADR-0001 — **jednoznaczne** dla zamrożonego Core.

---

## 5. Analiza spójności Canona (post Core v1)

### 5.1 Powielania (akceptowalne vs do rozważenia)

| Obszar | Gdzie się powiela | Werdykt |
|--------|-------------------|---------|
| Repository / Documentation First | PRINCIPLES, Intelligence Model, GLOSSARY, README, ADR-0000 | **Akceptowalne** — warstwy L0 vs Architecture; Intelligence Model rozwija, nie przeczy |
| Realne problemy operacyjne | Canon V1 §3, §10 PRINCIPLES, MANIFEST, ADR-0001, H-006, Zero Theory w GLOSSARY | **Skonsolidowane przez odnośniki** — nie dodano 4. zasady fundamentalnej |
| No bypass Guardian | IFG Profile, CONSTITUTION emergency, H-007, Guardian First w GLOSSARY | **Profile = instance, H-007 = pattern** |
| Source of truth | CONSTITUTION, PRINCIPLES §1, H-001, Intelligence Model | Spójne po EXP-0001 fix H-002 |

### 5.2 Kandydaci do połączenia (odroczone)

| Kandydat | Powód odroczenia |
|----------|------------------|
| Trzy modele procesu (Canon V1 7 kroków vs MANIFEST 6 faz vs Intelligence Model 7 kroków) | Wymaga mapowania 1:1 i aktualizacji wielu plików — **osobny GWO**, nie freeze housekeeping |
| GUARDIAN_CANON_V1 (PL) vs reszta (EN) | Świadomy split; tłumaczenie lub EN summary — **nie blokuje operacji** |
| README vs CONSTITUTION precedencja | H-002 + CONSTITUTION authoritative; README nadal może mieć uproszczoną listę — **niski priorytet** |

### 5.3 Przestarzałe

| Wpis | Ocena |
|------|-------|
| MANIFEST „Version reflects GWO-0001 bootstrap” | **Częściowo przestarzałe** — platforma przeszła GWO-0002/0003 i Core v1; aktualizacja MANIFEST Version wymaga Constitution-level review — **nie zmieniano** w tym review |
| „No CLI, no business logic” w README (stara końcówka) | **Zastąpione** linią o Core v1 Frozen |
| FOUNDATION_REVIEW open items (Backlog empty, no Profile template) | Część **rozwiązana** (IFG Profile istnieje); Backlog — nadal TBD |

### 5.4 Spójność po Guardian Core v1 Frozen

**Tak — Canon jest spójny**, pod warunkiem:

1. **ADR-0001** traktowany jako wiążący dla Core (precedencja: Constitution → Canon → **ADR**).
2. Rozwój execution/backends pozostaje w **Profile repo** do czasu promocji przez ADR + udowodniony Workflow.
3. Agenci ładują **H-006, H-007** w L0 razem z CONSTITUTION.

**Ryzyko resztkowe:** Agent czytający tylko polski `GUARDIAN_CANON_V1.md` nie widzi słowa „Frozen” — mitigacja: wiersz w Related docs → ADR-0001 (EN). Pełna integracja wymagałaby PL § w Canon V1 — **odroczone** (zmiana znaczenia kotwicy PL).

---

## 6. Wykonane zmiany

### 6.1 Dodane

| Artefakt | Opis |
|----------|------|
| `guardian/ADR/ADR-0001-guardian-core-v1-freeze.md` | Decyzja Frozen v1.0, zakaz spekulacyjnej architektury Core, evidence requirements |
| `PRINCIPLES.md` H-006, H-007 | Heurystyki production-driven Core + operations through Guardian |
| `GLOSSARY.md` | Guardian Core v1 (Frozen), Production-driven evolution, Guardian First, Zero Theory Rule |

### 6.2 Zmodyfikowane

| Plik | Zmiana |
|------|--------|
| `guardian/Canon/CONSTITUTION.md` | Bullet o Core v1 Frozen w § Change control |
| `guardian/Canon/GUARDIAN_CANON_V1.md` | Wiersz ADR-0001 w Related Canon documents |
| `guardian/README.md` | Status: Core v1 Frozen per ADR-0001 |
| `ifg_standalone/docs/guardian/core/GUARDIAN_CORE_STATUS.md` | Link do ADR-0001 |

### 6.3 Bez zmian (i dlaczego)

| Obszar | Powód |
|--------|-------|
| VISION, MANIFEST (treść merytoryczna) | Nadal aktualne; MANIFEST version note — wymaga osobnego governance GWO |
| PRINCIPLES §1–10 fundamental principles | Znaczenie zachowane; nowe treści tylko jako heurystyki |
| ADR-0000 | Nie koliduje z ADR-0001; bootstrap philosophy nadal obowiązuje |
| Intelligence Model, DESIGN_EVOLUTION | ADR-0001 implementuje istniejącą filozofię; brak sprzeczności |
| Mapowanie trzech process models | Poza zakresem freeze; nie wynika z praktyki operacyjnej |
| Plugin terminology | Brak praktyki wymagającej terminu w Canonie |
| Backend architecture w Canonie | Należy do Profile/downstream do promocji po PRODUCTION PROVEN |

---

## 7. Lista zmienionych plików

### Repozytorium `guardian`

1. `ADR/ADR-0001-guardian-core-v1-freeze.md` — **nowy**
2. `Canon/CONSTITUTION.md`
3. `Canon/PRINCIPLES.md`
4. `Canon/GLOSSARY.md`
5. `Canon/GUARDIAN_CANON_V1.md`
6. `README.md`

### Repozytorium `ifg_standalone`

7. `docs/guardian/core/GUARDIAN_CORE_STATUS.md`

### Ten raport

8. `docs/reports/GUARDIAN_CANON_REVIEW_2026-07-06.md`

---

## 8. Rekomendacje na kolejne GWO (poza tym review)

1. **GWO housekeeping:** Jedna tabela mapująca 7 kroków Canon V1 ↔ MANIFEST ↔ Intelligence Model (EXP-0001).
2. **GWO po GWO-IFG-002A PRODUCTION PROVEN:** Promocja deploy backend pattern do Capability + Workflow w Core (jeśli powtarzalny).
3. **MANIFEST Version:** Aktualizacja sekcji Version po Constitution-level review (post-bootstrap, post-freeze).
4. **Opcjonalnie:** Jedno zdanie PL w GUARDIAN_CANON_V1 o stanie Frozen z linkiem do ADR-0001 — tylko jeśli wymagane dla agentów ładujących wyłącznie PL Canon.

---

## 9. Werdykt

Canon Guardiana **był gotowy filozoficznie** na Core v1 Frozen, ale **brakował wiążącego ADR** i centralnego wpisu governance. Review uzupełniło lukę **bez duplikowania** Repository/Documentation/Knowledge First i **bez tworzenia** nowych „ład brzmiących” zasad fundamentalnych.

**Guardian Core v1 Frozen** jest od 2026-07-06 formalnie częścią Canona przez **ADR-0001** i **CONSTITUTION § Change control**.
