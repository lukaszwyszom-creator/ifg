# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001

Data: 2026-09-22
Repo: `/Users/lukasz/projekty/ifg_standalone`
Branch: `production` (bez commit / push / deploy)

## Separacja artefaktów (nie mieszać w commicie KSeF)

Istniejące, **niezwiązane** zmiany (Cursor/npm/Guardian/docs) — **nie commitować** razem z tą poprawką:

- `frontend-react/package.json` (EOL / npm task provider)
- `docs/reports/2026-09-22_GWO-IFG-CURSOR-*`
- Guardian: `scripts/ifg_guardian/**`, `tests/unit/test_guardian_*`
- inne historyczne `docs/reports/2026-07*`, `2026-08*`, `2026-09-12*`, `docs/gwo/`

Do ewentualnego osobnego commitu KSeF (gdy użytkownik poprosi): tylko pliki z sekcji FILES_CHANGED poniżej.

`npm.autoDetect=off` w User Settings Cursora — **nietknięte**.

---

## ETAP 1 — DIAGNOZA

### ROOT_CAUSE

Backendowa walidacja `_has_minimum_address` wymagała `(street ∨ building_no ∨ apartment_no) ∧ (city ∨ postal_code)`.

Gdy REGON zwraca NIP/nazwę/miejscowość/kod **bez** ulicy i **bez** numeru, snapshot nabywcy nie przechodzi `validate_sale_formal_requirements` → komunikat:

`Niekompletny snapshot nabywcy: wymagane minimum danych adresowych.`

mapowany w `TransmissionService._friendly_submit_error` na:

`Uzupełnij dane nabywcy na fakturze przed wysyłką do KSeF.`

Dodatkowo generator FA(3) `_format_adres_l1` przy pustym `street` i obecnym `building_no` składał `"10, 98-331 Prusicko"` zamiast `"Prusicko 10, 98-331 Prusicko"`.

Frontend: pola nabywcy były **read-only** (NIP + nazwa) — brak UI do ręcznego uzupełnienia mimo istniejącego API `PATCH /contractors/{id}/override`.

### CURRENT_DATA_FLOW

```
REGON (RegonClient/Mapper)
  → ContractorORM (street/building nullable, source=regon)
  → opcjonalnie ContractorOverrideORM (już w schema)
  → InvoiceService._resolve_buyer_snapshot (merge override)
  → invoice.buyer_snapshot_json
  → validate_sale_formal_requirements / _has_minimum_address
  → FA3Mapper._format_adres_l1 → Podmiot2/Adres/KodKraju + AdresL1
```

### BLOCKING_VALIDATION

| Warstwa | Blokada |
|---|---|
| Frontend (przed zmianą) | Brak pre-check nabywcy; błąd dopiero po submit KSeF |
| Backend domain | `_has_minimum_address` — **street/building required** (nie AdresL1) |
| Generator XML | Nie blokował sam; złe składanie linii bez ulicy |
| DB constraints | **Nie** — street/building nullable |

### DB_CHANGE_NEEDED

`NO` — `contractors` + `contractor_overrides` wystarczają; ręczna korekta = override.

---

## ETAP 2 — IMPLEMENTACJA

### Zmiany

1. `app/domain/party_address.py` — `format_adres_l1` / `can_build_adres_l1` (street **nie** wymagane; wieś: `{city} {building_no}, {postal} {city}`).
2. Walidacja sale używa `can_build_adres_l1` (wymaga place-line + **postal i city**).
3. FA(3) mapper używa wspólnego `format_adres_l1`.
4. Override merge: `is not None` (ręczna korekta ma pierwszeństwo po niepełnym REGON refresh).
5. UI: edytowalny adres nabywcy; zapis przez `updateOverride`; klik „Uzupełnij dane nabywcy” otwiera edycję faktury.

### Przykłady AdresL1

| Wejście | AdresL1 |
|---|---|
| ul. Testowa + 10 + 00-001 Warszawa | `ul. Testowa 10, 00-001 Warszawa` |
| (bez street) + 10 + 98-331 Prusicko | `Prusicko 10, 98-331 Prusicko` |
| Moczydła + 2 + 98-331 Prusicko | `Moczydła 2, 98-331 Prusicko` |
| tylko 98-331 Prusicko | **BLOCK** |

---

## STATUS

`IMPLEMENTED_LOCAL_REVIEW`

## ROOT_CAUSE

Walidacja wymagała sztucznej linii „ulicy/numeru” zamiast możliwości zbudowania AdresL1; brak UI override mimo gotowego modelu DB.

## FILES_CHANGED

- `app/domain/party_address.py` (new)
- `app/domain/models/invoice.py`
- `app/integrations/ksef/mapper.py`
- `app/services/contractor_service.py`
- `frontend-react/src/components/invoice/partyAddress.js` (new)
- `frontend-react/src/components/invoice/partyAddress.test.js` (new)
- `frontend-react/src/components/invoice/InvoiceForm.jsx`
- `frontend-react/src/components/invoice/InvoiceForm.module.css`
- `frontend-react/src/components/invoice/InvoiceActions.jsx`
- `frontend-react/src/components/invoice/InvoiceCardList.jsx`
- `frontend-react/src/api/contractors.js`
- `tests/unit/test_ksef_partial_regon_address.py` (new)
- `docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001.md` (this)

## DB_MIGRATION

`NO`

## TESTS

```text
python3 -m pytest tests/unit/test_ksef_partial_regon_address.py -q
→ 15 passed

node --test frontend-react/src/components/invoice/partyAddress.test.js
→ 4 passed
```

Pokrycie wymagań: pełny adres PASS; brak street + building PASS; brak danych BLOCK; override merge PASS; FA(3) KodKraju+AdresL1 PASS.
Bez realnej wysyłki KSeF.

## UX_BEFORE

- REGON częściowy → submit KSeF → toast/error „Uzupełnij dane nabywcy…”
- Formularz: NIP + nazwa read-only, brak edycji adresu
- Output Tasks UI mylący w innych GWO (niezwiązane)

## UX_AFTER

- Formularz pokazuje adres z REGON + edycję ulicy/numeru/kodu/miasta
- Alert przy niepełnym AdresL1; zapis → `contractor_overrides`
- Kafelek KSeF: „Uzupełnij dane nabywcy…” klikalne → otwiera edycję faktury
- Kolejna faktura tego NIP dostaje adres z override

## FA3_BEFORE

- Bez street: AdresL1 typu `10, 98-331 Prusicko` (jeśli w ogóle doszło do generacji)
- Często blokada przed generacją

## FA3_AFTER

- `KodKraju=PL`
- AdresL1 zgodne z przykładami powyżej

## RISK

| Ryzyko | Mitigacja |
|---|---|
| Seller company settings nadal wymagają street∨building (osobna ścieżka) | Poza zakresem GWO nabywcy |
| Override z pustym street=null nie „czyści” REGON street | Zamierzone; wieś OK |
| LOCAL only — brak weryfikacji na DS723 | NEXT_STEP: review + deploy osobnym GWO |

## VERDICT

`READY_FOR_LOCAL_REVIEW` — logika AdresL1 + override + UI lokalnie z regresjami PASS; bez PROD.

## NEXT_STEP

1. Lokalny review UI: NIP z częściowym REGON → uzupełnij numer → zapisz → Wyślij (bez PROD / bez real KSeF jeśli nie chcesz).
2. Osobny commit **tylko** plików KSeF z FILES_CHANGED (bez artefaktów Cursor/Guardian).
3. Deploy DS723 osobnym GWO po akceptacji.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED
