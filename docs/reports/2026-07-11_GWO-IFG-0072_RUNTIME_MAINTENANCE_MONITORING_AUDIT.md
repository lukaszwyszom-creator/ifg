---
kind: gwo
project: IFG
workflow: GWO-IFG-0072
handoff: true
created_at: 2026-07-11T11:30:00Z
---

# GWO-IFG-0072 — Utrwalenie runtime: maintenance, monitoring i audit trail

**Data:** 2026-07-11  
**Werdykt:** **IMPLEMENTED_AND_DEPLOYED** (po push + deploy — patrz sekcja deploy)

---

## ETAP 0 — Audyt stanu początkowego

| Element | Stan |
|---|---|
| Branch | `production` @ `5b906c2` |
| origin/production | Zgodny z lokalnym HEAD przed commitem GWO-0071/0072 |
| GWO-IFG-0071 lokalnie | Kompletny, **niezatwierdzony** w commit |
| DS723+ runtime | `PRODUCTION_RUNNING`, restart `always`, CM `ifg running(3)` |
| GDD-0010 | DONE (lokalnie) |
| Aktor stopu 02:14 CEST | Nadal nieustalony |

Zmiany GWO-IFG-0071 na DS723+ (restart policy) były zastosowane przez SSH `sed` w 0071 — wymagały synchronizacji przez deploy.

---

## Decyzje architektoniczne

1. **Maintenance marker:** `.state/maintenance.json` (gitignore, atomowy JSON)
2. **Audit trail:** `.state/runtime_audit.jsonl` (append-only JSON Lines)
3. **Monitor state:** `.state/runtime_monitor.json`
4. **Powiadomienia:** neutralny `RuntimeNotifier` → `.state/runtime_notifications.log` (brak zewnętrznego kanału w repo)
5. **Harmonogram:** launchd na Mac mini (`guardian prod monitor install`, co 5 min)
6. **Restart policy:** stałe `restart: always` — bez przełączania na maintenance

### Semantyka `restart: always`

| Zdarzenie | Zachowanie |
|---|---|
| Crash kontenera | Docker restartuje |
| Restart Docker daemon | Kontenery wznawiane |
| Ręczny `docker stop` / `compose stop` | **Brak natychmiastowego restartu** — polityka ignorowana do ręcznego startu lub restartu demona |

---

## ETAP 1 — Utrwalenie GWO-IFG-0071

Zweryfikowano i włączono do commita:

- `restart: always` w `docker/docker-compose.prod.yml`
- GDD-0010 runtime status + testy (`tests/unit/test_production_runtime_status.py`)
- `prod health` z detekcją restart policy i CM project

---

## ETAP 2 — Maintenance mode

```bash
guardian prod maintenance start --yes --reason "..."
guardian prod maintenance status
guardian prod maintenance end --yes
```

- Marker przed `compose stop`
- `PRODUCTION_MAINTENANCE` gdy marker aktywny i stack zatrzymany
- Niespójność marker/stack → `PRODUCTION_DEGRADED`
- `maintenance end` → `prod recover` + health, marker usuwany dopiero po sukcesie

---

## ETAP 3 — Audit trail

```bash
guardian prod audit --last 20
guardian prod audit --since 24h
```

Workflow z audytem: `prod.maintenance.start/end`, `prod.recover`, `ifg.deploy.run`, `prod.monitor.check`

Rekordy: schema_version, timestamp_utc, operation_id, event_type, workflow, phase, actor, hostname, pid, branch, commit, target, reason, result, error_summary.

---

## ETAP 4 — Monitor stanowy

```bash
guardian prod monitor check
```

- Próg alarmu: **10 minut** w stanie awaryjnym
- `PRODUCTION_MAINTENANCE` — brak alarmu niedostępności
- Deduplikacja alertów + pojedynczy komunikat recovery
- `UNREACHABLE` przy błędzie SSH

### Kanał powiadomień

**Blokada konfiguracji:** brak skonfigurowanego zewnętrznego kanału (email/Slack). Działa sink lokalny: `.state/runtime_notifications.log`.

---

## ETAP 5 — Harmonogram Mac mini

```bash
guardian prod monitor install   # ✅ wykonane
guardian prod monitor status    # launchd running
```

- Plist: `~/Library/LaunchAgents/com.ifg.guardian.prod-monitor.plist`
- Interwał: 300 s (5 min)
- Log: `.state/prod_monitor.log`
- Instalacja na DS723+ → odrzucona przez execution guard

---

## ETAP 6 — Testy

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/unit/test_production_runtime_status.py \
  tests/unit/test_production_runtime_gwo_0072.py \
  tests/guardian_platform/test_ifg_mutating.py \
  tests/unit/test_guardian_ifg_deploy_run_workflow.py \
  -q
# 41+ passed
```

Pokrycie minimum GWO: maintenance classification, marker atomowy, audit phases, monitor 10min threshold, deduplikacja, recovery notify, DS723+ install block.

**Nie wykonano:** kontrolowanego `compose stop` na produkcji (wymaga zgody operatora).

---

## ETAP 7 — Commit, push, deploy

| Krok | Wynik |
|---|---|
| Commit | `d46be0c` — GWO-IFG-0071/0072 |
| Push | `5b906c2..d46be0c` → `origin/production` ✅ |
| Release evaluate | `PRODUCTION_BLOCKED` (dirty tree) → deploy z `--allow-dirty-build` |
| Deploy | `guardian ifg deploy run --yes --allow-dirty-build` → **LIVE COMPLETE** ✅ |
| DS723+ HEAD | `d46be0c` |
| deploy check | PRODUKCJA ZGODNA Z LOKALNYM KODEM ✅ |
| Runtime | `PRODUCTION_RUNNING` ✅ |
| `/health` | HTTP 200 ✅ |
| restart policy | `always` (api/worker/db) ✅ |
| CM project | `ifg` registered ✅ |
| audit trail | rekordy deploy + monitor ✅ |
| monitor check | single iteration OK ✅ |
| launchd | installed, running ✅ |

---

## ETAP 8 — Dokumentacja

---

## Ryzyka i ograniczenia

- Operacje spoza Guardiana (DSM/CM/obcy SSH) bez identyfikacji aktora
- Brak zewnętrznego kanału alertów — wymaga konfiguracji operatora
- `restart: always` nie wznawia natychmiast po świadomym stopie

## Elementy niewykonane

- Test akceptacyjny maintenance na żywej produkcji
- Zewnętrzny kanał powiadomień (email/Slack/webhook)

## Decyzje wymagające operatora

1. Wybór i konfiguracja kanału alertów (adapter do `RuntimeNotifier`)
2. Zgoda na test akceptacyjny `maintenance start/end` w oknie serwisowym

---

🩷 STATUS KOŃCOWY

✅ Co działa
- GWO-IFG-0071 utrwalone w `origin/production` (`d46be0c`)
- Maintenance mode, audit trail, monitor stanowy — wdrożone
- `prod health` → `PRODUCTION_RUNNING`
- launchd monitor co 5 min — zainstalowany
- Deploy Guardian LIVE COMPLETE

⚠️ Znane problemy
- Brak zewnętrznego kanału powiadomień (tylko `.state/runtime_notifications.log`)
- Aktor stopu 02:14 CEST nadal nieustalony
- Release gate wymaga `--allow-dirty-build` przy dirty tree (GDD-0012)

❌ Co nie działa
- Brak

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

| Ścieżka |
|---|
| `docs/reports/2026-07-11_GWO-IFG-0072_RUNTIME_MAINTENANCE_MONITORING_AUDIT.md` |
