# KSeF purchase metadata — diagnoza limitu 50 (2026-06-23)

## Stan produkcji (DS723+)

| Metryka | Wartość |
|---------|---------|
| Zakres sync | `2026-03-25` .. `2026-06-23` |
| subjectType | Subject2 |
| ksef_returned | 50 |
| created | 0 |
| skipped_existing | 50 |
| max issue_date w DB | 2026-06-05 |
| pageOffset=0 | page_refs=50, hasMore=True, page_date_min=20260330, page_date_max=20260605 |
| pageOffset=50 | page_refs=0, hasMore=False |
| raw_refs / unique_refs | 100 / 50 (PermanentStorage + Invoicing, dedup) |

---

## 1. Jakie pole daty wysyłamy w body?

IFG **nie** używa pól top-level `dateFrom`/`dateTo`, `acquisitionTimestamp`, `invoicingDate`.

Wysyłany kształt (`client.py`, `scripts/ksef_metadata_probe.py` — identyczny):

```json
{
  "subjectType": "Subject2",
  "dateRange": {
    "dateType": "PermanentStorage",
    "from": "2026-03-25T00:00:00Z",
    "to": "2026-06-23T23:59:59Z"
  }
}
```

| Pole | Używane przez IFG? |
|------|------------------|
| `dateRange.from` / `dateRange.to` | ✅ ISO 8601 UTC |
| `dateRange.dateType` | ✅ `PermanentStorage`, potem `Invoicing` |
| `dateRange.dateType=Issue` | ❌ sync nie odpytuje; probe obsługuje |
| `acquisitionTimestamp` | ❌ |
| `invoicingDate` (płaskie) | ❌ (tylko w legacy GET sesyjnym, nie w metadata) |

Semantyka MF (`dateType`):
- **Issue** — data wystawienia (portal często filtruje po niej)
- **Invoicing** — data fakturowania / nabycia
- **PermanentStorage** — data trwałego zapisu (rekomendowany sync przyrostowy)

---

## 2. Paginacja pageOffset=50

IFG wysyła query params: `pageOffset`, `pageSize=50`.

**Nie wysyła:** `sortOrder` (OpenAPI MF: opcjonalny `Asc`/`Desc`; przykłady Java/C# używają `SortOrder.ASC`).

**Nie logował / nie obsługiwał:** `isTruncated`, `permanentStorageHwmDate` z odpowiedzi.

### Obserwacja prod

- Strona 0: 50 ref, `hasMore=True`, max token ref = **20260605**
- Strona 50: **0 ref**, `hasMore=False`

To **nie** wygląda na poprawną paginację offsetową: przy `hasMore=True` oczekiwano kolejnych rekordów. Możliwe wyjaśnienia:

| Hipoteza | Opis |
|----------|------|
| **H3** | Brak `sortOrder=Asc` → niestabilna paginacja offsetowa (hasMore true, strona 2 pusta) |
| **H2** | W zakresie jest dokładnie 50 FV; `hasMore=True` to błąd/semantyka KSeF, brak FV po 06.05 w metadata |
| **H4** | `isTruncated=true` — MF wymaga zawężenia `dateRange` od ostatniej daty (sync przyrostowy), nie samego pageOffset |
| **H1** | FV z 12.06 widoczne w portalu po **Issue**, nie po PermanentStorage/Invoicing w tym zakresie |

Dokumentacja MF (`przyrostowe-pobieranie-faktur.md`, OpenAPI): paginacja przez `pageOffset` jest oficjalna, ale przy `isTruncated` trzeba resetować offset i przesunąć `from` w `dateRange`.

---

## 3. Subject2 dla zakupów

**Subject2 = podmiot przyjmujący (nabywca)** — zgodnie z OpenAPI MF i `docs/KSEF_METADATA_PROBE.md`.

Sync hardcode: `_METADATA_SUBJECT_PURCHASE = "Subject2"`, `subject_type_used = "subject2"`.

Subject2 jest **właściwy** dla FV zakupowych. Problem raczej nie leży w subjectType.

---

## 4. Filtry w kodzie sync

Po zebraniu metadata **brak** dodatkowego filtra dat ani obcinania listy:

- `ksef_session_service._sync_received_invoices_incremental` iteruje wszystkie `refs`
- `skipped_existing=50` → wszystkie 50 ref już w DB (dedup po `ksef_reference_number`)
- `page_date_max=20260605` pochodzi z **tokenów ref KSeF**, nie z filtra IFG

IFG **nie** odrzuca nowszych ref — KSeF ich nie zwraca w metadata.

---

## 5. Sync vs probe

| Aspekt | `client.py` | `ksef_metadata_probe.py` |
|--------|-------------|---------------------------|
| URL | `POST /invoices/query/metadata` | identyczny |
| Body | `subjectType` + `dateRange` | identyczny |
| Params | `pageOffset`, `pageSize` | identyczny |
| dateType | PermanentStorage + Invoicing | domyślnie jeden; `--date-type all` = 3 typy |
| Issue | ❌ | ✅ |
| sortOrder | ❌ | ❌ |
| Auth | token sesji z DB | `--auth fresh/session/token` |

Probe i sync używają **tego samego body** dla danej kombinacji subject/dateType.

---

## 6. Zmiana kodu (diagnoza)

Dodano w `client.py` (bez zmiany logiki paginacji):

- log `KSeF metadata request body=... pageOffset=... pageSize=...` (bez tokenów)
- log `isTruncated`, `permanentStorageHwmDate` per strona

---

## Hipotezy (priorytet)

1. **H1 (wysoka):** FV GENERON/P4 z 12.06 są w portalu po **Issue**, IFG odpytuje tylko PermanentStorage+Invoicing — max PermanentStorage w wynikach = 06.05.
2. **H2 (wysoka):** W metadata Subject2 w zakresie jest tylko 50 FV; brak FV po 06.05 to stan KSeF, nie bug dedup IFG.
3. **H3 (średnia):** Brak `sortOrder=Asc` powoduje hasMore=true przy pustej stronie 2.
4. **H4 (średnia):** `isTruncated=true` — wymagany algorytm przyrostowy MF (shift dateRange), nie sam pageOffset.
5. **H5 (niska):** FV w portalu pod innym kontekstem (inny NIP, Subject1 jako sprzedawca, nie zakup).

---

## Komendy weryfikacyjne DS723+

### A. Macierz dateType — czy Issue zwraca 12.06?

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH"

for DT in Issue Invoicing PermanentStorage; do
  echo "=== dateType=$DT ==="
  sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
    python scripts/ksef_metadata_probe.py \
    --env production --auth fresh --nip 9670402857 \
    --subject Subject2 --date-type "$DT" \
    --date-from 2026-03-25 --date-to 2026-06-23 \
    --page-offset 0 --page-size 50
done
```

Sprawdź w JSON: `hasMore`, `isTruncated`, `permanentStorageHwmDate`, ref z `-20260612-`.

### B. Paginacja strona 2 + sortOrder (ręczny curl z fresh token)

```bash
# Po probe: sprawdź saved JSON w logs/ksef_metadata_probe/
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
  python3 -c "
import json,glob
f=sorted(glob.glob('/app/logs/ksef_metadata_probe/ksef_metadata_Subject2_PermanentStorage_*.json'))[-1]
d=json.load(open(f))
print('hasMore=',d.get('hasMore'))
print('isTruncated=',d.get('isTruncated'))
print('permanentStorageHwmDate=',d.get('permanentStorageHwmDate'))
print('keys=',sorted(d.keys()))
"
```

### C. pageOffset=50 vs pageOffset=0 z Issue

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
  python scripts/ksef_metadata_probe.py \
  --env production --auth fresh --nip 9670402857 \
  --subject Subject2 --date-type Issue \
  --date-from 2026-06-01 --date-to 2026-06-23 \
  --page-offset 0 --page-size 50
```

### D. Po deploy logów diagnostycznych — ponowny sync

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs worker --tail=100 | \
  grep -E "metadata request body|isTruncated|permanentStorageHwmDate|metadata page"
```

---

## Rekomendowana następna akcja

**Komenda A** — macierz `Issue` / `Invoicing` / `PermanentStorage` dla Subject2; porównanie ref z `-20260612-` w zapisanych JSON. Jeśli tylko `Issue` zwraca 12.06 → fix to dodanie `Issue` do `_METADATA_DATE_TYPES` lub zmiana strategii dateType, nie paginacja offset.
