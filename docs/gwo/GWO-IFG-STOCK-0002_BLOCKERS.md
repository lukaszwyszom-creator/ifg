# GWO-IFG-STOCK-0002 — BLOCKERS (brak gotowości deployu)

**Powód:** wynik audytu GWO-IFG-STOCK-0001 = **BLOCKED**.  
**Zakaz:** nie wykonywać deployu commitu `31c64ea` z `program-do-faktur` na  
`/volume1/docker/ifg_v2/ifg_standalone` do czasu usunięcia blokerów poniżej.  
**Produkcja:** nietknięta przez GWO-0001.

Kanoniczny raport:  
`docs/reports/2026-08-04_GWO-IFG-STOCK-0001_REPOSITORY_PRODUCTION_COMPATIBILITY_AUDIT.md`

---

## BLOCKER B1 — Różne repozytoria Git (krytyczny)

| | Developerskie | Produkcja IFG |
|--|--|--|
| Remote | `github.com/lukaszwyszom-creator/program-do-faktur.git` | `github.com/lukaszwyszom-creator/ifg.git` |
| Commit `31c64ea` | obecny na `main` | **ABSENT** w obiektach Git |
| Prod HEAD | n/d | `9b4d187` na `production` |

**Skutek:** `git pull` w katalogu produkcyjnym IFG **nigdy** nie pobierze `31c64ea`.

**Wymagany dowód do odblokowania:**  
pisemna decyzja, że kanoniczne źródło wdrożeń IFG = `ifg.git`; zmiany magazynowe portowane jako nowe commity w `ifg`.

**Kolejność:** najpierw B1, potem B2–B4.

---

## BLOCKER B2 — Kolizja revision Alembic `k1l2m3n4o5p6` (krytyczny)

| Repo | Plik | Znaczenie `k1l2m3n4o5p6` |
|--|--|--|
| program-do-faktur | `0011_…_invoice_item_product_stock_idempotency.py` | `product_id` + `invoice_item_id` + unique |
| ifg | `0011_…_remove_draft_status.py` | normalizacja statusu DRAFT |

Prod DB: `alembic_version = p6q7r8s9t0u1` (head **po** zużytym już `k1l2`).

**Skutek:** nie wolno aplikować migracji PDF z ID `k1l2` na IFG.

**Wymagany dowód:** nowa migracja w `ifg` z **unikalnym** `revision`, `down_revision = p6q7r8s9t0u1` (lub aktualny head w chwili portu), zawierająca równoważne DDL (nullable `product_id`, `invoice_item_id`, FK, unique).

---

## BLOCKER B3 — Schemat prod niegotowy / inny model magazynu (wysoki)

Na produkcji (odczyt `\d`):

- `invoice_items` **bez** `product_id`;  
- `stock_movements` **bez** `invoice_item_id`;  
- równolegle pełny tor **`warehouse_items` / `warehouse_documents` (FIFO)**.

IFG kod ma martwy hook `hasattr(item, "product_id")` w `InvoiceService`, podczas gdy ORM nie eksponuje pola.

**Wymagany dowód:**

1. Decyzja domenowa: FV integruje się ze **stock/products** czy z **warehouse_items/documents**.  
2. Port kodu serwisów/FE do `ifg` zgodny z decyzją.  
3. Migracja + testy na kopii schematu IFG (nie PDF-only SQLite preview).

---

## BLOCKER B4 — Błędna ścieżka runtime w poprzednim planie (operacyjny)

Poprzedni plan zakładał osobny compose `program-do-faktur` na DS723+.  
Faktyczny runtime: Compose project **`ifg`**, working_dir  
`/volume1/docker/ifg_v2/ifg_standalone/docker`, volume DB `docker_postgres_data`.

**Wymagany dowód:** przyszłe GWO deployu adresuje **wyłącznie** ten runtime; zakaz drugiego stacku/bazy/portów kolidujących z `8000`.

---

## BLOCKER B5 — Sync Mac IFG vs prod HEAD (średni, osobny)

| | HEAD |
|--|--|
| Prod DS723+ | `9b4d187` |
| Mac `ifg_standalone` | `5d07d6b` (potomek `9b4d187`) |

**Wymagany dowód:** kontrolowany sync docs/handoff na prod **przed** dużym deployem feature (osobne GWO), żeby nie mieszać luk docs z portem stock.

---

## Bezpieczna kolejność usuwania blokerów

1. **Decyzja ChatGPT/operator:** kanon = `ifg.git`; PDF = źródło do portu (nie do pull).  
2. **Decyzja domenowa magazynu:** stock vs warehouse_*.  
3. Utworzyć gałąź w `ifg`: port logiki z `31c64ea` (bez kopiowania pliku migracji z kolizją ID).  
4. Dodać migrację po aktualnym head IFG; dry-run na kopii DB.  
5. Testy integracyjne na schemacie IFG (w tym współistnienie warehouse_*).  
6. Dopiero wtedy napisać **wykonywalne** GWO-IFG-STOCK-0002_CONTROLLED_IFG_STOCK_DEPLOY.md (nowa rewizja dokumentu).  
7. Backup do **`/volume1/docker/ifg_v2/backups/`** (oraz ewidencja w `ifg_standalone/backups/`), nie do ścieżki PDF.

---

## Czego NIE robić

- `git pull` / cherry-pick `31c64ea` bezpośrednio na prod.  
- `alembic upgrade` migracji PDF na bazie IFG.  
- Tworzenie stacku `program-do-faktur` / drugiej Postgres / drugiego volume.  
- Deploy „na skróty” mimo BLOCKED.

---

## Backup IFG (lokalizacje potwierdzone odczytem)

- `/volume1/docker/ifg_v2/backups/` (m.in. `ksef_backend_20260708_230227.dump`)  
- `/volume1/docker/ifg_v2/ifg_standalone/backups/` (m.in. `pre_recovery_*.dump`)  
- `/volume2/Dane/backup/program-do-faktur/` — **nie** traktować jako kanoniczny backup runtime IFG

---

## STATUS dokumentu

**BLOCKERS_PUBLISHED** — deploy GWO niegotowy.
