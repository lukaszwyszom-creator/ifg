# KSeF metadata probe — komendy DS723+ (PermanentStorage vs Invoicing)

**Data:** 2026-06-21  
**Skrypt:** `scripts/ksef_metadata_probe.py` (istniejący — bez zmian kodu aplikacji)  
**Zakres:** 2026-03-23 → 2026-06-21, NIP `9670402857`, Subject2

---

## Dlaczego nie surowy curl

Ręczny `curl` z `token_metadata_json->access_token` zwraca **401** — token w DB mógł wygasnąć.  
Skrypt probe używa tej samej infrastruktury co IFG:

| `--auth` | Mechanizm |
|----------|-----------|
| **`fresh`** (zalecane) | `KSeFAuthProvider.get_tokens()` — ten sam provider co normalny flow KSeF w aplikacji |
| **`session`** | `token_metadata_json.access_token` z aktywnej sesji DB (identyczne pole co sync; **może być stale → 401**) |

Worker odświeża kontekst sesji przez serwis; probe **`--auth fresh`** omija stary token z DB.

---

## Komendy DS723+

Katalog produkcyjny: `/volume1/docker/ifg_v2/ifg_standalone`

### A. PermanentStorage (Subject2)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone && \
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH" && \
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
  python scripts/ksef_metadata_probe.py \
    --env production \
    --auth fresh \
    --nip 9670402857 \
    --subject Subject2 \
    --date-type PermanentStorage \
    --date-from 2026-03-23 \
    --date-to 2026-06-21 \
    --page-offset 0 \
    --page-size 50 && \
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
  python3 -c "
import json, glob, os
os.chdir('/app')
files=sorted(glob.glob('logs/ksef_metadata_probe/ksef_metadata_Subject2_PermanentStorage_*.json'))
d=json.load(open(files[-1]))
refs=[]
for k in ('invoices','invoiceList','items','results'):
    if isinstance(d.get(k),list):
        for i in d[k]:
            r=i.get('ksefNumber') or i.get('ksefReferenceNumber')
            if r: refs.append(r)
        break
dates=[r.split('-')[1][:8] for r in refs if '-' in r]
print('=== PARSE PermanentStorage ===')
print('refs_count=', len(refs))
print('hasMore=', d.get('hasMore'))
print('max_date_token=', max(dates) if dates else 'none')
j12=[r for r in refs if '-20260612-' in r]
print('june12_refs=', j12)
print('target_hits=', [r for r in refs if r.startswith('8762469751-20260612') or r.startswith('9512120077-20260612')])
print('json_file=', files[-1])
"
```

### B. Invoicing (Subject2)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone && \
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH" && \
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
  python scripts/ksef_metadata_probe.py \
    --env production \
    --auth fresh \
    --nip 9670402857 \
    --subject Subject2 \
    --date-type Invoicing \
    --date-from 2026-03-23 \
    --date-to 2026-06-21 \
    --page-offset 0 \
    --page-size 50 && \
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api \
  python3 -c "
import json, glob, os
os.chdir('/app')
files=sorted(glob.glob('logs/ksef_metadata_probe/ksef_metadata_Subject2_Invoicing_*.json'))
d=json.load(open(files[-1]))
refs=[]
for k in ('invoices','invoiceList','items','results'):
    if isinstance(d.get(k),list):
        for i in d[k]:
            r=i.get('ksefNumber') or i.get('ksefReferenceNumber')
            if r: refs.append(r)
        break
dates=[r.split('-')[1][:8] for r in refs if '-' in r]
print('=== PARSE Invoicing ===')
print('refs_count=', len(refs))
print('hasMore=', d.get('hasMore'))
print('max_date_token=', max(dates) if dates else 'none')
j12=[r for r in refs if '-20260612-' in r]
print('june12_refs=', j12)
print('target_hits=', [r for r in refs if r.startswith('8762469751-20260612') or r.startswith('9512120077-20260612')])
print('json_file=', files[-1])
"
```

### C. Wariant `--auth session` (opcjonalnie — jak w sync DB token)

Zamień `--auth fresh` na:

```
--auth session --nip 9670402857
```

Przy **401** na `[query]` — użyj wariantu A/B z `--auth fresh`.

---

## Co porównać

| Metryka | PermanentStorage | Invoicing |
|---------|------------------|-----------|
| `refs_count` | IFG prod: 50 | ? |
| `hasMore` | ? | ? |
| `max_date_token` | prod: 20260605 | oczekiwane ≥ 20260612 |
| `june12_refs` | [] | GENERON/P4? |
| `target_hits` | [] | `8762469751-20260612*`, `9512120077-20260612*` |

Ref docelowe (portal, 12.06.2026):

- `8762469751-20260612...` (GENERON)
- `9512120077-20260612...` (P4)

---

## Logi probe (stdout)

Szukaj linii:

```
[auth] Nowy access_token z KSeFAuthProvider ...
[query] POST ... subjectType=Subject2 dateType=PermanentStorage|Invoicing
[result] subjectType=Subject2 dateType=... total=...
[result] first_ksef_numbers (5): [...]
[result] response saved: logs/ksef_metadata_probe/ksef_metadata_....json
```

Pełne JSON: `logs/ksef_metadata_probe/` w kontenerze `api` (mount repo).

---

## Paginacja (jeśli `hasMore=true`)

Powtórz probe z `--page-offset 50` dla danego `--date-type`.

---

## Interpretacja

| Wynik | Wniosek |
|-------|---------|
| Invoicing ma `target_hits`, PermanentStorage nie | Hipoteza **potwierdzona** — IFG powinien odpytywać Invoicing |
| Oba bez 12.06 | Hipoteza **niepotwierdzona** — sprawdzić paginację / opóźnienie indeksu KSeF |
| Oba z 12.06 | Problem w paginacji/break po PermanentStorage w `client.py`, nie w API |

---

## Wymagania

- `.env.production` z `KSEF_AUTH_TOKEN`, `DATABASE_URL`, `SELLER_NIP` (dla `--auth fresh`)
- Kontener `api` uruchomiony
- Skrypt już w repo (`scripts/ksef_metadata_probe.py`) — **bez nowego mechanizmu auth**
