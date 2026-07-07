# KSEF_SCHEDULER

## Architektura

Scheduler auto-sync KSeF jest zintegrowany z istniejącym procesem workera i nie wymaga
osobnego procesu.

```
Worker loop
  ├─ scheduler tick (raz na minutę)
  │   ├─ read KSEF_AUTO_SYNC_ENABLED
  │   ├─ read KSEF_AUTO_SYNC_CRON
  │   ├─ evaluate due slot / recovery
  │   └─ enqueue BackgroundJob(job_type="sync_purchase_invoices", incremental=true)
  └─ existing job polling/execution
```

## Przepływ działania

1. Worker uruchamia pętlę główną.
2. Na początku każdej iteracji wykonywany jest scheduler tick.
3. Tick uruchamia się maksymalnie raz na minutę.
4. Scheduler wylicza ostatni należny slot z CRON (`minute hour * * *`).
5. Jeśli slot nie był jeszcze wykonany:
   - enqueue do `background_jobs`,
   - zapis `last_executed_slot` w `ksef_sync_states` (`scope=ksef_purchase_auto_scheduler`).
6. Synchronizację wykonuje istniejący handler `sync_purchase_invoices`.

## Recovery (missed run)

- Po restarcie workera scheduler wylicza ostatni należny slot `<= now`.
- Jeśli ten slot nie jest równy `last_executed_slot`, enqueue zostaje wykonany raz.
- Gdy worker był wyłączony długo, nadrabiany jest wyłącznie **ostatni** brakujący slot.

## Idempotencja

- Klucz idempotencji harmonogramu: `slot_key = YYYY-MM-DDTHH:MM`.
- `last_executed_slot` jest persistowany w `ksef_sync_states`.
- Ponowny start workera w tym samym slocie nie powoduje podwójnego enqueue.

## Telemetria w Monitorze KSeF

Scheduler zapisuje zdarzenia przez `KSeFTransmissionJournalService`:

- `SCHEDULER_STARTED`
- `SCHEDULER_TICK`
- `SCHEDULER_SLOT`
- `SCHEDULER_ENQUEUE`
- `SCHEDULER_SKIP_ALREADY_EXECUTED`
- `SCHEDULER_RECOVERY`
- `SCHEDULER_DISABLED`

## Dlaczego takie rozwiązanie

- Brak nowych komponentów infrastrukturalnych.
- Pełna zgodność z istniejącą architekturą IFG:
  - worker + kolejka `background_jobs` + istniejące handlery.
- Prosty model operacyjny:
  - restart workera wystarcza do przeładowania ENV i CRON.
