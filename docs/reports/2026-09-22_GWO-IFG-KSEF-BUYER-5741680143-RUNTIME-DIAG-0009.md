# GWO-IFG-KSEF-BUYER-5741680143-RUNTIME-DIAG-0009

Data: 2026-09-22  
Cel: diagnostyka blokady wysyłki KSeF dla NIP 5741680143 po deploy `e0a53b0` — **READ-ONLY**.

## WYNIK

```
STATUS: DIAG_COMPLETE
DEPLOYED_SHA: e0a53b0bf673f2243fca90d522edf999622224ae
FRONTEND_BUILD_CURRENT: YES
INVOICE_ID: c7643dfd-cdb7-4913-8353-20bd16f98b8f
FRONTEND_BLOCK_SOURCE: InvoiceActions.jsx → isBuyerSnapshotComplete(invoice.buyer_snapshot) → canBuildAdresL1(snapshot)
FRONTEND_MISSING_FIELDS: place_line (street | building_no | apartment_no) — brak; jest tylko postal_code + city
REGON_DATA: city=Prusicko postal=98-331 street=null building_no=null (source=regon)
OVERRIDE_DATA: (brak wiersza contractor_overrides)
EFFECTIVE_DATA: = REGON (bez override)
BUYER_SNAPSHOT: nip=5741680143 city=Prusicko postal_code=98-331 street=null building_no=null apartment_no=null
FA3_ADRESL1: "98-331 Prusicko" (format) ALE can_build_adres_l1=False
FRONTEND_CAN_SEND: false
BACKEND_VALIDATION: FAIL (ten sam predykat AdresL1 / minimum address)
FA3_MAPPING: FAIL (brak sensownego AdresL1 wg can_build)
ROOT_CAUSE: F — REGON/snapshot mają wyłącznie miejscowość+kod; brak ulicy/numeru budynku → wspólna logika AdresL1 celowo blokuje
MINIMAL_FIX: edycja nabywcy na tej fakturze (np. building_no / street) + zapis → regeneracja buyer_snapshot; opcjonalnie override kontrahenta
DATA_FIX_REQUIRED: YES
CODE_FIX_REQUIRED: NO
VERDICT: DATA_INCOMPLETE_ADDRESS_NOT_DEPLOY_BUG
```

## ETAP 1 — RUNTIME

| Check | Wynik |
|---|---|
| Host `git rev-parse HEAD` | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| FE dist | `index-BWXliTm-.js` (2026-09-22 23:22) |
| String `Uzupełnij dane nabywcy na fakturze…` w dist | **TAK** |
| Logika AdresL1 (village / `m. ` / `building_no`) w dist | **TAK** |
| Kontener API: `app/domain/party_address.py` | **istnieje** |

**FRONTEND_BUILD_CURRENT = YES** — nie STOP na starym bundlu.

## ETAP 2 — ŹRÓDŁO KOMUNIKATU

```
frontend-react/src/components/invoice/InvoiceActions.jsx
  BUYER_INCOMPLETE_MSG
  isBuyerSnapshotComplete(snapshot):
    name && nip && canBuildAdresL1(snapshot)
  buyerIssue = !isBuyerSnapshotComplete(invoice.buyer_snapshot)
  → sendBlocked / disabled + komunikat
```

Źródło danych: **`invoice.buyer_snapshot`** (zapisany na fakturze), **nie** live contractor/override przy kliknięciu Wyślij.

`canBuildAdresL1` (`partyAddress.js`) wymaga:
- `address` **lub**
- `(street|building_no|apartment_no)` **oraz** `(postal_code && city)`

**Nie** ma starego twardego `street && building_number` jako jedynego warunku.

## ETAP 3 — FAKTURA (prod, read-only)

| Pole | Wartość |
|---|---|
| id | `c7643dfd-cdb7-4913-8353-20bd16f98b8f` |
| number_local | `FV/22/09/2026` |
| issue_date | `2026-09-18` (UI „18-09-2026” = data; nie mylić z numerem) |
| status | `ready_for_submission` |
| gross | `1200.05` |
| buyer NIP | `5741680143` |
| buyer name | PARAFIA RZYMSKOKATOLICKA… |
| city / postal | Prusicko / 98-331 |
| street / building / apartment | **null** |

## ETAP 4 — CONTRACTOR + OVERRIDE

| Warstwa | Treść |
|---|---|
| REGON_DATA | contractor `7c9bb5e0-…`, source=regon; city+postal; street/building puste |
| OVERRIDE_DATA | **brak** |
| EFFECTIVE_DATA | = REGON |
| BUYER_SNAPSHOT | zgodny z REGON (locality-only) |
| FA3_ADRESL1 | format → `98-331 Prusicko`; **can_build = false** |

**Czy override istnieje, a faktura ma stary snapshot?**  
**NIE** — override nie istnieje; snapshot = aktualne (niepełne) dane REGON.

## ETAP 5 — FRONTEND VS BACKEND

| Gate | Wynik |
|---|---|
| FRONTEND_CAN_SEND | **false** (`canBuildAdresL1` na snapshot) |
| BACKEND_VALIDATION | **FAIL** (`can_build_adres_l1` / `_validate_party_snapshot`) |
| FA3_MAPPING | **FAIL** (brak kwalifikującego AdresL1) |

Wyniki **zgodne** — nie ma rozjazdu FE vs BE.

Dowód: z `building_no='10'` obie strony → PASS (`Prusicko 10, 98-331 Prusicko`).

## ETAP 6 — SCENARIUSZE

| ID | Werdykt |
|---|---|
| A stary FE gate street&&building | **ODRZUCONY** |
| B stary snapshot mimo override | **ODRZUCONY** (brak override) |
| C override nie zapisany | **N/A** — nie było override; REGON i tak bez numeru |
| D stary build FE | **ODRZUCONY** |
| E backend nadal odrzuca inaczej niż FE | **ODRZUCONY** (oba FAIL tak samo) |
| F inna konkretna | **POTWIERDZONY** — brak place_line w danych |

## ETAP 7 — MINIMALNA NAPRAWA (bez wdrożenia)

1. **DATA (preferowane):** otwórz fakturę → uzupełnij adres nabywcy (np. numer budynku / ulica) → zapisz → nowy `buyer_snapshot`.  
2. **Opcjonalnie:** zapisz `contractor_override` dla NIP 5741680143, żeby kolejne faktury nie powtarzały luki REGON.  
3. **NIE** globalnie przepisywać historycznych snapshotów.  
4. **CODE_FIX_REQUIRED = NO** dla tego przypadku (logika AdresL1 działa zgodnie z projektem).

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

*(diag only — deploy już był w 0008; tu brak zmian kodu)*

## Decyzje dla ChatGPT

1. Czy operator uzupełnia `building_no`/ulicę ręcznie na fakturze `c7643dfd-…` i zapisuje override kontrahenta?
2. Czy potrzebny osobny UX hint „REGON bez numeru domu — uzupełnij ręcznie” (opcjonalny follow-up, poza tym GWO)?
