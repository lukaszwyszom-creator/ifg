# Ślad danych: rachunek bankowy `61114010140000310278885108` vs `48109018960000000106474926`

Data analizy: 2026-06-26  
Środowisko produkcyjne: DS723+ (`ksef_backend`, NIP `9670402857`)  
**Bez zmian w kodzie** — wyłącznie audyt przepływu danych.

---

## Werdykt

| Wartość | Skąd pochodzi |
|---------|----------------|
| **`61114010140000310278885108`** | **Nie pochodzi z bazy IFG.** Wstrzyknięta ręcznie w lokalnym skrypcie weryfikacyjnym (`BANK_RAW = "61 1140 1014 0000 3102 7888 5108"`) użytym przy `docs/KSEF_BANK_ACCOUNT_XML_VERIFY_2026_06.md`. W repozytorium, produkcji i testach **nie występuje**. |
| **`48109018960000000106474926`** | **Produkcyjne źródło prawdy:** `app_settings.seller_bank_account` (wiersz `id=1`, zaktualizowany 2026-06-16). To numer oczekiwany w PDF i — po deployu poprawki KSeF — w XML. |

---

## 1. Produkcja — rekord w bazie

```sql
SELECT id, seller_nip, seller_bank_account, updated_at
FROM app_settings WHERE id = 1;
```

| id | seller_nip | seller_bank_account | updated_at |
|----|------------|---------------------|------------|
| 1 | 9670402857 | **48109018960000000106474926** | 2026-06-16 19:43:14+02 |

- **Tabela:** `app_settings` (singleton, `id = 1`)
- **Pole:** `seller_bank_account` (`VARCHAR(26)`, 26 cyfr)
- **Model ORM:** `AppSettingsORM.seller_bank_account` (`app/persistence/models/app_settings.py`)
- **Zapis:** `SettingsService.update_settings()` → `AppSettingsRepository.upsert()` (frontend: Ustawienia firmy)

**Uwaga:** W `_merge()` rachunek bankowy **nie ma fallbacku z env** (w przeciwieństwie do NIP/nazwy/adresu). Źródło wyłącznie DB:

```154:158:app/services/settings_service.py
            "seller_bank_account": (
                str(row.seller_bank_account).strip()
                if row and row.seller_bank_account
                else None
            ),
```

W `.env.example` **brak** `SELLER_BANK_ACCOUNT`.

---

## 2. SettingsService → merged settings

```
app_settings.seller_bank_account = '48109018960000000106474926'
        ↓
AppSettingsRepository.get()  →  AppSettingsORM row
        ↓
SettingsService._merge(row)
        ↓
get_settings()["seller_bank_account"] = '48109018960000000106474926'
```

---

## 3. build_company_snapshot()

```87:90:app/services/settings_service.py
        bank_account = str(merged.get("seller_bank_account") or "").strip()
        if bank_account:
            snapshot["bank_account"] = bank_account
        return snapshot
```

**Wynik dla produkcji (po poprawce w kodzie, jeszcze przed deployem na DS723+):**

```json
{
  "nip": "9670402857",
  "name": "Ikona Małgorzata Katarzyna Krzyżanowska-Witkowska",
  "street": "Juliusza Kossaka",
  "building_no": "72",
  "apartment_no": "",
  "postal_code": "85-307",
  "city": "Bydgoszcz",
  "country": "PL",
  "bank_account": "48109018960000000106474926"
}
```

---

## 4. seller_snapshot faktury

### 4a. PDF / podgląd HTML (działa dziś)

```
get_settings()["seller_bank_account"]
        ↓
invoices router: resolve_seller_bank_account_for_render(..., company_bank_account=...)
        ↓
render_invoice_html / render_invoice_pdf(seller_bank_account='48109018960000000106474926')
```

PDF **nie czyta** `seller_snapshot_json.bank_account` dla faktur sprzedaży — bierze **bezpośrednio ustawienia firmy**. Stąd kontrahent widzi poprawny numer na PDF IFG.

### 4b. Wysyłka KSeF (TransmissionService)

```
TransmissionService._prepare_sale_invoice_for_submit()
        ↓
_refresh_sale_seller_snapshot()
        ↓
build_company_snapshot() → invoice.seller_snapshot
        ↓
InvoiceRepository.update() → invoices.seller_snapshot_json
        ↓
KSeFMapper.invoice_to_xml(invoice)
```

### 4c. Stan produkcyjny **przed deployem poprawki** (2026-06-26)

Przykład `FV/19/06/2026` — `seller_snapshot_json` **bez** `bank_account`:

```json
{
  "nip": "9670402857",
  "city": "Bydgoszcz",
  "name": "Ikona Małgorzata Katarzyna Krzyżanowska-Witkowska",
  "street": "Juliusza Kossaka",
  "country": "PL",
  "building_no": "72",
  "postal_code": "85-307",
  "apartment_no": ""
}
```

| Zapytanie | Wynik (10 ostatnich FV sprzedaży) |
|-----------|-----------------------------------|
| `seller_snapshot_json->>'bank_account'` | **puste / NULL** |
| `transmissions.xml_content` zawiera `<NrRB>` | **NIE** (8 ostatnich transmisji) |
| `transmissions.xml_content` zawiera `481090…` | **NIE** |
| `transmissions.xml_content` zawiera `611140…` | **NIE** |

Faktury wysłane do KSeF **przed deployem** nie miały rachunku w XML z dwóch powodów:
1. `build_company_snapshot()` wcześniej **nie kopiował** `seller_bank_account` do snapshotu.
2. `FA3Mapper._build_platnosc()` **nie emitował** `RachunekBankowy/NrRB`.

---

## 5. FA3Mapper → XML

```125:131:app/integrations/ksef/mapper.py
def _seller_bank_account_from_snapshot(snapshot: dict) -> str | None:
    for key in ("bank_account", "bankAccount", "nr_rb", "NrRB"):
        raw = snapshot.get(key)
        if isinstance(raw, str) and raw.strip():
            normalized = normalize_bank_account(raw.strip())
            return normalized or raw.strip()
    return None
```

```265:268:app/integrations/ksef/mapper.py
        bank_account = _seller_bank_account_from_snapshot(invoice.seller_snapshot or {})
        if bank_account:
            rachunek = _el(platnosc, "RachunekBankowy")
            _el(rachunek, "NrRB", bank_account)
```

**Po deployu poprawki**, symulacja lokalna ze snapshotem produkcyjnym + `bank_account: 48109018960000000106474926`:

```xml
<Platnosc>
    ...
    <RachunekBankowy>
        <NrRB>48109018960000000106474926</NrRB>
    </RachunekBankowy>
</Platnosc>
```

Walidacja XSD FA(3): **PASS**.

---

## 6. Pełny diagram przepływu (oczekiwany, produkcja)

```
┌─────────────────────────────────────────────────────────────────┐
│  app_settings (id=1)                                            │
│  seller_bank_account = 48109018960000000106474926               │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
         ▼                                       ▼
 SettingsService.get_settings()          (PDF/HTML — osobna ścieżka)
         │                               invoices router → pdf_service
         ▼                               seller_bank_account z settings
 build_company_snapshot()
 snapshot["bank_account"] = 481090…
         │
         ▼ (przy wysyłce KSeF)
 TransmissionService._refresh_sale_seller_snapshot()
         │
         ▼
 invoices.seller_snapshot_json.bank_account = 481090…
         │
         ▼
 FA3Mapper._seller_bank_account_from_snapshot()
 normalize_bank_account() → 26 cyfr
         │
         ▼
 Fa/Platnosc/RachunekBankowy/NrRB = 48109018960000000106474926
```

---

## 7. Skąd wzięła się wartość `61114010140000310278885108`

| Krok | Fakt |
|------|------|
| 1 | Lokalna weryfikacja przed deployem uruchomiła skrypt Python **bez połączenia z DB** (`DATABASE_URL` → host `db` niedostępny poza Dockerem). |
| 2 | Skrypt **nie odczytał** `app_settings`; zamiast tego ustawił: `BANK_RAW = "61 1140 1014 0000 3102 7888 5108"`. |
| 3 | `normalize_bank_account()` → `61114010140000310278885108`. |
| 4 | Wartość trafiła wyłącznie do `docs/KSEF_BANK_ACCOUNT_XML_VERIFY_2026_06.md` i odpowiedzi w czacie. |
| 5 | Grep całego repo + produkcja: **zero trafień** na `61114010140000310278885108` poza tym raportem weryfikacyjnym. |

**Interpretacja numerów:**

| Numer | Prefiks banku (cyfry 3–6) | Znaczenie |
|-------|---------------------------|-----------|
| `61114010140000310278885108` | `1140` (mBank) | Przykładowy numer testowy ze skryptu — **nie należy do instalacji IFG** |
| `48109018960000000106474926` | `1090` (Santander Bank Polska) | **Rzeczywisty rachunek** zapisany w Ustawieniach firmy (prod) |

---

## 8. Dlaczego PDF pokazuje `481090…`, a KSeF (dotychczas) nie

| Warstwa | Skąd bierze rachunek | Prod dziś |
|---------|---------------------|-----------|
| PDF/HTML | `SettingsService.get_settings().seller_bank_account` | **481090…** ✓ |
| KSeF XML (przed deployem) | `invoice.seller_snapshot` → mapper | snapshot **bez** `bank_account` → **brak NrRB** ✗ |
| KSeF XML (po deployem poprawki) | refresh snapshot + mapper | **481090…** (oczekiwane) |

---

## 9. Wnioski

1. **`61114010140000310278885108` nie jest danymi produkcyjnymi IFG** — to artefakt lokalnej weryfikacji z hardcodowanym przykładem.
2. **`48109018960000000106474926` jest jedynym rachunkiem w prod DB** (`app_settings.seller_bank_account`).
3. Poprawka mapowania KSeF (już w kodzie lokalnym) po deployu na DS723+ powinna emitować **właśnie ten numer**, o ile snapshot zostanie odświeżony przy wysyłce.
4. Faktury już zaakceptowane w KSeF **nie zawierają** `NrRB` w zapisanym `transmissions.xml_content` — wymagają nowej wysyłki (nowe FV) po deployu, aby kontrahent zobaczył rachunek w XML z KSeF.
