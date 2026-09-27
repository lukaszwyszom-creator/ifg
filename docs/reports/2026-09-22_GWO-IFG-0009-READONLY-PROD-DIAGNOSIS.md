# GWO-IFG-0009 — READ-ONLY production diagnosis (DS723)

**Date:** 2026-09-22  
**Scope:** SSH read-only diagnostics only. No writes, no deploy, no KSeF send, no DB UPDATE/DELETE/INSERT.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Diagnosis only — no app change.)

---

## 1. RUNTIME

| Check | Result |
|-------|--------|
| Host `git rev-parse HEAD` | `e0a53b0bf673f2243fca90d522edf999622224ae` (matches expected `e0a53b0…`) |
| Branch | `production...origin/production` |
| Container `party_address.py` | **exists** (`/app/app/domain/party_address.py`) |
| Container GIT_SHA env | `n/a` (not labeled) |
| Frontend asset | `frontend-react/dist/assets/index-BWXliTm-.js` (911545 bytes, mtime Sep 22 23:22) |

### Frontend build markers

| String / pattern | Present in `index-BWXliTm-.js` |
|------------------|-------------------------------|
| `Uzupełnij dane nabywcy na fakturze` | **YES** (count=1) — send-block message |
| `Uzupełnij dane nabywcy — REGON…` / AdresL1 form msgs | **YES** |
| `canBuildAdresL1` (unminified name) | **NO** (count=0; name minified) |
| `building_no` | **YES** (count=3) |
| `postal_code` | **YES** (count=3) |
| Village / `m. ` AdresL1 compose logic | **YES** (minified: `` `${o} ${r}` `` / `` `m. ${a}` ``) |

`party_address` header in container (first lines) confirms FA(3) AdresL1 / REGON-incomplete address module is deployed.

---

## 2. INVOICE

**Matched sale invoice** (NIP `5741680143`, gross `1200.05`):

| Field | Value |
|-------|-------|
| id | `c7643dfd-cdb7-4913-8353-20bd16f98b8f` |
| number_local | `FV/22/09/2026` (not `18-09-2026`; that number is a *different* invoice / other NIP) |
| issue_date | `2026-09-18` |
| direction | `sale` |
| status | `ready_for_submission` |
| totals | net `1142.90`, vat `57.15`, gross **`1200.05`** |
| transmissions | **none** |

### buyer_snapshot_json (full)

```json
{
  "krs": null,
  "nip": "5741680143",
  "city": "Prusicko",
  "name": "PARAFIA RZYMSKOKATOLICKA PW. ŚWIĘTEJ BARBARY",
  "regon": "040045514",
  "county": "pajęczański",
  "street": null,
  "commune": "Nowa Brzeźnica",
  "country": "PL",
  "legal_form": "P",
  "building_no": null,
  "postal_code": "98-331",
  "voivodeship": "ŁÓDZKIE",
  "apartment_no": null
}
```

**Address gap:** `street` / `building_no` / `apartment_no` all null — locality only (`postal_code` + `city`).

Note: query by `issue_date = 2026-09-22` returned 0 sale rows; this invoice’s issue_date is **2026-09-18**.

---

## 3. CONTRACTOR

| Field | Value |
|-------|-------|
| id | `7c9bb5e0-ee9b-423d-bf25-c5155dda6acf` |
| nip | `5741680143` |
| regon | `040045514` (cached) |
| name | PARAFIA RZYMSKOKATOLICKA PW. ŚWIĘTEJ BARBARY |
| street / building_no | **NULL / blank** |
| postal_code / city | `98-331` / `Prusicko` |
| commune / county / voivodeship | Nowa Brzeźnica / pajęczański / ŁÓDZKIE |
| source | `regon` |
| lookup_last_status | `success` |
| source_fetched_at | 2026-09-22 17:10:28 +02 |
| cache_valid_until | 2026-09-29 17:10:28 +02 |

**contractor_overrides:** **0 rows** (no active override).

REGON `raw_payload_json` confirms empty `Ulica`, `NrNieruchomosci`, `NrLokalu`; filled `Miejscowosc=Prusicko`, `KodPocztowy=98-331`, `Regon=040045514`.

---

## 4. EFFECTIVE AdresL1 (API container, read-only)

Snap = invoice `buyer_snapshot` above.

| Check | Result |
|-------|--------|
| `can_build_adres_l1(snap)` | **False** |
| `format_adres_l1(snap)` | `'98-331 Prusicko'` (locality-only; insufficient for FA(3) gate) |
| `_has_minimum_address(snap)` | **False** |
| `Invoice._validate_party_snapshot(..., label='nabywcy')` | **FAIL** `InvalidInvoiceError: Niekompletny snapshot nabywcy: wymagane minimum danych adresowych.` |
| Hypothetical `building_no='10'` | `can_build=True`, AdresL1=`'Prusicko 10, 98-331 Prusicko'` |

Full `validate_for_ksef()` via ORM load was not completed in-container (SessionLocal/repo path blocked by sandbox policy once); party-level gate above is the same predicate `_has_minimum_address` → `can_build_adres_l1` used by sale formal validation / friendly TX message mapping to *„Uzupełnij dane nabywcy na fakturze przed wysyłką do KSeF.”*

---

## 5. Frontend completeness (same snap)

`isBuyerSnapshotComplete` = `name && nip && canBuildAdresL1(snapshot)`  
→ **False** (name+nip OK; AdresL1 gate fails).

FE dist contains the send-block string and AdresL1/REGON incomplete UX copy — consistent with UI blocking submit for this invoice.

---

## Verdict

Production at SHA `e0a53b0…` has party_address + FE buyer-incomplete messaging. Invoice `FV/22/09/2026` / `c7643dfd-…` cannot build AdresL1 because REGON returned village+postal only (no street/building). Contractor matches snapshot; no override. Root cause is **incomplete address data**, not missing deploy of AdresL1 logic.

## Decyzje dla ChatGPT

1. Czy uzupełnić `building_no` (adres wiejski) ręcznie / override dla NIP 5741680143, czy inny proces źródła adresu?
2. Czy po uzupełnieniu wystarczy edycja faktury (nowy buyer_snapshot), bez nowego deployu?

## GENERATED REPORTS

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-22_GWO-IFG-0009-READONLY-PROD-DIAGNOSIS.md`
