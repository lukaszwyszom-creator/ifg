# Audyt gotowości magazynu IFG — 2026-06-20

**Środowisko:** DS723+ production  
**Tryb:** diagnostyka read-only, bez zmian danych/kodu  
**Zakres:** PZ, WZ, KK, `inventory_layers`, `inventory_layer_movements`, `warehouse_balance`, UI Stany/Dokumenty

---

## 1. Status deploymentu

| Element | Stan |
|---------|------|
| **HEAD DS723+** | `e9b1772` — `feat(warehouse): group stock by purchase price` |
| **Commit group by price** | ✅ obecny (HEAD = e9b1772) |
| **Poprzednie hotfixy** | `0eca052` (flush PZ edit) w API ✅; migracja `f8a9b0c1d2e3` (head) ✅ |
| **frontend-react/dist** | ✅ świeży: `index-aTbofISl.js` **2026-06-20 23:14** (~3 min po commicie 23:11) |
| **Bundel JS** | zawiera `Cena zakupu netto`, **brak** `Śr. cena` |
| **Źródło BalanceTab @ HEAD** | `aggregateBalanceByItemAndPrice`, nagłówek „Cena zakupu netto” |

**Wniosek deploymentu:** UI grupowania po cenie zakupu **wdrożone** na DS723+.

---

## 2. Audyt SQL (prod)

| Test | Wynik |
|------|-------|
| `warehouse_balance` vs `SUM(inventory_layers.remaining_quantity)` | ✅ **0 rozbieżności** |
| Warstwy bez `source_document_item_id` | ✅ **0** |
| Duplikaty `source_document_item_id` | ✅ **0** |
| `remaining_quantity < 0` | ✅ **0** |
| `remaining_quantity > received_quantity` | ✅ **0** |
| PZ draft bez warstwy | ✅ **0** (1 PZ draft ma warstwę) |
| PZ posted bez ceny na warstwie | ✅ **0** |
| WZ posted bez movements | ✅ **0** |
| Movements bez layer | ✅ **0** |
| Aktywne warstwy bez ceny | **1** — PZ draft 15 szt. (oczekiwane) |

### Stan dokumentów (prod)

| Typ | Status | Liczba |
|-----|--------|--------|
| PZ | posted | 1 |
| PZ | draft | 1 |
| WZ | posted | 1 |
| WZ | draft | 1 |
| KK | posted | 1 |

### Warstwy FIFO

| Typ źródła | Warstwy | Suma remaining |
|------------|---------|----------------|
| PZ | 2 | 2014 |
| KK | 1 | 1 |

**Wartość magazynu (warstwy z ceną):** 62 760,00 zł netto

---

## 3. Towar: „Kościoły Archidiecezji Częstochowskiej t. II”

**item_id:** `cde30f78-eea0-4887-90fe-595dfba0d96a`

### Saldo

- `warehouse_balance.quantity_available` = **2015**

### Warstwy FIFO

| Warstwa | received | remaining | cena netto | Dokument | Status |
|---------|----------|-----------|------------|----------|--------|
| `051ff7a2…` | 2000 | **1999** | 31,38 | PZ/2026/0001 | posted |
| `23e2d229…` | 1 | **1** | 31,38 | KK/2026/0001 | posted |
| `9f13bea1…` | 15 | **15** | *null* | PZ draft | draft |

Suma remaining: **2015** = saldo ✅

### Dokumenty powiązane

| Dokument | Typ | Status | Ilość | Cena pozycji |
|----------|-----|--------|-------|--------------|
| PZ/2026/0001 | PZ | posted | 2000 | 31,38 |
| WZ/2026/0001 | WZ | posted | 1 | — |
| KK/2026/0001 | KK | posted | 1 | 31,38 |
| *(draft)* | PZ | draft | 15 | 20,00 (doc item; warstwa bez ceny do post) |
| *(draft)* | WZ | draft | 1 | — |

### Ruchy FIFO

- WZ/2026/0001: **1 szt.** z warstwy PZ @ 31,38 ✅

### Oczekiwany widok Stany (po e9b1772)

| Wiersz | Ilość | Cena zakupu netto | Wartość netto |
|--------|-------|-------------------|---------------|
| 1 | **2000** (1999+1 @ 31,38) | 31,38 zł | 62 760 zł |
| 2 | **15** | koszt nieustalony | — |

---

## 4. Weryfikacja scenariuszy biznesowych

| Scenariusz | Werdykt | Dowód |
|------------|---------|-------|
| PZ draft zwiększa stan | ✅ | Warstwa 15 szt. + saldo 2015 |
| Edycja PZ draft zmienia stan | ✅ | API hotfix `0eca052` w kontenerze; warstwa draft = 15 (po edycji 10→15) |
| Post PZ uzupełnia koszt | ✅ | PZ/2026/0001: warstwa `purchase_unit_price=31.38` |
| WZ draft nie zmniejsza | ✅ | WZ draft 1 szt.; saldo nadal 2015 |
| WZ posted zmniejsza | ✅ | WZ/2026/0001: movement 1 szt.; warstwa 2000→1999 |
| Różne ceny = osobne pozycje w Stany | ✅ | UI e9b1772 wdrożone; dane: 31,38 vs koszt nieustalony |
| Ta sama cena = suma ilości | ✅ | 1999+1 @ 31,38 → jeden wiersz 2000 |

---

## 5. Problemy

### Krytyczne

**Brak.** Integralność FIFO, salda, movements i dokumentów jest spójna.

### UX / wdrożenie częściowe

| Problem | Priorytet | Opis |
|---------|-----------|------|
| DocumentsTab bez kolumny „Towar” | średni | Prod dist nadal ma „Opis / Powód”; `DocumentsTab.jsx` + CSS **niezacommitowane** lokalnie |
| Mała baza testowa prod | niski | 1 SKU, 5 dokumentów — ograniczona reprezentatywność |
| PZ draft z ceną w formularzu, warstwa bez ceny | info | Zgodne z modelem: koszt na warstwie dopiero po post |

### E6 (blokada sprzedaży FV)

**Nie zaimplementowane** — to osobny etap (FV/invoices), nie magazyn. Magazyn E1–E5 jest stabilny.

---

## 6. Rekomendowane poprawki (bez wykonania)

1. **Deploy kolumny „Towar” w Dokumentach** — commit + build + rsync dist (osobny PR).
2. **Ręczna weryfikacja UI Stany** — potwierdzić 2 wiersze dla książki Częstochowskiej (2000 @ 31,38 + 15 koszt nieustalony).
3. **Soak 1–2 dni robocze** na prod przed startem E6 (zgodnie z planem PZ draft).
4. **E6:** implementacja blokady FV przy braku stanu — osobny sprint, backend + frontend faktur.
5. **Opcjonalnie:** zaksięgować lub anulować PZ draft testowy (15 szt.) gdy zakończą się testy operacyjne.

---

## 7. Czy magazyn jest gotowy do E6?

| Warstwa | Gotowość |
|---------|----------|
| Dane (FIFO, salda, warstwy) | ✅ **TAK** |
| API (PZ draft, edit, post, WZ) | ✅ **TAK** |
| UI Stany (grupowanie po cenie) | ✅ **TAK** (wdrożone e9b1772) |
| UI Dokumenty | ⚠️ częściowo (brak kolumny Towar) |
| **E6 jako funkcja (blokada FV)** | ❌ **NIE** — do zbudowania |

**Ocena:** Fundament magazynowy **gotowy do rozpoczęcia prac nad E6**. Sam etap E6 wymaga nowej implementacji w module faktur; nie blokuje go stan danych magazynowych.

---

## 8. Metodologia

- SSH DS723+: git, dist, API inspect, `psql` przez docker compose
- Bez migracji, resetu DB, modyfikacji wolumenów i danych
