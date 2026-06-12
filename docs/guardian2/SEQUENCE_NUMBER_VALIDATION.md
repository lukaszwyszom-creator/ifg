# Walidacja `get_next_sequence_number`

**Data:** 2026-05-22  
**Kontekst:** weryfikacja ustalenia z `KSEF_PURCHASE_NUMBERING_AUDIT.md`

---

## 1. Implementacja (przed fixem)

```145:160:app/persistence/repositories/invoice_repository.py
    def get_next_sequence_number(self, year: int, month: int) -> int:
        ...
        stmt = select(func.count(InvoiceORM.id)).where(
            InvoiceORM.issue_date >= month_start,
            InvoiceORM.issue_date < month_end,
            InvoiceORM.number_local.isnot(None),
        )
        count = self.session.execute(stmt).scalar_one()
        return count + 1
```

**Jedyne wywołanie:** `InvoiceService._assign_number_local` (`app/services/invoice_service.py`, linia ~526) — nadawanie numeru IFG wyłącznie fakturze **sale**.

---

## 2. Odpowiedź: czy purchase wpływa na sekwencję sprzedaży?

**TAK (przed fixem).**

Faktury zakupowe z wypełnionym `number_local` (np. numer P_2 z importu KSeF) były liczone w `COUNT(*)` dla danego miesiąca. Skutek:

- Następny numer sale mógł być **zawyżony** (luki w sekwencji IFG).
- Teoretycznie: numer dostawcy w formacie `FV/n/MM/YYYY` mógł też wpływać na count (choć `_assign_number_local` i tak generuje unikalny numer — ryzyko kolizji przez `exists_by_number`, nie duplikatu seq).

Purchase **nie** nadawał numeru IFG przez tę metodę (guard w `mark_as_ready` / `ensure_number_local`), ale **partycypował w liczeniu** bazy dla kolejnego seq.

---

## 3. Fix (minimalny)

Dodano filtr `InvoiceORM.direction == "sale"` w `get_next_sequence_number`.

```python
stmt = select(func.count(InvoiceORM.id)).where(
    InvoiceORM.issue_date >= month_start,
    InvoiceORM.issue_date < month_end,
    InvoiceORM.number_local.isnot(None),
    InvoiceORM.direction == "sale",
)
```

**Zakres zmian:** wyłącznie `app/persistence/repositories/invoice_repository.py` + test regresyjny.

---

## 4. Test regresyjny

Plik: `tests/unit/test_invoice_repository_sequence.py`

Scenariusz:
- 1× sale z `number_local` w kwietniu 2026
- 2× purchase z `number_local` w tym samym miesiącu
- Oczekiwany wynik: `get_next_sequence_number(2026, 4) == 2` (nie 4)

```bash
pytest tests/unit/test_invoice_repository_sequence.py -q
```

---

## 5. Werdykt

| Pytanie | Przed fixem | Po fixie |
|---------|-------------|----------|
| Purchase w COUNT seq? | TAK | NIE |
| Wpływ na numer IFG sale? | TAK (zawyżenie seq) | NIE |
| Zgodność z audytem Guardian2 | Potwierdzone | Naprawione |
