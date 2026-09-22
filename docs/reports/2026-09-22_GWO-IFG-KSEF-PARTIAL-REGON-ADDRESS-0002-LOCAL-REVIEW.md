# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0002-LOCAL-REVIEW

Data: 2026-09-22
Bazowe GWO: `GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001`
Bez commit / push / deploy.

## 1. Git snapshot (przed przeglądem)

```text
git status --short  →  M/?? jak w working tree (KSeF + unrelated WIP)
git diff --stat     →  m.in. invoice/mapper/contractor + InvoiceForm/Actions + noise EOL/Guardian/docs
```

Pełny `git diff` obejmuje też unrelated pliki (Guardian, Cursor reports, `package.json`).
Dla KSeF: `git diff --ignore-cr-at-eol` na plikach logicznych = małe, czytelne hunki.

## 2. Separacja scope

### KSeF-only (ten GWO)

| Plik | Rola |
|---|---|
| `app/domain/party_address.py` | NEW — AdresL1 |
| `app/domain/models/invoice.py` | walidacja → `can_build_adres_l1` |
| `app/integrations/ksef/mapper.py` | `_format_adres_l1` → shared |
| `app/services/contractor_service.py` | override `is not None` (+ EOL LF vs HEAD CRLF) |
| `frontend-react/src/api/contractors.js` | `updateOverride` |
| `frontend-react/src/components/invoice/partyAddress.js` | NEW |
| `frontend-react/src/components/invoice/partyAddress.test.js` | NEW |
| `frontend-react/src/components/invoice/InvoiceForm.jsx` | UI adres + zapis override |
| `frontend-react/src/components/invoice/InvoiceForm.module.css` | layout |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | buyer incomplete + open edit |
| `frontend-react/src/components/invoice/InvoiceCardList.jsx` | `onRequestEdit` |
| `tests/unit/test_ksef_partial_regon_address.py` | NEW regresje |
| `docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001.md` | raport implementacji |
| `docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0002-LOCAL-REVIEW.md` | ten raport |

### Wykluczone (nie do commit KSeF)

- `frontend-react/package.json` + raporty Cursor/npm (`*-CURSOR-*`)
- Guardian: `scripts/ifg_guardian/**`, `tests/unit/test_guardian_*`
- `docs/GUARDIAN2_RECOVERY_DS723.md`, `docs/_archiwum/migracja_mac_mini.md`
- `docs/gwo/`, starsze `docs/reports/2026-07*`, `2026-08*`, `2026-09-12*`
- `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` (WIP, FAIL poza zakresem)

---

## 3. Review A–D

### A. ADDRESS LOGIC — PASS

| Case | Wynik |
|---|---|
| street+building+postal+city | `Testowa 10, 00-001 Warszawa` |
| null street + building + locality | `Prusicko 10, 98-331 Prusicko` |
| brak dublowania | brak `Prusicko 10, Prusicko 10, …` |
| przecinki | brak leading/trailing/`,,` |
| `None`/`null` literały | **utwardzone w review** (`_strip` / `stripField`) |
| KodKraju | FA(3) testy → `PL` |

### B. OVERRIDE PRECEDENCE — PASS

- `InvoiceMapper.build_contractor_snapshot` + `_build_response`: override gdy `is not None`
- CASE 5: po niepełnym REGON (`street/building=null`) override `Moczydła`/`2` zostaje → AdresL1 PASS
- Override per `contractor_id` (API `PATCH /contractors/{id}/override`)
- `buyer_snapshot` na fakturze: `InvoiceService._resolve_buyer_snapshot` merge przy create/update

Uwaga: pola override ustawione na `null` (np. puste street z formularza) **nie** blokują późniejszego pełnego REGON na tym polu — chronione są tylko jawnie zapisane wartości override.

### C. VALIDATION — PASS

- Sale: `can_build_adres_l1` (place-line + postal **i** city)
- Street nieobowiązkowe
- CASE 3 (tylko postal+city) → BLOCK
- **Sprzedawca backend** (`SettingsService.validate_company_snapshot`): **bez zmian**
- **Sprzedawca UI** (`isSellerSnapshotComplete`): w review **przywrócone** do starej logiki (nie `canBuildAdresL1`)

### D. UI — PASS (code review + flow)

- „Uzupełnij dane nabywcy” → `onRequestEdit` → `onOpenInvoice(inv, 'edit')`
- Prefill z REGON / `buyerInfo` → pola adresu
- Zapis: `updateOverride` → potem `invoicesApi.update` → `refreshAllInvoicePools` + `refreshKey` → lista z nowym snapshotem; przycisk KSeF bez ręcznego reloadu okna
- Błędy: `setError(...)` z API; override failure przerywa zapis (nie silent)

---

## 4–6. Testy

### Nowe

```text
pytest tests/unit/test_ksef_partial_regon_address.py  → 16 passed
node --test …/partyAddress.test.js                   → 5 passed
```

### Szersza regresja (backend)

```text
test_domain_invoice + test_ksef_mapper + test_transmission_service
+ test_invoice_service + test_fa3_seller_city_parse + test_ksef_xml_parser
→ 209 passed, 1 failed

FAIL (poza zakresem GWO):
  test_sale_requires_number_local_before_send
  — regex 'number_local' vs komunikat PL (istniejący mismatch, nie z AdresL1)

test_contractor_service.py → 6 passed
```

### Frontend (invoice-related, bez WIP numbering)

```text
partyAddress + invoiceOpenMode + buyerPopup + catalogItemLine
→ 21 passed

invoiceCardListNumbering.test.js → FAIL (unrelated WIP, excluded)
```

---

## 7. Manual cases

| Case | Result |
|---|---|
| 1 Testowa/10/00-001/Warszawa | PASS `Testowa 10, 00-001 Warszawa` |
| 2 null/10/98-331/Prusicko | PASS `Prusicko 10, 98-331 Prusicko` |
| 3 null/null/98-331/Prusicko | BLOCK |
| 4 Moczydła/2/… | PASS |
| 5 po 4 niepełny REGON | override remains PASS |

---

## 8. Naprawy w trakcie review

1. `isSellerSnapshotComplete` — rollback do poprzedniej reguły (seller UI unchanged).
2. Filtrowanie literałów `None`/`null`/`undefined` w AdresL1 (PY + JS + testy).
3. Normalizacja CRLF→LF w plikach KSeF, które miały CRLF w HEAD (`contractor_service`, `mapper`, `contractors.js`, `InvoiceActions`) — logiczny diff mały; surowy `git diff` na `contractor_service` nadal wygląda na duży przez EOL.

---

## STATUS

`LOCAL_REVIEW_PASS`

## VERDICT

`READY_FOR_KSEF_ONLY_COMMIT`

## DIFF_SCOPE_OK

`YES` (po wykluczeniu unrelated; uwaga na EOL w `contractor_service.py`)

## BACKEND_TESTS

`209 passed / 1 pre-existing fail (number_local regex)` + `contractor 6/6` + `partial_regon 16/16`

## FRONTEND_TESTS

`partyAddress 5/5` + related invoice suite `21/21` (numbering WIP excluded)

## REGRESSION_TESTS

`PASS` w zakresie KSeF/invoice/contractor; 1 fail domain number_local = unrelated

## MANUAL_CASES

`1–5 PASS` (jak tabela)

## OVERRIDE_PRECEDENCE

`PASS`

## BUYER_SNAPSHOT

`PASS` (resolve przy zapisie faktury z merge override)

## SELLER_LOGIC_UNCHANGED

`YES` (backend settings; UI seller snapshot przywrócony)

## FILES_FOR_COMMIT

```text
app/domain/party_address.py
app/domain/models/invoice.py
app/integrations/ksef/mapper.py
app/services/contractor_service.py
frontend-react/src/api/contractors.js
frontend-react/src/components/invoice/partyAddress.js
frontend-react/src/components/invoice/partyAddress.test.js
frontend-react/src/components/invoice/InvoiceForm.jsx
frontend-react/src/components/invoice/InvoiceForm.module.css
frontend-react/src/components/invoice/InvoiceActions.jsx
frontend-react/src/components/invoice/InvoiceCardList.jsx
tests/unit/test_ksef_partial_regon_address.py
docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001.md
docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0002-LOCAL-REVIEW.md
```

## FILES_EXCLUDED

Wszystkie pozostałe `M`/`??` z `git status` (Cursor/npm, Guardian, numbering WIP, stare docs/gwo).

## RISKS

| Risk | Poziom |
|---|---|
| Commit `contractor_service.py` pokaże duży diff EOL (CRLF→LF) | LOW — treść logiczna = 1 warunek |
| Brak ręcznego kliknięcia w działającym UI w tej sesji (review code+test) | MED — zalecany 1 smoke lokalny przed deploy |
| Puste pole override = null → nie „zamraża” pustki wobec pełnego REGON | LOW — zgodne z modelem pól |

## READY_FOR_COMMIT

`YES`

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED
