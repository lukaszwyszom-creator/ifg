# GWO-IFG-SYNC-COMPLETENESS-FIX-AND-NOTIFICATION-BACKFILL-2026-09-12

**Data:** 2026-09-12  
**Repo:** `/Users/lukasz/projekty/ifg_standalone` (implementacja w worktree `/tmp/ifg-sync-completeness-fix`)  
**Prod:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`

---

## STATUS:
SUCCESS

## VERDICT:
FIX_DEPLOYED_AND_SINGLE_BACKFILL_SENT

## ROOT_CAUSE_CONFIRMED:
YES — audyt kompletności używał `list_ksef_purchase_refs_in_issue_range` (filtr `issue_date`), więc istniejący `ksef_reference_number` z wcześniejszą datą wystawienia (Alior `issue_date=2026-08-29` przy oknie od `2026-08-30`) dawał fałszywy `metadata_not_in_db` → `incomplete=True` → brak enqueue maila mimo `saved>0`.

## PREVIOUS_HEAD:
`42b77faf5b5ba37d250bb76fba1d5ae193dd8235`

## FINAL_HEAD:
`40e6445b59dced074c76aa2b62d450aa36bb38da`

## COMMIT:
`40e6445` — `fix: key purchase sync completeness by ksef_reference_number`

Pliki:
- `app/persistence/repositories/invoice_repository.py` — `list_existing_ksef_purchase_refs`
- `app/services/ksef_session_service.py` — finalize po dokładnym numerze KSeF
- `app/services/purchase_sync_email_notifier.py` — temat/treść backfill
- `app/services/purchase_sync_notify_backfill.py` — jednorazowy backfill + idempotency
- testy: `test_ksef_sync_completeness_ksef_ref.py` + fake repo updates

## TESTS_TARGETED:
`80 passed` — completeness + purchase sync audit/email/resume/session/sync service

## TESTS_FULL:
`1442 passed`, `27 failed` (niezwiązane z tą zmianą: PDF/guardian handoff/preflight/numbering/domain — pre-existing / env). Regresje KSeF sync po fixie: **0**.

## DEPLOYED_SHA:
`40e6445b59dced074c76aa2b62d450aa36bb38da`  
Deploy: `guardian ifg deploy run --yes` z czystego klona `/tmp/ifg-release-completeness-40e6445`  
Image label `ifg.git.commit` = ten sam SHA. Workflow SUCCESS.

## PROD_HEALTH:
| Usługa | Stan po settle |
|--------|----------------|
| db | healthy |
| api | healthy + `/health` ok |
| worker | healthy |
| frontend | running |
| scheduler | `last_executed_slot=2026-09-12T08:00`, cron `0 8,14,20 * * *` |

## HISTORICAL_CASE_FIXED:
**True** (read-only w kontenerze api):
- Alior ref w DB, `issue_date=2026-08-29`
- `early_in_issue_range=False` (stary bug)
- `early_in_exact_lookup=True`
- `incomplete_with_exact_lookup=False`

## BACKFILL_EXPECTED_COUNT:
11

## BACKFILL_ACTUAL_COUNT:
11

### Zbiór (ID + ksef_ref — bez danych wrażliwych kontrahenta)

| # | invoice_id | ksef_reference_number |
|---|------------|------------------------|
| 1 | `910d3dad-9986-4e85-b69e-53d1e9991241` | `5540233408-20260901-4E8368800004-2F` |
| 2 | `5e8817c9-d375-4216-b5f3-6c8b02c62c31` | `6972413365-20260901-A32D74400000-52` |
| 3 | `f619560c-4a33-4b71-95da-e58868ded1d9` | `5260250995-20260903-8F13F5400109-5C` |
| 4 | `7dd2c56e-bbc3-4a17-a509-932117de7127` | `5731114146-20260904-6048FEC00004-00` |
| 5 | `677b77fe-ce63-41a8-baf4-14a8702cb1b9` | `5540162849-20260908-44C3F5C00026-99` |
| 6 | `3c556acb-537e-42be-828b-881e98a436b3` | `8762469751-20260908-4F1BF4400021-52` |
| 7 | `e86825b0-bf8d-42f4-a84a-3ad9d3e64c51` | `7440004589-20260909-4D2574400001-EF` |
| 8 | `67535966-24c6-455c-97c4-c1992774d031` | `5611563887-20260909-68E1F4400004-8D` |
| 9 | `4249da12-a3d1-40db-950d-732523eb19b2` | `6050016561-20260909-7EFD6D800001-B0` |
| 10 | `003e201d-c21d-4643-aab8-ce17fe54f059` | `7392094211-20260909-8524ED800002-AA` |
| 11 | `da577a32-e106-4a22-90cc-a7baaa63c5f7` | `9512120077-20260912-0805490004A8-9F` |

Dowód braku wcześniejszego SENT: żadne z powyższych ID nie występuje w `purchase_sync_notifications` ze `status=SENT` sprzed backfillu; ostatni SENT mail: **2026-09-01 08:00**.

## BACKFILL_EMAIL_ATTEMPTED:
YES

## BACKFILL_EMAIL_RESULT:
**SENT**  
- wiersz `purchase_sync_notifications` correlation `a11c0ffe-2026-0912-b001-000000000001`, status **SENT**, `invoice_count=11`, `sent_at=2026-09-12 10:13:42` Europe/Warsaw  
- journal: **1×** `PURCHASE_SYNC_EMAIL` / `email_sent`  
- temat: `Zaległe powiadomienie — faktury zakupowe pobrane od 01.09.2026`  
- Uwaga: skrypt CLI błędnie wypisał `EMAIL_FAILED/PENDING` (refresh sesji przed commit); stan DB + journal potwierdzają SENT. `attempt_count=2` — możliwy race api-exec vs worker claim; **jeden** event `email_sent` w journalu.

## BACKFILL_IDEMPOTENCY_KEY:
scope=`purchase_sync_notify_backfill`  
key=`missed-since-2026-09-01T14:00-to-2026-09-12T08:00`  
status=`completed`

## REPEAT_RUN_RESULT:
**ALREADY_SENT** (bez kolejnego maila)

## NEXT_SCHEDULED_SLOT:
`2026-09-12T14:00` Europe/Warsaw (po `last_executed_slot=2026-09-12T08:00`)

## FILES_CHANGED:
(patrz COMMIT; WIP użytkownika w głównym checkoutcie **nietknięty**)

## Operacje
| Akcja | Wynik |
|-------|-------|
| Worktree | użyty, usunięty po zakończeniu |
| Push `origin/production` | `42b77fa..40e6445` |
| Deploy LIVE | SUCCESS |
| Testowy mail | nie (tylko backfill produkcyjny) |
| Harmonogram / SMTP ENV | nie zmieniane |

## RELEASE STATE
- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [x] DEPLOYED_TO_DS723
- [x] PRODUCTION_VERIFIED *(health + historical case + backfill SENT)*

## Decyzje dla ChatGPT
Brak.

## GENERATED_REPORTS:
`/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-12_GWO-IFG-SYNC-COMPLETENESS-FIX-AND-NOTIFICATION-BACKFILL.md`
