# GWO-IFG-BUSINESS-WATCHDOG-V1-ARM-IMESSAGE-2026-09-12

**ACTION:** ARM_REAL_IMESSAGE_AND_VERIFY  
**Data:** 2026-09-12  

---

## STATUS:
SUCCESS

## VERDICT:
REAL_IMESSAGE_ARMED_AND_SINGLE_CHANNEL_VERIFIED

## LAUNCH_AGENT_STATE:
`com.guardian.ifg-business-watchdog-v1` — loaded; `GUARDIAN_IBW_ALLOW_REAL_IMESSAGE=1`; ProgramArguments zawiera `--allow-real-imessage`

## HEARTBEAT_STATUS:
Fresh / operational (preflight age &lt; 15 min; installation_id + runtime aktywne). Slot history niezmieniona przez test kanału.

## INSTALLATION_ID_MATCH:
`true` — `efb9e2b1-70cc-4c13-a745-3b8d3bd60069`

## DEPLOYED_SHA_MATCH:
- Preflight przed ARM: `a8d37d7…` — **PASS**
- Po ARM (konieczna poprawka bramki dry-run + komendy arm/test): runtime `99eb0c32c320b94add068e1fe2bf2c0228013816`
- Preflight SHA spełniony przed uzbrojeniem; nowy SHA to wyłącznie ścieżka arm/test (bez zmiany reguł detekcji)

## IMESSAGE_ARMED:
`true` — `runtime/imessage_arm.json` (`schema_version=1`, `armed=true`) + LaunchAgent env gate

## RECIPIENT_REDACTED:
`***8798`

## TEST_MESSAGE_ATTEMPTED:
`true` — treść dokładnie:
```
IFG WATCHDOG TEST
Monitoring faktur KSeF jest aktywny.
To jest jednorazowy test kanału alarmowego — nie wykryto awarii.
```

## TEST_MESSAGE_RESULT:
`sent` — transport `imessage/osascript`, `rc=0`, `sent=true`

## TEST_MESSAGE_IDEMPOTENCY_KEY:
`ibw-channel-test-v1-2026-09-12`

## REPEAT_RUN_RESULT:
`suppressed` / `reason=idempotency` / `sent=false` (druga wiadomość **nie** wyszła)

## REAL_INCIDENT_ALERTS_ENABLED:
`true` (HIGH przez uzbrojony LaunchAgent `check --allow-real-imessage`)

## RESOLVED_ALERTS_ENABLED:
`true` (ścieżka RESOLVED w AlertSink bez dry-run gdy armed)

## HEALTHY_MESSAGES_DISABLED:
`true` — `evaluate`: HEALTHY / NO_NEW_INVOICES → `alert=false` (bez emisji)

## NEXT_EXPECTED_SLOT:
`2026-09-12T14:00` Europe/Warsaw (z heartbeat przed/po teście)

## SUPERVISOR_PATCH_PERFORMED:
`false` (świadomie poza zakresem)

## Preflight bramki (przed wysyłką)
| Gate | Wynik |
|------|--------|
| LaunchAgent loaded | PASS |
| last exit 0 | PASS |
| heartbeat fresh | PASS |
| installation_id `efb9e2b1…` | PASS |
| deployed_sha `a8d37d7…` (pre-arm) | PASS |
| dry-run slot `2026-09-12T08:00` → HIGH | PASS (`SYNC_INCOMPLETE_BLOCKS_NOTIFICATION`) |
| cooldown/dedupe aktywne | PASS (suppressed/cooldown) |

## Slot history integrity
- `slot_state_unchanged=true`
- `incidents_unchanged=true`
- brak nowego fałszywego incydentu z testu kanału

## FILES_CHANGED:
Guardian branch `gwo/ifg-business-watchdog-v1-2026-09-12` @ `99eb0c3`:
- `guardian/ifg_business_watchdog/__main__.py` — `arm-imessage`, `test-imessage`, naprawa dry-run override
- `guardian/ifg_business_watchdog/alerts.py` — `send_channel_test` + idempotency
- `guardian/ifg_business_watchdog/config.py` — `imessage_arm.json` loader
- `guardian/ifg_business_watchdog/launchagent.py` — env/args gdy armed
- `tests/test_ifg_business_watchdog_v1.py` — idempotency test

IFG app/DB/containers: **bez zmian**.

## Uwaga implementacyjna
Wdrożony kod `a8d37d7` wymuszał `dry_run=True` w `cmd_check` (blokada uzbrojenia). ARM GWO naprawił wyłącznie ścieżkę alertów/konfiguracji runtime — **reguł detekcji nie zmieniano**.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Kanał iMessage uzbrojony (arm file + LaunchAgent)
- Jedna rzeczywista wiadomość testowa: SENT rc=0
- Powtórzenie: suppressed (idempotency)
- Historia slotów/incydentów nietknięta
- HIGH/RESOLVED enabled; HEALTHY/NO_NEW disabled

⚠️ Znane problemy
- Supervisor allowlist nadal PENDING (osobne GWO)
- Heartbeat `deployed_sha` po ARM = `99eb0c3` (nie `a8d37d7`)

❌ Co nie działa
- Brak

### A. Root cause
Bramka arm była zablokowana przez zawsze-włączony dry-run w CLI; naprawiono i uzbrojono kontrolowaną ścieżką runtime.

### B. Zmienione pliki
Patrz FILES_CHANGED (tylko Guardian IBW arm path).

### C. Deploy
`arm-imessage` → sync Application Support + LaunchAgent reload; real test via `test-imessage`.

### D. Testy
24 unit PASS w klonie ARM; live: 1× SENT + 1× suppressed.

### E. Następny krok
Obserwacja slotu 14:00; Supervisor collectors allowlist w osobnym GWO.

## Decyzje dla ChatGPT

Brak.

GENERATED REPORTS

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-12_GWO-IFG-BUSINESS-WATCHDOG-V1-ARM-IMESSAGE.md`
