# KSeF — PoC `POST /invoices/query/metadata`

Data: 2026-06-10  
Skrypt: `scripts/ksef_metadata_probe.py`

---

## 1. Cel skryptu

Diagnostyczny PoC dla **produkcyjnego API KSeF v2**, który sprawdza, czy faktury zakupowe można pobrać przez oficjalny endpoint **`POST /invoices/query/metadata`** — zamiast obecnej ścieżki IFG (`GET /sessions/{session}/invoices*`).

Skrypt **nie modyfikuje** sync zakupów ani kodu produkcyjnego IFG. Służy wyłącznie do ustalenia, która kombinacja `subjectType` + `dateType` zwraca faktury widoczne w portalu MF.

**Kontekst dotychczasowego wyniku IFG:**

- Sesja KSeF aktywna, sync zakupów kończy się sukcesem z `ksef_returned=0`.
- `GET /sessions/{session}/invoices` → HTTP 200, pusta lista.
- `POST /sessions/{session}/invoices/query` → 405, `POST /invoices/query` → 404.
- Wniosek: obecna integracja trafia w niewłaściwy surface API; metadata probe ma to zweryfikować.

---

## 2. Co testuje

### Endpoint

`POST {base_url}/invoices/query/metadata`  
Prod: `https://api.ksef.mf.gov.pl/v2/invoices/query/metadata`  
Query params: `pageOffset`, `pageSize` (domyślnie 0 / 50).

Body (przykład):

```json
{
  "subjectType": "Subject2",
  "dateRange": {
    "dateType": "PermanentStorage",
    "from": "2026-03-01T00:00:00Z",
    "to": "2026-06-09T23:59:59Z"
  }
}
```

### subjectType (`--subject`)

| Wartość | Rola |
|---------|------|
| `Subject1` | podmiot wystawiający (sprzedaż) |
| `Subject2` | podmiot przyjmujący (**FV zakupowe**) |
| `Subject3` | podmiot trzeci |
| `all` | wszystkie trzy (3 requesty) |

### dateType (`--date-type`)

| Wartość | Opis |
|---------|------|
| `Issue` | data wystawienia faktury |
| `Invoicing` | data fakturowania |
| `PermanentStorage` | data trwałego zapisu w KSeF (rekomendowana do sync przyrostowego) |
| `all` | wszystkie trzy (3 requesty) |

Macierz `--subject all --date-type all` = **9 kombinacji** (3 × 3).

### Output każdego requestu

- liczba faktur (`totalCount` / długość listy),
- pierwsze 5 numerów KSeF (`ksefNumber`, `ksefReferenceNumber`),
- pełna odpowiedź JSON zapisana do pliku.

---

## 3. Sposób uruchomienia

W katalogu repo, z `.env` (min. `KSEF_AUTH_TOKEN`, `SELLER_NIP`; przy `--auth session` także `DATABASE_URL`):

```bash
# Pojedynczy test — nabywca + PermanentStorage
python scripts/ksef_metadata_probe.py \
  --env production \
  --subject Subject2 \
  --date-type PermanentStorage \
  --date-from 2026-03-01 \
  --date-to 2026-06-09

# Pełna macierz diagnostyczna (9 requestów prod)
python scripts/ksef_metadata_probe.py \
  --env production \
  --subject all \
  --date-type all \
  --date-from 2026-03-01 \
  --date-to 2026-06-09

# Token z aktywnej sesji IFG w DB (bez ponownego auth)
python scripts/ksef_metadata_probe.py \
  --auth session \
  --nip 9670402857 \
  --subject Subject2 \
  --date-type Issue \
  --date-from 2026-03-01 \
  --date-to 2026-06-09
```

Opcjonalnie: `--auth token --access-token "..."`, `--page-size 100`, `--output-dir /ścieżka`.

---

## 4. Gdzie zapisuje JSON

Katalog domyślny:

```
logs/ksef_metadata_probe/
```

Pliki:

```
ksef_metadata_{SubjectType}_{DateType}_{timestamp}.json
```

Przykład: `ksef_metadata_Subject2_PermanentStorage_20260610T120000Z.json`

---

## 5. Tryb auth

| Tryb | Opis |
|------|------|
| **`--auth fresh`** (domyślnie) | Standardowy flow **`KSeFAuthProvider.get_tokens()`** — ten sam mechanizm uwierzytelniania co IFG (`/auth/challenge` → `/auth/ksef-token` → `/auth/token/redeem`). Wymaga `KSEF_AUTH_TOKEN` w `.env`. |
| **`--auth session`** | `access_token` z aktywnej sesji `ksef_sessions` w lokalnej bazie IFG. |
| **`--auth token`** | Jawny Bearer token (`--access-token`). |

Skrypt **nie otwiera** sesji online (`/sessions/online`) — do metadata wystarczy access token.

### Diagnostyka auth (przed zapytaniami metadata)

Przed macierzą metadata skrypt wypisuje bezpieczny fingerprint tokena (bez wartości sekretu):

- `source` — `fresh` / `session` / `token`
- `token_field` — skąd pochodzi token (np. `token_metadata_json.access_token`)
- `length` — długość tokena
- `sha256_prefix` — pierwsze 12 znaków SHA256 tokena

Przy **`--auth session`** dodatkowo:

- `session_id` — UUID rekordu w `ksef_sessions`
- `session_reference` — referencja sesji online KSeF
- lista kluczy token-like w `token_metadata_json` (np. `access_token`, `refresh_token`) — **bez wartości**

Następnie (tylko `--auth session`) wykonuje test sesyjny:

`GET /sessions/{session_reference}/invoices` z tym samym Bearer tokenem i parametrami:

```
invoiceType=received
subjectType=subject2
invoicingDateFrom=<date_from>
invoicingDateTo=<date_to>
```

Wynik:

```
[auth-check] status=<kod HTTP>
[auth-check] body_snippet=<pierwsze 300 znaków odpowiedzi>
```

Token pobierany jest z **`token_metadata_json.access_token`** — to samo pole co w sync IFG.

---

## 6. Ocena ryzyka

| Aspekt | Ocena |
|--------|-------|
| Ogólne ryzyko | **Niskie** |
| Typ operacji | Tylko **odczyt metadanych** — brak zapisu faktur do IFG |
| Wpływ na sync zakupów | **Brak** — skrypt standalone, nie wywołuje `query_received_invoices` |
| Macierz `all × all` | **9 requestów** do prod KSeF — uruchamiaj świadomie |
| Logowanie tokenów | Skrypt nie wypisuje tokenów; pliki JSON to odpowiedzi MF |
| `--auth fresh` | Nowe uwierzytelnienie MF (standardowy flow) |

---

## 7. Co będzie sukcesem

Sukces = **co najmniej jedna kombinacja** zwraca `total > 0` i lista zawiera numery KSeF zgodne z fakturami widocznymi w portalu MF w zadanym okresie.

Najbardziej oczekiwany wariant dla FV zakupowych:

- `Subject2` + `PermanentStorage` lub `Subject2` + `Issue`

Jeśli sukces — kolejny krok to implementacja sync zakupów przez `/invoices/query/metadata` (+ pobranie XML przez `/invoices/{ksefNumber}`), a nie sesyjne GET.

---

## 8. Co będzie oznaczał brak wyników

Jeśli **wszystkie 9 kombinacji** zwróci `total=0` (HTTP 200, pusta lista), mimo że faktury są w portalu KSeF:

- prawdopodobny problem **uprawnień tokena** (zakres, rola, kontekst NIP),
- **NIP** w tokenie niezgodny z kontekstem wyszukiwania (`subjectType` vs rola podmiotu),
- faktury **niewidoczne** dla tego podmiotu w prod API (inny NIP nabywcy, self-billing, B2B edge case),
- zły zakres dat (faktury poza oknem mimo obecności w UI),
- ewentualnie błędna wielkość liter enum (`Subject2` vs `subject2`) — wtedy HTTP 400 w logu skryptu.

Brak wyników **nie potwierdza** poprawności obecnego sync IFG — wręcz wskazuje, że trzeba dalej diagnozować auth/uprawnienia, a nie sesyjne GET.

---

## 9. Interpretacja wyników auth-check vs metadata

| `[auth-check]` session GET | `[query]` metadata | Interpretacja |
|----------------------------|-------------------|---------------|
| **200** | **401** | Token **działa dla sesji online**, ale **nie dla metadata** — inny wymóg auth/scope; spróbuj `--auth fresh` |
| **401** | **401** | Token **nieważny / wygasły / niewłaściwy** — problem auth ogólnie |
| **200** | **200** | **Auth OK** — badamy wyniki metadata (`total`, numery KSeF) |

---

## Powiązane dokumenty

- `docs/KSEF_PURCHASE_API_INVESTIGATION.md`
- `docs/KSEF_EMPTY_SYNC_HANDLING.md`
