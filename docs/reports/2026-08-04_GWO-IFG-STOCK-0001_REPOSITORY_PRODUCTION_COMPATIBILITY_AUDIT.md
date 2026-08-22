# GWO-IFG-STOCK-0001 — Audyt zgodności repo developerskiego z produkcją IFG

**Wygenerowano:** 2026-08-04  
**Tryb:** read-only wobec produkcji DS723+  
**Commit audytowany (developerski):** `31c64ea771aa38001a8afce379636662f07f75e6`  
**Zakres commitu:** integracja faktura ↔ magazyn (`product_id`, ruchy SALE/PURCHASE, idempotencja)

---

## STATUS

**COMPLETE — BLOCKED**

Produkcja IFG **nie została zmieniona** (brak pull/checkout/build/restart/migracji/edycji `.env`).

## VERDICT

**C. BLOCKED**

Nie potwierdzono, że `~/projekty/program-do-faktur` jest bezpiecznym, liniowym źródłem wdrożenia commitu `31c64ea` do runtime  
`/volume1/docker/ifg_v2/ifg_standalone`.  
Z tego powodu **nie utworzono** wykonywalnego GWO deployu udającego gotowość. Utworzono dokument blokerów:  
`docs/gwo/GWO-IFG-STOCK-0002_BLOCKERS.md`.

---

## 1. Lokalny HEAD i origin/main (`program-do-faktur`)

| Pole | Wartość |
|------|---------|
| Path | `/Users/lukasz/projekty/program-do-faktur` |
| Toplevel | `/Users/lukasz/projekty/program-do-faktur` |
| Branch | `main` |
| HEAD | `31c64ea771aa38001a8afce379636662f07f75e6` |
| Origin URL | `git@github.com:lukaszwyszom-creator/program-do-faktur.git` |
| origin/main | `31c64ea771aa38001a8afce379636662f07f75e6` |
| Ahead/behind | `0 0` |
| Parent `31c64ea` | `9e9f4e3a7404e0ad589be1681c197b6321bec9b6` |
| Tagi na `31c64ea` | brak |
| Dirty worktree | tylko untracked: `.preview/`, `.preview_backups/`, `frontend-react/vite.preview.config.js`, `projekt_ifg.zip` |

**Pliki w `31c64ea`:** 16 (migracja `0011_k1l2…`, modele/serwisy stock+invoice, FE InvoiceForm/StockPage, testy).  
**Diffstat:** `+912 / −35`.

**Ryzyko deployu z dirty tree:** artefakty preview nie są w commitcie, ale obecność `.preview*` / zip należy wykluczyć z jakichkolwiek rsync/scp poza kontrolowanym Git.

---

## 2. Produkcyjny HEAD (DS723+ IFG)

| Pole | Wartość |
|------|---------|
| Path | `/volume1/docker/ifg_v2/ifg_standalone` |
| Jest Git | **tak** |
| Branch | `production` |
| HEAD | `9b4d187ef83cd54f9a433d238c9d43c35198699c` |
| Origin URL | `https://github.com/lukaszwyszom-creator/ifg.git` |
| origin/production (lokalny ref, **bez fetch**) | `9b4d187…` |
| Dirty | untracked: `.env.production.bak.*`, `backups/`, `logs/` |
| Obiekt `31c64ea` w prod repo | **ABSENT** |
| Image label `ifg.git.commit` | `9b4d187…` |
| Alembic current (prod DB) | **`p6q7r8s9t0u1` (head)** |

Kontenery (project Compose **`ifg`**): `ifg-api-1`, `ifg-worker-1`, `ifg-db-1`, `ifg-frontend-1` — healthy/up.  
Compose: `docker/docker-compose.prod.yml` + env `/volume1/docker/ifg_v2/ifg_standalone/.env.production`.  
DB volume: `docker_postgres_data`. Port API: `127.0.0.1:8000`.

**Mac `ifg_standalone`:** remote `ifg.git`, HEAD `5d07d6b`; `9b4d187` jest przodkiem Mac HEAD (prod jest w tej samej linii `ifg`, tylko starszy o kilka commitów docs/handoff).

---

## 3. Wspólna historia — potwierdzenie / brak

### Dowody **braku** wspólnej tożsamości Git do wdrożenia `31c64ea`

1. **Różne remote:** `program-do-faktur.git` ≠ `ifg.git`.  
2. **Brak wspólnych obiektów commita:**  
   - w `program-do-faktur` nie ma `5d07d6b` / `9b4d187` / `969bea3`;  
   - w `ifg` (Mac i prod) nie ma `31c64ea` / `9e9f4e3` / `ffea643`.  
3. **Merge-base między remote’ami:** nieustalony / niemożliwy na podstawie dostępnych obiektów (brak wspólnych SHA).  
4. **Kolizja ID Alembic:** revision `k1l2m3n4o5p6` w obu drzewach oznacza **różne migracje**:  
   - `program-do-faktur`: `invoice_item_product_and_stock_movement_idempotency` (parent `j0k1…`);  
   - `ifg`: `remove_draft_status` (parent `j0k1…`), a head produkcji to już `p6q7r8s9t0u1`.  

### Dowody **częściowego** wspólnego dziedzictwa kodu (nie wystarczające do deployu)

- Plik `0009_i9j0k1l2m3n4_stock_module.py` ma **identyczny SHA-256** w obu repo (historyczny fork / kopia ścieżki stock).  
- Oba repo mają tabele `products` / `stock` / `stock_movements` oraz `StockService`.  
- IFG ma **dodatkowo** pełny magazyn biznesowy: `warehouse_items`, `warehouse_documents`, FIFO, WZ/PZ — nieobecny w głównym torze `program-do-faktur` (head kończy się na `k1l2` stock-idempotency).

**Wniosek:** to **nie są dwa środowiska tego samego repozytorium Git**. To pokrewne / rozwidlone linie aplikacji IFG. Commit `31c64ea` **nie istnieje** w produkcyjnym `ifg.git` i **nie da się** go „ściągnąć” przez `git pull` w `/volume1/docker/ifg_v2/ifg_standalone`.

---

## 4. Porównanie Compose i runtime

| Aspekt | `program-do-faktur` (dev) | Prod IFG |
|--------|---------------------------|----------|
| Compose prod | `docker/docker-compose.prod.yml` (project historycznie „docker” / PDF) | `docker/docker-compose.prod.yml`, **project=`ifg`** |
| Usługi | api, worker, db, frontend | api, worker, db, frontend (+ cloudflared osobno) |
| Image API | budowany z Dockerfile PDF | `ifg-api:latest` z label `ifg.git.commit` |
| DB volume | osobny w PDF compose | **`docker_postgres_data`** (współdzielony z historią IFG) |
| Porty preview lokalne | 8001 / 5173 / 5433 (izolowany preview) | `127.0.0.1:8000`, frontend kontener |
| Migracje | head `k1l2m3n4o5p6` (stock idempotency) | head **`p6q7r8s9t0u1`** |
| KSeF / SMTP | obecne w `.env` PDF | klucze SMTP_*, KSEF_*, PURCHASE_SYNC_NOTIFY_* w `.env.production` (wartości **nie** ujawnione) |
| Guardian | skrypt `deploy_ds723.sh` w PDF (nieadekwatny) | pełny `scripts/ifg_guardian`, cutover, doctor |

**Commit `31c64ea` nie zakłada osobnego wolumenu w samym diffie kodu**, ale **wcześniejszy błędny plan deployu** zakładał osobny stack PDF — to było niepoprawne względem produkcji IFG.

---

## 5. Stan migracji lokalnej i produkcyjnej

### `program-do-faktur`

Łańcuch (skrót):  
`6462… → … → h8i9 → i9j0 (stock_module) → j0k1 (sku→isbn) → **k1l2 (product_id + invoice_item_id + unique)**`.

Migracja `k1l2` jest additive: nullable columns + FK RESTRICT/SET NULL + unique — **bez DROP**.

### Produkcja IFG

- `alembic_version` = **`p6q7r8s9t0u1`**.  
- W drzewie migracji IFG revision **`k1l2m3n4o5p6` już zużyte** przez `remove_draft_status`, po czym idą m.in. due_date, xml, ksef sync, warehouse FIFO, notifications.  
- **Liniowe `alembic upgrade` migracji z PDF o ID `k1l2` na prod jest niemożliwe** (kolizja revision + prod już dawno przeszedł ten ID).

### Schemat prod (istotne kolumny)

- `invoice_items`: **brak** `product_id`.  
- `stock_movements`: **brak** `invoice_item_id`; jest `invoice_id` (SET NULL).  
- Istnieją `products`, `stock`, `warehouses`, `stock_movements` **oraz** `warehouse_*`.  
- Unique `uq_stock_movement_invoice_item_type`: **nie istnieje** na prod.

**Precheck danych / destrukcja:** sama migracja PDF jest niedestrukcyjna, ale **nie jest aplikowalna jako-ta** na prod. Wymagana byłaby **nowa migracja w `ifg.git`** z unikalnym `revision` po `p6q7…`, plus port kodu.

---

## 6. Analiza wpływu commitu `31c64ea` (na IFG — koncepcyjnie)

### Zachowania w PDF (po `31c64ea`) — obsługiwane

- Opcjonalne `product_id` na pozycji faktury.  
- Auto SALE/PURCHASE przez `StockService.create_movement` + `handle_invoice_created`.  
- Pomiń `product_id=null`.  
- Oversell → błąd, rollback transakcji faktury.  
- Idempotencja `(invoice_item_id, movement_type)`.  
- TRANSFER wycofany z API/UI.  
- Helper `reverse_invoice_stock_movements` (bez lifecycle cancel w API).

### Stan IFG dziś

- Hook w `InvoiceService` woła `handle_invoice_created` z **`hasattr(item, "product_id")`**, podczas gdy model/ORM **nie mają** `product_id` → logika magazynu z faktury jest **martwa**.  
- Równolegle działa **warehouse documents** (PZ/WZ/FIFO) — kanoniczny tor magazynu biznesowego IFG.  
- Istniejące faktury/pozycje bez `product_id` — zgodne z null; import KSeF bez mapowania produktu — bez ruchów stock (jak w PDF).

### Ryzyka blokujące „ślepy” deploy `31c64ea` na IFG

1. Commit nie jest w `ifg.git`.  
2. Kolizja Alembic `k1l2`.  
3. Dual model magazynu (stock vs warehouse_*) — niespójność produktowa bez decyzji domenowej.  
4. Cherry-pick bez rebase migracji uszkodziliby historię Alembic.  
5. Prod HEAD ≠ Mac IFG HEAD (luka docs) — osobny temat sync, nie rozwiązany przez PDF.

### Ryzyka akceptowalne po portowaniu (dokumentacja)

- Create-only lifecycle faktury.  
- TRANSFER wycofany.  
- KSeF bez `product_id` → brak ruchów stock.

---

## 7. Wykryte rozbieżności (lista)

1. Remote Git: `program-do-faktur` vs `ifg`.  
2. Brak obiektu `31c64ea` na produkcji.  
3. Alembic head: `k1l2` (PDF) vs `p6q7` (prod).  
4. Znaczenie `k1l2`: stock idempotency vs remove_draft_status.  
5. Brak `product_id` / `invoice_item_id` na prod schema.  
6. IFG ma warehouse FIFO; PDF commit nie integruje się z `warehouse_documents`.  
7. Błędny wcześniejszy plan zakładał osobny stack PDF na DS723+.  
8. Backup IFG kanoniczny obserwowany: `/volume1/docker/ifg_v2/backups/` oraz `…/ifg_standalone/backups/` — **nie** `/volume2/.../program-do-faktur` jako źródło prawdy IFG.

---

## 8. Warunki bezpiecznego deployu (przyszłe — poza tym GWO)

Dopiero po usunięciu blokerów z `GWO-IFG-STOCK-0002_BLOCKERS.md`:

1. Port funkcjonalny **do `ifg.git`** (nie pull PDF).  
2. Nowa migracja z **nowym** `revision` po `p6q7r8s9t0u1`.  
3. Decyzja: stock↔FV vs warehouse_items/documents.  
4. Backup zweryfikowany w `/volume1/docker/ifg_v2/backups/`.  
5. Osobne GWO deploy IFG na istniejącym project `ifg`.

---

## 9. Czy powstało poprawione GWO deployu?

**NIE** (werdykt BLOCKED).  
Powstał dokument blokerów: `docs/gwo/GWO-IFG-STOCK-0002_BLOCKERS.md`.

---

## 10. Potwierdzenie braku zmian produkcji

| Operacja | Wykonano? |
|----------|-----------|
| git pull / checkout / reset na DS723+ | **NIE** |
| docker compose up/down/build/restart | **NIE** |
| alembic upgrade/downgrade | **NIE** |
| zapis do DB / `.env.production` | **NIE** |
| kopiowanie plików na DS723+ | **NIE** |
| push commitów | **NIE** |

Odczyt: SSH `git status/log`, `docker ps/inspect`, `alembic current`, `\d` tabel, lista kluczy env (bez wartości).

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [ ] DEPLOYED_TO_DS723  
- [ ] PRODUCTION_VERIFIED  

## Decyzje dla ChatGPT

1. Czy kanonicznym źródłem kodu IFG pozostaje wyłącznie `ifg.git`, a `program-do-faktur` traktujemy jako repo pokrewne / legacy do portowania?  
2. Czy integracja FV↔stock ma iść w tor `products/stock_*`, czy docelowo łączyć się z `warehouse_items` / dokumentami PZ/WZ?  
3. Czy akceptujemy port `31c64ea` jako nowy commit w `ifg` z nową migracją po `p6q7…`?

## Wygenerowane raporty

- `docs/reports/2026-08-04_GWO-IFG-STOCK-0001_REPOSITORY_PRODUCTION_COMPATIBILITY_AUDIT.md`  
- `docs/gwo/GWO-IFG-STOCK-0002_BLOCKERS.md`
