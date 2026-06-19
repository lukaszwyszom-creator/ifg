-- E3: weryfikacja backfillu PZ draft (gate przed deployem E4)
-- Oczekiwany wynik każdego SELECT count: 0 wierszy (poza E3-6 gdy brak draft)

-- E3-1: linie draft PZ bez warstwy
SELECT di.id AS orphan_doc_item
FROM warehouse_documents d
JOIN warehouse_document_items di ON di.document_id = d.id
LEFT JOIN inventory_layers il ON il.source_document_item_id = di.id
WHERE d.doc_type = 'PZ' AND d.status = 'draft' AND il.id IS NULL;

-- E3-2: duplikaty source_document_item_id
SELECT source_document_item_id, COUNT(*) AS cnt
FROM inventory_layers
WHERE source_document_item_id IS NOT NULL
GROUP BY source_document_item_id
HAVING COUNT(*) > 1;

-- E3-3: warehouse_balance vs suma warstw
SELECT wb.item_id,
       wb.quantity_available AS balance_cache,
       COALESCE(SUM(il.remaining_quantity), 0) AS layers_sum
FROM warehouse_balance wb
LEFT JOIN inventory_layers il ON il.item_id = wb.item_id
GROUP BY wb.item_id, wb.quantity_available
HAVING wb.quantity_available != COALESCE(SUM(il.remaining_quantity), 0);

-- E3-4: spójność qty linii draft vs warstwa
SELECT di.id, di.quantity, il.received_quantity, il.remaining_quantity
FROM warehouse_documents d
JOIN warehouse_document_items di ON di.document_id = d.id
JOIN inventory_layers il ON il.source_document_item_id = di.id
WHERE d.doc_type = 'PZ' AND d.status = 'draft'
  AND (di.quantity != il.received_quantity OR il.remaining_quantity > il.received_quantity);

-- E3-5: posted PZ bez warstwy lub bez ceny
SELECT d.id, d.number
FROM warehouse_documents d
JOIN warehouse_document_items di ON di.document_id = d.id
LEFT JOIN inventory_layers il ON il.source_document_item_id = di.id
WHERE d.doc_type = 'PZ' AND d.status = 'posted'
  AND (il.id IS NULL OR il.purchase_unit_price IS NULL);

-- E3-6: liczba warstw draft bez kosztu (informacyjnie)
SELECT COUNT(*) AS draft_layers_without_cost
FROM inventory_layers il
JOIN warehouse_document_items di ON di.id = il.source_document_item_id
JOIN warehouse_documents d ON d.id = di.document_id
WHERE d.doc_type = 'PZ' AND d.status = 'draft'
  AND il.purchase_unit_price IS NULL;
