---
kind: gwo
project: IFG
workflow: GWO-IFG-0029
handoff: true
created_at: 2026-07-20T20:00:00Z
---

# GWO-IFG-0029 — Purchase seller_snapshot.city integrity fix

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS  
**STATUS:** SUCCESS  

---

## A. Root cause

FA(3) `TAdres` **nie ma** elementów `Miejscowosc` / `KodPocztowy` / `Ulica` — tylko wolny tekst `AdresL1` (+ opcjonalnie `AdresL2`).

Stary parser (`xml_parser._parse_address`) mapował:
- cały `AdresL1` → `street`,
- `AdresL2` → `apartment_no` (błędnie),
- `Miejscowosc` → `city` (element nie istnieje w FA3) → **zawsze puste**.

Stąd produkcja: street wypełniony, `seller_snapshot.city` puste (20/20 w GWO-IFG-0028; audyt: 84 faktury zakupowe).

---

## B. Pole źródłowe KSeF

| Schemat | Pole | Znaczenie |
|---------|------|-----------|
| FA(3) `TAdres` | `AdresL1` | Pierwsza linia adresu (tu jest miejscowość w praktyce) |
| FA(3) `TAdres` | `AdresL2` | Druga linia (często `XX-XXX Miasto` lub `Miasto, XX-XXX`) |
| FA(3) `TAdres` | `KodKraju` | Kraj |
| Legacy / nieściśle | `Miejscowosc`, `KodPocztowy`, `Ulica` | Obsługiwane z priorytetem, jeśli obecne |

Kanoniczne mapowanie IFG przy eksporcie (`mapper._format_adres_l1`) składa `AdresL1` jako `{street}, {postal} {city}` — import wykonuje odwrotność.

---

## C. Pełna ścieżka mapowania

```
KSeF XML Podmiot1/Adres (AdresL1/AdresL2)
  → xml_parser._parse_address
       → fa3_address.split_fa3_address_lines
       → seller_snapshot.{street, postal_code, city, ...}
  → purchase_seller_city_validation_error (integralność)
  → ksef_session_service._process_purchase_invoice_xml
  → Invoice.seller_snapshot → seller_snapshot_json
  → API InvoiceResponse.seller_snapshot.city
  → UI popup „Nazwa, Miejscowość”
```

---

## D. Zmienione pliki

- `app/integrations/ksef/fa3_address.py` (nowy)
- `app/integrations/ksef/xml_parser.py`
- `app/services/ksef_session_service.py`
- `app/services/purchase_seller_city_backfill.py` (nowy)
- `scripts/backfill_purchase_seller_city.py`
- `scripts/ifg_guardian/modules/ifg_purchase_seller_city_backfill.py`
- `scripts/ifg_guardian/cli.py` → `guardian ifg purchase backfill-seller-city`
- `tests/unit/test_fa3_seller_city_parse.py`
- `tests/unit/test_backfill_purchase_seller_city.py`

**Commity:** `b2e7e1b`, `90421c8`, `deaa5f1`, `39c8202`

---

## E. Testy

| Suite | Wynik |
|-------|-------|
| `test_fa3_seller_city_parse.py` + xml_parser + backfill unit | **PASS** (12–19 w przebiegach) |
| Fixture FA(3) tylko `AdresL1`/`AdresL2` | city zapisane |
| Legacy `Miejscowosc` | bez regresji |
| Integralność gdy źródło ma city, snapshot puste | error |
| Integralność gdy brak wyodrębnialnego city | brak blokady |
| Backfill extract + city-before-postal | PASS |

---

## F. Audyt produkcyjnych rekordów

| Metryka | Wartość |
|---------|---------|
| Purchase z pustym city (przed) | **84** |
| Klasa A (naprawialne ze street/apartment) | 81 (+3 po rozszerzeniu wzorca) |
| Klasa B (wymagało refetch — przed poprawką wzorca) | 3 (układ „Miasto, kod”) |
| Klasa C | 0 |

---

## G. Dry-run backfill

```
EMPTY_CITY_CANDIDATES=84
A_REPAIRABLE=81
B_NEEDS_KSEF_REFETCH=3
```

Workflow: `guardian ifg purchase backfill-seller-city`

---

## H. Apply backfill

| Przebieg | UPDATED | SECOND_PASS_A |
|----------|---------|---------------|
| 1 (kod+miasto) | **81** | 0 |
| 2 (miasto+kod) | **3** | 0 |
| **Razem** | **84** | — |

Artefakty JSON:
- `docs/reports/GWO-IFG-0029_seller_city_backfill_apply.json`
- `docs/reports/GWO-IFG-0029_seller_city_backfill_remaining.json`
- `docs/reports/GWO-IFG-0029_seller_city_backfill_final.json`

Idempotencja: po apply dry-run → `EMPTY_CITY_CANDIDATES=0`.

---

## I. Rekordy nierozwiązane

**0** po finalnym apply.

(Wcześniejsze 3 B zostały naprawione bez refetch KSeF po obsłudze wzorca `Miasto, XX-XXX`.)

---

## J. Deploy i health

| Krok | Wynik |
|------|-------|
| Push `origin/production` | PASS |
| Guardian deploy (frontend) | LIVE COMPLETE (image rebuild **SKIP** — wykrywanie backendu nie zadziałało przy dirty tree) |
| **Ręczny** `docker compose build api worker` + up na DS723 | PASS |
| Health | `status=ok`, `environment=production` |
| Moduł w obrazie | `fa3_address` → `CITY Warszawa` |

Uwaga operacyjna: release plan pominął rebuild obrazu mimo zmian w `app/` — wykonano kontrolowany rebuild SSH.

---

## K. Realny produkcyjny hover

Playwright Docker `--network host` na DS723:

```
BUYER_POPUP_PROD_VERIFY=PASS
SELLER_POPUP_HOVER_VERIFY=PASS
BUYER_CITY_DISPLAY=PASS
SELLER_CITY_DISPLAY=PASS
SELLER_CITY_DATA_ERROR=NO
BUYER_TITLE=…PARAFIA…, Strzałków
SELLER_TITLE=…TOMDEK…, Biadoliny Sufczyn
```

Brak pustego przecinka; brak fallbacku UI.

---

## L. RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [x] **PRODUCTION_VERIFIED**

Rozdział:
- **Nowe importy:** parser FA3 + walidacja integralności w sync zakupów — wdrożone w obrazie API.
- **Backfill historyczny:** 84/84 naprawione; 0 nierozwiązanych.
- **UI:** popup Sprzedawcy z miejscowością — PASS.

---

## M. Następny krok

1. Rozważyć poprawkę Guardian release-plan, aby dirty tree nie pomijał `docker build` przy zmianach `app/`.
2. Opcjonalnie: osobne GWO na normalizację `street`/`postal_code` (backfill zmieniał tylko `city`).

## Decyzje dla ChatGPT

1. Czy otworzyć GWO na twardy gate w Guardian Deploy (wymuszony rebuild API przy diff w `app/`), żeby uniknąć SKIP image przy dirty worktree?

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG-0029_PURCHASE_SELLER_SNAPSHOT_CITY_INTEGRITY_FIX.md`
- `docs/reports/GWO-IFG-0029_seller_city_backfill_apply.json`
- `docs/reports/GWO-IFG-0029_seller_city_backfill_remaining.json`
- `docs/reports/GWO-IFG-0029_seller_city_backfill_final.json`

## Wygenerowane artefakty

- Commits: `b2e7e1b`, `90421c8`, `deaa5f1`, `39c8202`
- CLI: `guardian ifg purchase backfill-seller-city [--apply]`
- DS723 API/worker images rebuilt (manual compose build)
