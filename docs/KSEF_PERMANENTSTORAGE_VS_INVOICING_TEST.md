# KSeF — test ręczny PermanentStorage vs Invoicing

**Cel:** Zweryfikować hipotezę, że IFG widzi tylko 50 ref (max ~05.06), bo sync używa wyłącznie `dateType=PermanentStorage` i **nie odpytuje** `Invoicing`.

**Źródło parametrów:** `app/integrations/ksef/client.py` — `_query_purchase_metadata_refs`, `_format_metadata_datetime`, `_extract_metadata_invoice_refs`

---

## Parametry identyczne z IFG

| Parametr | Wartość |
|----------|---------|
| URL | `https://api.ksef.mf.gov.pl/v2/invoices/query/metadata` |
| Method | `POST` |
| Query | `pageOffset=0`, `pageSize=50` |
| Header | `Authorization: Bearer {access_token}`, `Accept: application/json` |
| `subjectType` | `Subject2` |
| `dateRange.from` | `2026-03-23T00:00:00Z` |
| `dateRange.to` | `2026-06-21T23:59:59Z` |
| `dateRange.dateType` | **`PermanentStorage`** lub **`Invoicing`** (jedyna różnica między testami) |

Body (jak w `client.py:674–680`):

```json
{
  "subjectType": "Subject2",
  "dateRange": {
    "dateType": "PermanentStorage",
    "from": "2026-03-23T00:00:00Z",
    "to": "2026-06-21T23:59:59Z"
  }
}
```

(dla testu 2 zamień `"dateType": "Invoicing"`)

IFG czyta ref z pól odpowiedzi: `invoices` / `invoiceList` / `items` / `results` → `ksefNumber` lub `ksefReferenceNumber` (`_extract_metadata_invoice_refs`).

---

## Jedna komenda diagnostyczna (DS723+)

Uruchom w katalogu produkcyjnym (`/volume1/docker/ifg_v2/ifg_standalone`):

```bash
cd /volume1/docker/ifg_v2/ifg_standalone && \
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH" && \
TOKEN=$(sudo docker compose -f docker/docker-compose.prod.yml exec -T db \
  psql -U postgres -d ksef_backend -tA -c "
    SELECT token_metadata_json->>'access_token'
    FROM ksef_sessions
    WHERE nip='9670402857' AND status='active'
    ORDER BY updated_at DESC LIMIT 1;
  ") && \
for DATE_TYPE in PermanentStorage Invoicing; do
  echo "========== dateType=$DATE_TYPE pageOffset=0 =========="
  RESP=$(curl -sS -X POST \
    "https://api.ksef.mf.gov.pl/v2/invoices/query/metadata?pageOffset=0&pageSize=50" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"subjectType\":\"Subject2\",\"dateRange\":{\"dateType\":\"$DATE_TYPE\",\"from\":\"2026-03-23T00:00:00Z\",\"to\":\"2026-06-21T23:59:59Z\"}}")
  echo "$RESP" | python3 -c "
import json,sys
d=json.load(sys.stdin)
refs=[]
for k in ('invoices','invoiceList','items','results'):
    if isinstance(d.get(k),list):
        for i in d[k]:
            r=i.get('ksefNumber') or i.get('ksefReferenceNumber')
            if r: refs.append(r)
        break
print('hasMore=', d.get('hasMore'))
print('refs_count=', len(refs))
targets=[r for r in refs if r.startswith('8762469751-20260612') or r.startswith('9512120077-20260612')]
print('target_hits=', targets)
june12=[r for r in refs if '-20260612-' in r]
print('any_20260612=', june12[:10], '... total', len(june12))
print('max_ref_date_token=', max((r.split('-')[1][:8] for r in refs), default='none'))
"
  sleep 2
done
```

**Uwaga:** token musi być ważny (aktywna sesja KSeF). Przy 401 odśwież sesję w UI i powtórz.

---

## Co porównać

| Pole | PermanentStorage | Invoicing |
|------|------------------|-----------|
| `refs_count` | IFG prod: **50** | ? |
| `hasMore` | ? | ? |
| `target_hits` | ref GENERON / P4 | ref GENERON / P4 |
| `any_20260612` | lista ref z 12.06 | lista ref z 12.06 |
| `max_ref_date_token` | prod: **20260605** | oczekiwane **≥ 20260612** jeśli hipoteza słuszna |

### Ref do weryfikacji (portal)

- `8762469751-20260612...` (GENERON, 12.06.2026)
- `9512120077-20260612...` (P4, 12.06.2026)

**Oczekiwane przy potwierdzeniu hipotezy:**

- **PermanentStorage:** brak obu ref (lub brak jakiegokolwiek `-20260612-`); `refs_count=50`, `max` ~ `20260605` — jak obecny sync IFG.
- **Invoicing:** **obecność** co najmniej jednego z ref `8762469751-20260612*` / `9512120077-20260612*`; ewentualnie więcej pozycji z czerwca po 05.06.

**Odrzucenie hipotezy:** oba `dateType` bez ref z 12.06 → przyczyna leży gdzie indziej (paginacja, Subject, opóźnienie indeksu KSeF).

---

## Paginacja (opcjonalnie strona 2)

IFG przy pustej stronie 1 kończy pętlę. Jeśli `hasMore=true` na stronie 0, powtórz curl z `pageOffset=50` dla obu `dateType`.

---

## Logi IFG do skorelowania

```bash
sudo docker compose -f docker/docker-compose.prod.yml logs worker 2>&1 | \
  grep 'KSeF metadata query subjectType'
```

Prod (job `4d6ad6ef`): tylko `dateType=PermanentStorage refs=50`, **brak** linii `Invoicing` — zgodne z `client.py:710–713` (`break` po pierwszym niepustym dateType).

---

## Interpretacja

| Wynik testu | Wniosek |
|-------------|---------|
| Invoicing ma ref 12.06, PermanentStorage nie | Hipoteza **potwierdzona** — IFG powinien odpytywać oba dateType lub preferować Invoicing |
| Oba bez 12.06 | Hipoteza **niepotwierdzona** — sprawdzić paginację / opóźnienie KSeF |
| Oba z 12.06 | IFG powinien był je zobaczyć — szukać buga paginacji lub filtrowania po stronie klienta |
