# KSeF — brakujące faktury zakupowe: root cause (subjectType / payload)

Data: 2026-06-23  
Zakres analizy: **subjectType**, **payload metadata**, endpointy — **bez** analizy dateType.

## Stan obserwacji (prod)

- `POST /invoices/query/metadata`, `Subject2`, zakres dat w `dateRange`
- Zawsze **50 ref**, najnowszy token daty **20260605**
- `hasMore=true` na stronie 0, `pageOffset=50` → **0 ref**
- `isTruncated=false`
- IFG wysyła minimalny payload zgodny z OpenAPI

---

## 1. Obsługiwane subjectType (KSeF v2 OpenAPI)

| Wartość | Rola MF | Zastosowanie |
|---------|---------|--------------|
| **Subject1** | Podmiot 1 — **sprzedawca** | FV **sprzedażowe** (wystawione przez zalogowany NIP) |
| **Subject2** | Podmiot 2 — **nabywca** | FV **zakupowe** (otrzymane przez zalogowany NIP) |
| **Subject3** | Podmiot 3 | Podmiot trzeci na fakturze (np. płatnik, pośrednik) |
| **SubjectAuthorized** | Podmiot **upoważniony** | Dostęp na podstawie uprawnień/delegacji, nie jako nabywca/sprzedawca |

Źródło: `InvoiceQuerySubjectType` w OpenAPI prod (`/docs/v2/openapi.json`).

IFG (`client.py`, `ksef_metadata_probe.py`) używa wyłącznie **`Subject2`** dla sync zakupów.

---

## 2. Czy Subject2 jest jedynym poprawnym wariantem dla zakupów?

**Dla standardowych FV zakupowych — tak.**

- Token auth IFG: `contextIdentifier.type=Nip`, `value=<NIP firmy>` (`KSeFAuthProvider`).
- Zakupy = firma jest **nabywcą** (Podmiot2) → **`Subject2`** to właściwy filtr API.
- **`Subject1`** zwróciłby FV **sprzedażowe** (błędny kierunek importu).
- **`Subject3`** — tylko jeśli brakujące FV są widoczne w portalu w roli podmiotu trzeciego, nie nabywcy.
- **`SubjectAuthorized`** — jeśli portal pokazuje FV na podstawie **uprawnienia** (biuro rachunkowe, pełnomocnik), a nie roli nabywcy w metadata.

**Wniosek:** Subject2 nie jest błędem konfiguracji. Zmiana na Subject1 byłaby regresją. Ewentualny zysk tylko z diagnostyki Subject3 / SubjectAuthorized.

---

## 3. Alternatywne endpointy metadata / query dla FV otrzymanych

| Endpoint | W OpenAPI | Filtry | Uwagi |
|----------|-----------|--------|-------|
| **`POST /invoices/query/metadata`** | ✅ | `InvoiceQueryFilters` | Używany przez IFG |
| **`POST /invoices/exports`** | ✅ | **ten sam** `InvoiceQueryFilters` + szyfrowanie | Rekomendowany przez MF do sync przyrostowego; paczka + `_metadata.json` |
| `GET /sessions/{ref}/invoices` | ✅ (inna semantyka) | flat params | Faktury **wysłane w sesji online**, nie pełna historia zakupów — prod: pusta lista |
| `GET /sessions/{ref}/invoices/received` | ❌ | — | IFG fallback; **brak w OpenAPI** |
| `POST /invoices/query` | ❌ | — | prod: 404 |
| `POST /sessions/{ref}/invoices/query` | ❌ | — | prod: 405 |

**Nie ma osobnego endpointu „received/metadata”.** Jedyna oficjalna lista metadanych to `POST /invoices/query/metadata` (lub eksport z identycznym payloadem filtrów).

---

## 4. Portal KSeF vs API metadata

Portal (UI) i API używają tego samego backendu KSeF, ale:

| Aspekt | Portal | IFG (API) |
|--------|--------|-----------|
| Rola podmiotu | Zakładki UI (zakup / sprzedaż / uprawnienia) | Jawny `subjectType` w body |
| Filtry | UI może agregować widoki, sortować po dacie wystawienia | Tylko `subjectType` + `dateRange` (+ opcjonalne filtry — IFG ich **nie wysyła**) |
| Paginacja | Nieskończony scroll / inna logika UI | `pageOffset` / `pageSize` / `hasMore` |
| Zakres dat | Użytkownik wybiera okno | IFG: `dateRange.from/to` ISO UTC |
| Limit | Nieujawniony w UI | OpenAPI: max **3 miesiące** na `dateRange`; max **10 000** ref / filtr |

Portal może pokazywać FV **nowsze niż 2026-06-05**, podczas gdy API Subject2 zwraca zamrożony zestaw 50 ref, bo:

- UI nie jest równoważne z jednym zapytaniem metadata (inna rola/uprawnienie w sesji przeglądarkowej), **albo**
- API zwraca pełny wynik Subject2 dla tokena, a „brakujące” FV **nie są przypisane do tego NIP jako Subject2** w indeksie KSeF (inny NIP nabywcy, JST, oddział, pełnomocnictwo).

Identyczny zbiór 50 ref niezależnie od wariantów `dateType` wskazuje, że **problem leży poza wyborem subjectType** — API zwraca ten sam pool metadanych dla kontekstu tokena + Subject2.

---

## 5. Payload IFG vs pełny InvoiceQueryFilters

### Co IFG wysyła dziś

```json
{
  "subjectType": "Subject2",
  "dateRange": {
    "dateType": "...",
    "from": "2026-03-25T00:00:00Z",
    "to": "2026-06-23T23:59:59Z"
  }
}
```

Query params: `pageOffset`, `pageSize=50` — **bez** jawnego `sortOrder` (OpenAPI default: `Asc`).

### Opcjonalne pola OpenAPI (IFG **nie używa**)

| Pole | Cel | Wpływ na „brakujące” zakupy |
|------|-----|----------------------------|
| `buyerIdentifier` | `{type: Nip, value: "9670402857"}` | **Nie rozszerza** wyniku — zawęża do nabywcy; przy Subject2 i tokenie NIP raczej redundantne |
| `sellerNip` | NIP sprzedawcy | **Zawęża**, nie poszerza |
| `ksefNumber`, `invoiceNumber` | Exact match | Pojedyncza FV |
| `amount`, `currencyCodes`, `formType`, `invoiceTypes`, … | Filtry dodatkowe | Tylko zawężenie |

**Brak dodatkowych filtrów podmiotu nie tłumaczy braku FV po 2026-06-05.** Payload jest minimalny, ale **poprawny** dla zakupów standardowych.

---

## Root cause (konkretna)

**Przyczyna nie leży w błędnym `subjectType` ani w niepełnym payloadzie filtrów podmiotu.**

IFG używa poprawnego oficjalnego endpointu i **`Subject2` (nabywca)** — jedynego właściwego typu dla importu zakupów. KSeF API dla kontekstu tokena `NIP=9670402857` zwraca **stabilny, zamknięty zbiór 50 metadanych** (ostatni token daty 20260605). Faktury widoczne w portalu po tej dacie **nie wchodzą w ten zbiór API Subject2** — albo są dostępne w innym **kontekście roli/uprawnień** (Subject3 / SubjectAuthorized / sesja portalowa), albo lista Subject2 jest **niekompletna po stronie paginacji API** (`hasMore=true`, strona 2 pusta — problem warstwy `pageOffset`/`sortOrder`, nie body `subjectType`).

**SubjectType nie jest root cause.** Root cause operacyjny: **integracja nie dociera do pełnej listy FV przypisanych do NIP w KSeF** mimo poprawnego Subject2 — przez defekt paginacji metadata **lub** przez to, że brakujące FV wymagają innego kanału (`/invoices/exports`) albo innej roli API niż Subject2.

---

## Propozycja poprawki (bez zmiany subjectType zakupów)

### A. Diagnostyka (1 sesja, bez zmian prod sync)

Probe macierzy **subjectType** (stały dateRange, ten sam NIP):

```bash
for ST in Subject1 Subject2 Subject3 SubjectAuthorized; do
  python scripts/ksef_metadata_probe.py \
    --env production --auth fresh --nip 9670402857 \
    --subject "$ST" --date-type PermanentStorage \
    --date-from 2026-06-01 --date-to 2026-06-23
done
```

Sprawdź, czy ref `8762469751-20260612*` / `9512120077-20260612*` pojawia się pod **Subject3** lub **SubjectAuthorized**, nie Subject2.

### B. Poprawka produkcyjna (rekomendowana)

1. **Zachować `Subject2`** dla sync zakupów — bez zmian.
2. **Przenieść listowanie ref na `POST /invoices/exports`** z tym samym payloadem:
   ```json
   { "subjectType": "Subject2", "dateRange": { ... } }
   ```
   MF rekomenduje ten kanał do pełnego sync; filtry identyczne jak metadata.
3. **Opcjonalnie** jawnie dodać w body:
   ```json
   "buyerIdentifier": { "type": "Nip", "value": "9670402857" }
   ```
   — walidacja kontekstu nabywcy (mały diff, bez zmiany semantyki jeśli Subject2 już działa).
4. **Nie przełączać zakupów na Subject1.**
5. Jeśli macierz A pokaże brakujące FV tylko pod **SubjectAuthorized** — osobna ścieżka sync z uprawnieniami/delegacją (wymaga analizy uprawnień tokena `InvoiceRead`).

### C. Czego nie robić

- Zmiana `Subject2` → `Subject1` (importowałby sprzedaż).
- Dodawanie `sellerNip` „żeby poszerzyć” (tylko zawęża).
- Powrót do sesyjnych GET `/sessions/.../invoices*` (nie lista zakupów historycznych).

---

## Pliki referencyjne IFG

| Plik | Rola |
|------|------|
| `app/integrations/ksef/client.py` | `_METADATA_SUBJECT_PURCHASE = "Subject2"`, body metadata |
| `scripts/ksef_metadata_probe.py` | Probe Subject1/2/3, ten sam body |
| `docs/KSEF_OFFICIAL_API_AUDIT_2026-06-10.md` | Audyt OpenAPI vs IFG |

---

## Podsumowanie jednym zdaniem

**Subject2 i minimalny payload metadata są poprawne; brakujące zakupy po 2026-06-05 nie wynikają ze złego subjectType, lecz z tego, że API nie zwraca ich w dostępnej liście 50 ref Subject2 — naprawa: diagnostyka Subject3/SubjectAuthorized + migracja listowania na `/invoices/exports` (ten sam Subject2 payload), ewentualnie jawny `buyerIdentifier`.**
