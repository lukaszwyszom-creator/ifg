# GWO-IFG-BUSINESS-WATCHDOG-V1-2026-09-12

**ACTION:** DESIGN_IMPLEMENT_TEST_DEPLOY_VERIFY  
**Data:** 2026-09-12  

---

## STATUS:
PARTIAL

## VERDICT:
CODE_READY_DEPLOYMENT_OR_REAL_IMESSAGE_APPROVAL_PENDING

Watchdog **wdrożony i aktywny** (LaunchAgent loaded, check exit 0, heartbeat fresh).  
Prawdziwy iMessage **nie został wysłany** — wymaga jawnej bramki `GUARDIAN_IBW_ALLOW_REAL_IMESSAGE=1` + `--allow-real-imessage` (`NEEDS_REAL_IMESSAGE_APPROVAL`).

## REPO:
`/Volumes/WorkspaceSSD/projects/guardian` (izolowany worktree)

## BRANCH:
`gwo/ifg-business-watchdog-v1-2026-09-12`

## PREVIOUS_HEAD:
`ade4dae2b0445c965593b8c82cfc36fd17d05b2f` (`gwo/guardian-ds723-container-watcher-0001`)

## FINAL_HEAD:
`1790873af2feafaafca19a3f15de26bd389d0fd1`

## COMMIT:
`1790873` (report) / runtime code `a8d37d7` (+ `857e480`, `5c20b4e`, `60b1e84`, `cb7c810`)

## REMOTE_BRANCH:
`origin/gwo/ifg-business-watchdog-v1-2026-09-12`

## ARCHITECTURE:
1. **Deterministyczna warstwa** (`evaluate.py`) — reguły slot/job/sync/notify/backlog; **wyłączny** właściciel alarmu.
2. **Zuch** (`zuch.py`) — Ollama chat, tylko po WARNING/HIGH; timeout 60s; nie mutuje IFG; nie może anulować alarmu.
3. **Alert** (`alerts.py`) — iMessage via osascript (wzorzec PSAG), fingerprint + cooldown 900s, RESOLVED jednorazowy; dry-run domyślnie.
4. **Probe** (`probe.py`) — SSH read-only do DS723 (`psql` SELECT + bounded `docker logs`).
5. **State** — `heartbeat.json`, `incidents.jsonl`, `alert_dedupe.json`, single-instance lock.
6. **LaunchAgent** — internal volume (TCC: brak WorkspaceSSD).

## IFG_ACCESS_MODE:
`read_only` (brak mutacji DB/kodu IFG; brak restartów kontenerów)

## MONITORED_SLOTS:
`08:00`, `14:00`, `20:00` Europe/Warsaw (`0 8,14,20 * * *`)

## GRACE_PERIOD:
`15` minut (self-check LaunchAgent `StartInterval=300s` weryfikuje poprzedni slot po grace)

## DETERMINISTIC_RULES:
- MISSED_SCHEDULER_SLOT / JOB_FAILED / JOB_STALE / JOB_NOT_ENQUEUED / JOB_NOT_CLAIMED → HIGH
- SYNC_INCOMPLETE_BLOCKS_NOTIFICATION (saved>0) → HIGH
- SAVED_WITHOUT_NOTIFICATION / PENDING_OVER_LIMIT / FAILED|SKIPPED → HIGH
- BACKLOG_UNNOTIFIED_INVOICES → HIGH
- PROD_UNREACHABLE_AFTER_RETRIES → HIGH
- saved=0 terminal → NO_NEW_INVOICES (bez alertu)
- saved>0 + SENT → HEALTHY (bez alertu)
- Korelacja **nie** opiera się wyłącznie na `issue_date`

## ZUCH_MODEL:
`qwen2.5-coder:14b` (preflight `GET /api/tags`)

## ZUCH_ENDPOINT:
`http://127.0.0.1:11434`

## ZUCH_TIMEOUT:
`60` s

## ZUCH_FAILURE_FALLBACK:
`ZUCH_UNAVAILABLE` — alarm deterministyczny i tak wychodzi

## ALERT_CHANNEL:
iMessage (Messages.app / osascript) — niezależny od SMTP IFG; recipient z `~/Library/Application Support/Guardian/secrets/psag_watchdog_v2_imessage.env`

## ALERT_RECIPIENT_REDACTED:
`***8798`

## COOLDOWN:
`900` s (15 min); escalation severity / zmiana fingerprint → nowy alert; RESOLVED jednorazowy; dedupe trwałe na dysku

## TARGETED_TESTS:
`22 passed` — `tests/test_ifg_business_watchdog_v1.py` (przypadki 1–20 + heartbeat/mask)

## FULL_TESTS:
`34 passed` — IBW + `tests/test_container_watcher.py` (brak nowych regresji na bazie worktree)

## HISTORICAL_INCIDENT_REPLAY:
Fake + live SSH slot `2026-09-12T08:00` → **HIGH** `SYNC_INCOMPLETE_BLOCKS_NOTIFICATION`  
(metrics: received=15, saved=1, notified=0; backlog live=0 po wcześniejszym backfillu)

## DRY_RUN_RESULT:
PASS — `sent=false` / suppressed w cooldownie; zero osascript send

## LAUNCH_AGENT_LABEL:
`com.guardian.ifg-business-watchdog-v1`

## LAUNCH_AGENT_STATE:
`loaded=true`, `last exit code = 0`, StartInterval 300s  
Plist: `~/Library/LaunchAgents/com.guardian.ifg-business-watchdog-v1.plist`  
Runtime: `~/Library/Application Support/Guardian/ifg-business-watchdog/`

### Plan instalacji (wykonany)
```bash
cd /Volumes/WorkspaceSSD/projects/guardian_worktrees/gwo-ifg-business-watchdog-v1-2026-09-12
PYTHONPATH=$PWD /usr/bin/python3 -m guardian.ifg_business_watchdog install-launchagent --backend ssh --host ds723
/usr/bin/python3 ~/Library/Application\ Support/Guardian/ifg-business-watchdog/runner.py check --dry-run --slot 2026-09-12T08:00
```

## HEARTBEAT_PATH:
`/Users/lukasz/Library/Application Support/Guardian/ifg-business-watchdog/runtime/heartbeat.json`

## HEARTBEAT_STATUS:
Fresh — `status=INCIDENT` (historyczny slot 08:00 nadal bez notify w oknie slotu), `next_expected_slot=2026-09-12T14:00`, `zuch_status=OK`

## INSTALLATION_ID:
`efb9e2b1-70cc-4c13-a745-3b8d3bd60069`

## DEPLOYED_SHA:
`a8d37d7d930098af63fb1223742bb3630a80cd34`

## SUPERVISOR_INTEGRATION:
`PENDING_ALLOWLIST_PATCH` — collectors V1 na osobnej gałęzi; proponowany wpis (read-only):

```python
"ifg-business-watchdog": {
    "path": Path.home() / "Library/Application Support/Guardian/ifg-business-watchdog/runtime/heartbeat.json",
    "root": Path.home() / "Library/Application Support/Guardian/ifg-business-watchdog",
    "ttl_seconds": 600,
    "adapter": "container_watcher",
},
# LAUNCHCTL_LABELS:
"ifg-business-watchdog": "com.guardian.ifg-business-watchdog-v1",
```

Bez mutacji runtime Supervisor w tym GWO.

## REAL_IMESSAGE_SENT:
`false` — **NEEDS_REAL_IMESSAGE_APPROVAL**

## KNOWN_ISSUES:
1. Real iMessage nieuzbrojony (świadomie).
2. Supervisor collectors — brak wpisu allowlist (osobne GWO).
3. Live slot 08:00 klasyfikowany jako INCIDENT (brak notify w oknie slotu) — oczekiwane do kolejnego zdrowego slotu; backlog=0.
4. IFG lokalne WIP **nie** ruszane; kod watchdoga wyłącznie w Guardian.
5. Canonical Guardian SSD HEAD (`airllm`) dirty — użyto izolowanego worktree od container-watcher.

## FILES_CHANGED:
- `guardian/ifg_business_watchdog/**` (nowy pakiet)
- `tests/test_ifg_business_watchdog_v1.py`

## MONITORING_ACTIVE:
**TAK** — LaunchAgent aktywny, self-check co 5 min, read-only wobec IFG.

## RELEASE STATE

- [x] READY_FOR_DEPLOY
- [ ] LOCAL_REVIEW_REQUIRED
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

*(Watchdog Mac mini / Guardian — nie deploy kodu IFG na DS723)*

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Pakiet IBW V1 + 22 testy + dry-run historyczny/live HIGH na incydencie 2026-09-12
- LaunchAgent loaded, exit 0, heartbeat + installation_id + deployed_sha
- Zuch analysis-only; dry-run bez iMessage

⚠️ Znane problemy
- Real iMessage: NEEDS_REAL_IMESSAGE_APPROVAL
- Supervisor allowlist: PENDING

❌ Co nie działa
- Brak uzbrojonego kanału iMessage produkcyjnego (celowe)

### A. Root cause
Referencyjny incydent: false SYNC_INCOMPLETE blokował maile przy healthy kontenerach — watcher infrastrukturalny milczał. IBW V1 zamyka lukę biznesową.

### B. Zmienione pliki
Guardian branch `gwo/ifg-business-watchdog-v1-2026-09-12` @ `a8d37d7`

### C. Deploy
LaunchAgent Mac mini — zainstalowany; merge do bazy Guardian **nie** wykonany.

### D. Testy
22 IBW PASS; 34 z container_watcher PASS

### E. Następny krok
1. Jawna zgoda na real iMessage arm.
2. Patch Supervisor collectors allowlist.
3. Merge branch wg procedury projektu Guardian.
4. Obserwacja slotu 14:00 dziś.

## Decyzje dla ChatGPT

1. Czy uzbroić real iMessage (`GUARDIAN_IBW_ALLOW_REAL_IMESSAGE=1`) w osobnym GWO ARM?
2. Czy dodać allowlist Supervisor w tym samym PR, czy osobnym collectors GWO?

GENERATED REPORTS

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-12_GWO-IFG-BUSINESS-WATCHDOG-V1.md`
