import { useState, useEffect, Fragment } from 'react';
import { warehouseDocumentsApi } from '../../../api/warehouseDocuments';
import { warehouseItemsApi } from '../../../api/warehouseItems';
import styles from '../WarehousePage.module.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABELS = { draft: 'Draft', posted: 'Zaksięgowany', cancelled: 'Anulowany' };

function StatusBadge({ status }) {
  const cls =
    status === 'posted'
      ? styles.badgePosted
      : status === 'cancelled'
        ? styles.badgeCancelled
        : styles.badgeDraft;
  return <span className={cls}>{STATUS_LABELS[status] ?? status}</span>;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('pl-PL');
}

function apiErr(err) {
  return (
    err?.response?.data?.error?.message ??
    err?.response?.data?.detail ??
    'Błąd operacji'
  );
}

function normalizeVatRateForSelect(value) {
  const text = String(value ?? '').trim();
  if (!text) return '23';
  const n = Number.parseFloat(text.replace(',', '.'));
  if (!Number.isFinite(n)) return '23';
  if (n <= 0.5) return '0';
  if (n >= 22.5 && n <= 23.5) return '23';
  if (n >= 7.5 && n <= 8.5) return '8';
  if (n >= 4.5 && n <= 5.5) return '5';
  return String(Math.round(n));
}

function sanitizeIntegerQty(value, allowNegative = false) {
  const raw = String(value ?? '').trim();
  if (raw === '' || (allowNegative && raw === '-')) return raw;
  const parsed = parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed === 0) return raw === '0' ? '0' : '';
  return String(parsed);
}

function fmtIntegerQty(value) {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return String(Math.trunc(n));
}

function fmtMoney2(value) {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtVatRate(value) {
  if (value == null || value === '') return '—';
  const normalized = normalizeVatRateForSelect(value);
  return `${normalized}%`;
}

function netToGrossDisplay(net, vatRate) {
  const n = Number(net);
  const rate = Number.parseFloat(String(vatRate ?? '23').replace(',', '.'));
  if (!Number.isFinite(n)) return '—';
  if (!Number.isFinite(rate) || rate <= 0) return fmtMoney2(n);
  return fmtMoney2(n * (1 + rate / 100));
}

function wzSalePriceGross(it, ci) {
  const vat = it.vat_rate ?? ci?.vat_rate;
  if (it.suggested_sale_price != null) {
    if (it.suggested_sale_price_mode === 'gross') return fmtMoney2(it.suggested_sale_price);
    if (it.suggested_sale_price_mode === 'net') {
      return netToGrossDisplay(it.suggested_sale_price, vat);
    }
  }
  if (ci?.suggested_sale_price != null) {
    const mode = ci.suggested_sale_price_mode ?? 'net';
    if (mode === 'gross') return fmtMoney2(ci.suggested_sale_price);
    return netToGrossDisplay(ci.suggested_sale_price, ci.vat_rate);
  }
  if (it.unit_price_net != null) {
    return netToGrossDisplay(it.unit_price_net, vat);
  }
  return '—';
}

function detailItemColSpan(docType) {
  if (docType === 'PZ') return 5;
  if (docType === 'WZ') return 3;
  if (docType === 'KK') return 3;
  return 4;
}

function kkQuantityDirectionHint(quantity) {
  if (quantity === '' || quantity == null) return null;
  const n = Number(quantity);
  if (!Number.isFinite(n) || n === 0) return null;
  if (n > 0) return 'Korekta dodatnia — przyjęcie na stan';
  return 'Korekta ujemna — zdjęcie ze stanu';
}

function sumDocItemQuantities(items) {
  if (!items?.length) return null;
  return items.reduce((acc, it) => {
    const n = Number(it.quantity);
    return Number.isFinite(n) ? acc + n : acc;
  }, 0);
}

function fmtDocListQtyImpact(docType, items) {
  if (!items?.length) return '—';
  const sum = sumDocItemQuantities(items);
  if (!Number.isFinite(sum)) return '—';
  const qty = Math.trunc(sum);
  if (docType === 'PZ') return `+${Math.abs(qty)}`;
  if (docType === 'WZ') return `-${Math.abs(qty)}`;
  if (qty > 0) return `+${qty}`;
  if (qty < 0) return String(qty);
  return '0';
}

function shortItemId(itemId) {
  if (!itemId) return '—';
  const s = String(itemId);
  return s.length > 8 ? `${s.slice(0, 8)}…` : s;
}

function resolveDocItemLabel(docItem, catalogById) {
  const cat = catalogById[String(docItem.item_id)];
  if (cat?.name) return cat.name;
  if (cat?.isbn) return cat.isbn;
  return shortItemId(docItem.item_id);
}

function fmtDocListItemsSummary(items, catalogById) {
  if (!items?.length) return { text: '—', title: '' };
  const labels = items.map((it) => resolveDocItemLabel(it, catalogById));
  const title = labels.join('\n');
  if (labels.length === 1) return { text: labels[0], title };
  return { text: `${labels[0]} +${labels.length - 1}`, title };
}

// ── DocList ───────────────────────────────────────────────────────────────────

function DocList({ onNew, onOpen, refreshKey }) {
  const [docs, setDocs] = useState([]);
  const [catalogById, setCatalogById] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([
      warehouseDocumentsApi.list({ limit: 200 }),
      warehouseItemsApi.list().catch(() => ({ items: [] })),
    ])
      .then(([docRes, catalogRes]) => {
        setDocs(docRes.items ?? []);
        const allItems = catalogRes.items ?? catalogRes ?? [];
        setCatalogById(Object.fromEntries(allItems.map((ci) => [String(ci.id), ci])));
      })
      .catch(() => setError('Błąd ładowania dokumentów'))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  if (loading) return <p className={styles.emptyMsg}>Ładowanie…</p>;
  if (error) return <p style={{ color: 'var(--color-error)' }}>{error}</p>;

  return (
    <div>
      <div className={styles.catalogToolbar}>
        <span className={styles.sectionTitle}>Dokumenty magazynowe</span>
        <button className="btn btn-primary" onClick={onNew}>
          + Nowy dokument
        </button>
      </div>

      {docs.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyMsg}>Brak dokumentów magazynowych</p>
          <button className="btn btn-primary" onClick={onNew}>
            + Nowy dokument
          </button>
        </div>
      ) : (
        <table className={styles.catalogTable}>
          <thead>
            <tr>
              <th>Numer</th>
              <th>Typ</th>
              <th>Data</th>
              <th>Towar</th>
              <th className={styles.right}>ILOŚĆ</th>
              <th className={styles.right}>Pozycji</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => {
              const itemSummary = fmtDocListItemsSummary(d.items, catalogById);
              return (
              <tr
                key={d.id}
                style={{ cursor: 'pointer' }}
                onClick={() => onOpen(d.id)}
              >
                <td>
                  {d.number ?? (
                    <span style={{ color: 'var(--color-text-secondary)' }}>
                      — draft —
                    </span>
                  )}
                </td>
                <td>
                  <strong>{d.doc_type}</strong>
                </td>
                <td>{fmtDate(d.created_at)}</td>
                <td
                  className={styles.docListItemCell}
                  title={itemSummary.title || undefined}
                >
                  {itemSummary.text}
                </td>
                <td className={styles.right}>{fmtDocListQtyImpact(d.doc_type, d.items)}</td>
                <td className={styles.right}>{d.items?.length ?? '?'}</td>
                <td>
                  <StatusBadge status={d.status} />
                </td>
              </tr>
            );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── DocForm ───────────────────────────────────────────────────────────────────

let _keySeq = 1;
const nextKey = () => ++_keySeq;
const VAT_OPTIONS = ['0', '5', '8', '23'];

const emptyRow = () => ({
  _key: nextKey(),
  item_id: '',
  quantity: '',
  purchase_unit_price: '',
  unit_price_net: '',
  vat_rate: '23',
  suggested_sale_price: '',
});

function DocForm({ onSaved, onCancel, initial }) {
  const isEdit = Boolean(initial?.id);
  const [docType, setDocType] = useState(initial?.doc_type ?? 'PZ');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [correctionReason, setCorrectionReason] = useState(initial?.correction_reason ?? '');
  const [issueReason, setIssueReason] = useState(initial?.issue_reason ?? '');
  // WZ z fakturą — currently always false (TODO: spięcie z FV)
  const [hasInvoice] = useState(!!initial?.source_invoice_id);
  const [items, setItems] = useState(
    initial?.items?.length
      ? initial.items.map((it) => ({
          _key: nextKey(),
          item_id: it.item_id,
          quantity: String(it.quantity),
          purchase_unit_price: it.purchase_unit_price != null ? String(it.purchase_unit_price) : '',
          unit_price_net: it.unit_price_net != null ? String(it.unit_price_net) : '',
          vat_rate: it.vat_rate != null ? String(it.vat_rate) : '23',
          suggested_sale_price: it.suggested_sale_price != null ? String(it.suggested_sale_price) : '',
        }))
      : [emptyRow()]
  );
  const [catalog, setCatalog] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    warehouseItemsApi
      .list()
      .then((r) => setCatalog((r.items ?? r).filter((ci) => ci.is_active)))
      .catch(() => {});
  }, []);

  const catalogMap = Object.fromEntries(catalog.map((ci) => [ci.id, ci]));
  const warehouseItems = catalog.filter((ci) => ci.is_warehouse_active);

  const addRow = () => setItems((p) => [...p, emptyRow()]);
  const removeRow = (key) => setItems((p) => p.filter((i) => i._key !== key));
  const setField = (key, field, val) =>
    setItems((p) => p.map((i) => (i._key === key ? { ...i, [field]: val } : i)));

  const selectItem = (rowKey, itemId) => {
    setItems((p) =>
      p.map((row) => {
        if (row._key !== rowKey) return row;
        const ci = catalogMap[itemId];
        const next = { ...row, item_id: itemId };
        if (docType === 'PZ' && ci) {
          if (ci.vat_rate != null) {
            next.vat_rate = normalizeVatRateForSelect(ci.vat_rate);
          }
          if (ci.suggested_sale_price != null) {
            next.suggested_sale_price = String(ci.suggested_sale_price);
          }
        }
        return next;
      })
    );
  };

  const needsPurchasePrice = (row) => {
    if (docType === 'PZ') return true;
    if (docType === 'KK') return row.quantity === '' || Number(row.quantity) >= 0;
    return false;
  };

  const handleDocTypeChange = (nextType) => {
    setDocType(nextType);
    setError('');
  };

  const validateForm = () => {
    if (items.length === 0) return 'Dodaj co najmniej jedną pozycję.';
    for (let i = 0; i < items.length; i++) {
      const row = items[i];
      const nr = i + 1;
      if (!row.item_id) return `Pozycja ${nr}: wybierz towar.`;
      const qty = Number(row.quantity);
      if (row.quantity === '' || isNaN(qty) || qty === 0 || !Number.isInteger(qty))
        return `Pozycja ${nr}: ilość musi być liczbą całkowitą różną od zera.`;
      if (docType === 'PZ') {
        if (row.purchase_unit_price !== '') {
          const price = Number(row.purchase_unit_price);
          if (isNaN(price) || price < 0)
            return `Pozycja ${nr}: cena zakupu musi być >= 0 (lub pusta w draft).`;
        }
        if (row.vat_rate === '' || row.vat_rate == null)
          return `Pozycja ${nr}: stawka VAT jest wymagana.`;
        if (row.suggested_sale_price !== '') {
          const sp = Number(row.suggested_sale_price);
          if (isNaN(sp) || sp < 0)
            return `Pozycja ${nr}: normatywna cena sprzedaży brutto musi być >= 0.`;
        }
      }
      if (docType === 'KK' && qty > 0) {
        const price = Number(row.purchase_unit_price);
        if (row.purchase_unit_price === '' || isNaN(price) || price < 0)
          return `Pozycja ${nr}: cena zakupu wymagana dla dodatniej korekty.`;
      }
    }
    if (docType === 'WZ' && !hasInvoice && !issueReason.trim())
      return 'WZ bez faktury wymaga podania powodu wydania.';
    if (docType === 'KK' && !correctionReason.trim())
      return 'Korekta (KK) wymaga podania powodu korekty.';
    return null;
  };

  const handleSave = async () => {
    const validationError = validateForm();
    if (validationError) { setError(validationError); return; }
    setError('');
    const body = {
      doc_type: docType,
      notes: notes.trim() || undefined,
      correction_reason: docType === 'KK' ? correctionReason.trim() || undefined : undefined,
      issue_reason: docType === 'WZ' && !hasInvoice ? issueReason.trim() || undefined : undefined,
      items: items.map((it) => ({
        item_id: it.item_id,
        quantity: it.quantity,
        purchase_unit_price: it.purchase_unit_price || undefined,
        unit_price_net: it.unit_price_net || undefined,
        vat_rate:
          docType === 'PZ'
            ? it.vat_rate !== '' && it.vat_rate != null
              ? it.vat_rate
              : undefined
            : it.item_id && catalogMap[it.item_id]?.vat_rate != null
              ? catalogMap[it.item_id].vat_rate
              : undefined,
        suggested_sale_price:
          docType === 'PZ' && it.suggested_sale_price !== ''
            ? it.suggested_sale_price
            : undefined,
        suggested_sale_price_mode:
          docType === 'PZ' && it.suggested_sale_price !== ''
            ? 'gross'
            : undefined,
      })),
    };
    setBusy(true);
    try {
      const doc = isEdit
        ? await warehouseDocumentsApi.update(initial.id, body)
        : await warehouseDocumentsApi.create(body);
      onSaved(doc.id);
    } catch (err) {
      setError(apiErr(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className={styles.catalogToolbar}>
        <span className={styles.sectionTitle}>
          {isEdit ? `Edycja dokumentu (${docType})` : 'Nowy dokument magazynowy'}
        </span>
        <button className="btn btn-secondary" onClick={onCancel}>
          Anuluj
        </button>
      </div>

      {/* Nagłówek */}
      <div className={styles.card}>
        <div className={styles.formRowMain} style={{ gap: 12 }}>
          <div style={{ flex: '0 0 160px' }}>
            <label className={styles.fieldLabel}>Typ dokumentu</label>
            <select
              className="input"
              value={docType}
              disabled={isEdit}
              onChange={(e) => handleDocTypeChange(e.target.value)}
            >
              <option value="PZ">PZ — Przyjęcie</option>
              <option value="WZ">WZ — Wydanie</option>
              <option value="KK">KK — Korekta</option>
            </select>
          </div>

          <div style={{ flex: '2 1 180px' }}>
            <label className={styles.fieldLabel}>Opis / Notatki</label>
            <input
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Opcjonalnie"
            />
          </div>

          {docType === 'KK' && (
            <div style={{ flex: '2 1 200px' }}>
              <label className={styles.fieldLabel}>Powód korekty *</label>
              <input
                className="input"
                value={correctionReason}
                onChange={(e) => setCorrectionReason(e.target.value)}
                placeholder="Wymagane"
              />
            </div>
          )}

          {docType === 'WZ' && (
            <>
              <div
                style={{
                  flex: '0 0 auto',
                  display: 'flex',
                  alignItems: 'flex-end',
                  paddingBottom: 8,
                }}
              >
                <label className={styles.checkboxLabel}>
                  <input type="checkbox" checked={hasInvoice} disabled readOnly />
                  WZ z fakturą{' '}
                  <span style={{ fontSize: '0.7rem', color: 'var(--color-text-secondary)' }}>
                    (TODO)
                  </span>
                </label>
              </div>

              {!hasInvoice && (
                <div style={{ flex: '2 1 200px' }}>
                  <label className={styles.fieldLabel}>Powód wydania *</label>
                  <input
                    className="input"
                    value={issueReason}
                    onChange={(e) => setIssueReason(e.target.value)}
                    placeholder="Podarunek, gratis, próbka…"
                  />
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Pozycje */}
      <div className={styles.card}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 10,
          }}
        >
          <span className={styles.sectionTitle}>Pozycje</span>
          <button className="btn btn-secondary" type="button" onClick={addRow}>
            + Dodaj pozycję
          </button>
        </div>

        <table
          className={`${styles.catalogTable}${
            docType === 'PZ'
              ? ` ${styles.pzItemsTable}`
              : docType === 'KK'
                ? ` ${styles.kkItemsTable}`
                : ''
          }`}
        >
          {docType === 'PZ' && (
            <colgroup>
              <col className={styles.colPzProduct} />
              <col className={styles.colPzIsbn} />
              <col className={styles.colPzQty} />
              <col className={styles.colPzPurchase} />
              <col className={styles.colPzVat} />
              <col className={styles.colPzGross} />
              <col className={styles.colPzActions} />
            </colgroup>
          )}
          {docType === 'KK' && (
            <colgroup>
              <col className={styles.colKkProduct} />
              <col className={styles.colKkIsbn} />
              <col className={styles.colKkQty} />
              <col className={styles.colKkPurchase} />
              <col className={styles.colKkActions} />
            </colgroup>
          )}
          <thead>
            <tr>
              <th>Towar</th>
              <th>ISBN</th>
              {docType === 'PZ' ? (
                <>
                  <th className={styles.right}>ILOŚĆ</th>
                  <th className={styles.right}>CENA ZAKUPU (NETTO)</th>
                  <th className={styles.right}>STAWKA VAT</th>
                  <th className={styles.right}>NORMATYWNA CENA SPRZEDAŻY BRUTTO</th>
                </>
              ) : docType === 'KK' ? (
                <>
                  <th className={styles.right}>Ilość</th>
                  <th className={styles.right}>Cena zakupu</th>
                </>
              ) : (
                <>
                  <th className={styles.right}>Ilość</th>
                  <th className={styles.right}>Cena suger.</th>
                </>
              )}
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((row) => {
              const ci = catalogMap[row.item_id];
              return (
                <tr key={row._key}>
                  <td>
                    <select
                      className="input"
                      style={{ minWidth: 160 }}
                      value={row.item_id}
                      onChange={(e) => selectItem(row._key, e.target.value)}
                    >
                      <option value="">— wybierz —</option>
                      {warehouseItems.map((ci) => (
                        <option key={ci.id} value={ci.id}>
                          {ci.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td
                    style={{
                      color: 'var(--color-text-secondary)',
                      fontSize: '0.8rem',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {ci?.isbn ?? '—'}
                  </td>
                  <td className={docType === 'PZ' ? styles.numCell : docType === 'KK' ? styles.numCell : styles.right}>
                    <input
                      className={docType === 'PZ' || docType === 'KK' ? `${styles.numInput} input` : 'input'}
                      style={docType === 'PZ' || docType === 'KK' ? undefined : { width: 80, textAlign: 'right' }}
                      type="number"
                      step="1"
                      min={docType === 'KK' ? undefined : '1'}
                      value={row.quantity}
                      onChange={(e) =>
                        setField(
                          row._key,
                          'quantity',
                          sanitizeIntegerQty(e.target.value, docType === 'KK')
                        )
                      }
                      placeholder="0"
                    />
                    {docType === 'KK' && kkQuantityDirectionHint(row.quantity) && (
                      <div
                        style={{
                          fontSize: '0.72rem',
                          color: 'var(--color-text-secondary)',
                          marginTop: 4,
                          lineHeight: 1.3,
                        }}
                      >
                        {kkQuantityDirectionHint(row.quantity)}
                      </div>
                    )}
                  </td>
                  {docType === 'PZ' ? (
                    <>
                      <td className={styles.numCell}>
                        <input
                          className={`${styles.numInput} input`}
                          type="number"
                          step="0.01"
                          min="0"
                          value={row.purchase_unit_price}
                          onChange={(e) =>
                            setField(row._key, 'purchase_unit_price', e.target.value)
                          }
                          placeholder="0,00"
                        />
                      </td>
                      <td className={styles.numCell}>
                        <select
                          className={`${styles.numInput} input`}
                          value={row.vat_rate}
                          onChange={(e) => setField(row._key, 'vat_rate', e.target.value)}
                        >
                          <option value="">—</option>
                          {VAT_OPTIONS.map((v) => (
                            <option key={v} value={v}>
                              {v}%
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className={styles.numCell}>
                        <input
                          className={`${styles.numInput} input`}
                          type="number"
                          step="0.01"
                          min="0"
                          value={row.suggested_sale_price}
                          onChange={(e) =>
                            setField(row._key, 'suggested_sale_price', e.target.value)
                          }
                          placeholder="0,00"
                        />
                      </td>
                    </>
                  ) : docType === 'KK' ? (
                    <td className={styles.numCell}>
                      {needsPurchasePrice(row) ? (
                        <input
                          className={`${styles.numInput} input`}
                          type="number"
                          step="0.01"
                          min="0"
                          value={row.purchase_unit_price}
                          onChange={(e) =>
                            setField(row._key, 'purchase_unit_price', e.target.value)
                          }
                          placeholder="0,00"
                        />
                      ) : (
                        <span
                          style={{
                            color: 'var(--color-text-secondary)',
                            fontSize: '0.8rem',
                          }}
                        >
                          n/d
                        </span>
                      )}
                    </td>
                  ) : (
                    <td className={styles.right}>
                      <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.85rem' }}>
                        {ci?.suggested_sale_price != null
                          ? `${fmtMoney2(ci.suggested_sale_price)} zł`
                          : '—'}
                      </span>
                    </td>
                  )}
                  <td>
                    <button
                      className="btn btn-ghost"
                      type="button"
                      onClick={() => removeRow(row._key)}
                      title="Usuń pozycję"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {error && (
        <p style={{ color: 'var(--color-error)', marginTop: 8, fontSize: '0.9rem' }}>{error}</p>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={busy}>
          {busy ? 'Zapisywanie…' : isEdit ? 'Zapisz zmiany' : 'Zapisz draft'}
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>
          Anuluj
        </button>
      </div>
    </div>
  );
}

// ── DocDetail ─────────────────────────────────────────────────────────────────

function DocDetail({ docId, onBack, onChanged, onEdit }) {
  const [doc, setDoc] = useState(null);
  const [itemById, setItemById] = useState({});
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([
      warehouseDocumentsApi.getById(docId),
      warehouseItemsApi.list().catch(() => ({ items: [] })),
    ])
      .then(([d, catalog]) => {
        setDoc(d);
        const allItems = catalog.items ?? catalog ?? [];
        setItemById(Object.fromEntries(allItems.map((ci) => [ci.id, ci])));
      })
      .catch(() => setError('Błąd ładowania dokumentu'))
      .finally(() => setLoading(false));
  }, [docId]);

  const handlePost = async () => {
    if (doc.doc_type === 'PZ') {
      for (let i = 0; i < doc.items.length; i++) {
        const it = doc.items[i];
        const price = Number(it.purchase_unit_price);
        if (it.purchase_unit_price == null || it.purchase_unit_price === '' || isNaN(price) || price < 0) {
          setError(`Pozycja ${i + 1}: cena zakupu wymagana do zaksięgowania PZ.`);
          return;
        }
      }
    }
    setPosting(true);
    setError('');
    try {
      const updated = await warehouseDocumentsApi.post(docId);
      setDoc(updated);
      onChanged?.();
    } catch (err) {
      setError(apiErr(err));
    } finally {
      setPosting(false);
    }
  };

  if (loading) return <p className={styles.emptyMsg}>Ładowanie…</p>;
  if (error && !doc)
    return <p style={{ color: 'var(--color-error)', padding: 16 }}>{error}</p>;
  if (!doc) return null;

  const isDraft = doc.status === 'draft';
  const isPosted = doc.status === 'posted';
  const reason = doc.correction_reason || doc.issue_reason || doc.notes;
  const reasonLabel =
    doc.doc_type === 'WZ' && doc.issue_reason
      ? 'Powód wydania'
      : doc.doc_type === 'KK' && doc.correction_reason
        ? 'Powód korekty'
        : 'Opis / Powód';
  const itemColSpan = detailItemColSpan(doc.doc_type);

  const fifoSectionTitle = (docType) =>
    docType === 'WZ' ? 'Zdjęcie z warstw FIFO' : 'Korekta — zdjęcie z warstw FIFO';

  const handleCancel = async () => {
    if (!window.confirm('Usunąć (anulować) ten draft? Operacji nie można cofnąć.')) return;
    setCancelling(true);
    setError('');
    try {
      await warehouseDocumentsApi.cancel(docId);
      onChanged?.();
      onBack();
    } catch (err) {
      setError(apiErr(err));
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div>
      <div className={styles.catalogToolbar}>
        <span className={styles.sectionTitle}>
          {doc.number ? doc.number : '(draft)'} — {doc.doc_type}
        </span>
        <button className="btn btn-secondary" onClick={onBack}>
          ← Lista
        </button>
      </div>

      {/* Nagłówek */}
      <div className={styles.card}>
        <div className={styles.formRowMain} style={{ gap: 24 }}>
          <div>
            <div className={styles.fieldLabel}>Typ</div>
            <strong>{doc.doc_type}</strong>
          </div>
          <div>
            <div className={styles.fieldLabel}>Status</div>
            <StatusBadge status={doc.status} />
          </div>
          <div>
            <div className={styles.fieldLabel}>Data utworzenia</div>
            <span>{fmtDate(doc.created_at)}</span>
          </div>
          {doc.posted_at && (
            <div>
              <div className={styles.fieldLabel}>Zaksięgowano</div>
              <span>{fmtDate(doc.posted_at)}</span>
            </div>
          )}
          {reason && (
            <div style={{ flex: '1 1 200px' }}>
              <div className={styles.fieldLabel}>{reasonLabel}</div>
              <span>{reason}</span>
            </div>
          )}
        </div>
      </div>

      {/* Pozycje */}
      <div className={styles.card}>
        <div className={styles.sectionTitle} style={{ marginBottom: 10 }}>
          Pozycje ({doc.items?.length ?? 0})
        </div>
        <table
          className={`${styles.catalogTable}${
            doc.doc_type === 'PZ'
              ? ` ${styles.pzItemsTable}`
              : doc.doc_type === 'WZ'
                ? ` ${styles.wzItemsTable}`
                : doc.doc_type === 'KK'
                  ? ` ${styles.kkItemsTable}`
                  : ''
          }`}
        >
          {doc.doc_type === 'PZ' && (
            <colgroup>
              <col className={styles.colPzProduct} />
              <col className={styles.colPzQty} />
              <col className={styles.colPzPurchase} />
              <col className={styles.colPzVat} />
              <col className={styles.colPzGross} />
            </colgroup>
          )}
          {doc.doc_type === 'WZ' && (
            <colgroup>
              <col className={styles.colWzProduct} />
              <col className={styles.colWzQty} />
              <col className={styles.colWzGross} />
            </colgroup>
          )}
          {doc.doc_type === 'KK' && (
            <colgroup>
              <col className={styles.colKkProduct} />
              <col className={styles.colKkQty} />
              <col className={styles.colKkPurchase} />
            </colgroup>
          )}
          <thead>
            <tr>
              <th>Towar</th>
              {doc.doc_type === 'PZ' ? (
                <>
                  <th className={styles.right}>ILOŚĆ</th>
                  <th className={styles.right}>CENA ZAKUPU (NETTO)</th>
                  <th className={styles.right}>STAWKA VAT</th>
                  <th className={styles.right}>NORMATYWNA CENA SPRZEDAŻY BRUTTO</th>
                </>
              ) : doc.doc_type === 'WZ' ? (
                <>
                  <th className={styles.right}>ILOŚĆ</th>
                  <th className={styles.right}>CENA SPRZEDAŻY BRUTTO</th>
                </>
              ) : doc.doc_type === 'KK' ? (
                <>
                  <th className={styles.right}>ILOŚĆ</th>
                  <th className={styles.right}>CENA ZAKUPU</th>
                </>
              ) : (
                <>
                  <th className={styles.right}>Ilość</th>
                  <th className={styles.right}>Cena zakupu</th>
                  <th className={styles.right}>Cena sprzedaży</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {doc.items?.map((it) => {
              const ci = itemById[it.item_id];
              const shortId = String(it.item_id).slice(0, 8) + '…';
              const qty = Number(it.quantity);
              const isPositiveKkPosted = isPosted && doc.doc_type === 'KK' && qty > 0;
              const showFifoMovements =
                isPosted &&
                (doc.doc_type === 'WZ' || (doc.doc_type === 'KK' && qty < 0)) &&
                it.fifo_movements?.length > 0;
              return (
                <Fragment key={it.id}>
                  <tr>
                    <td>
                      {ci ? (
                        <>
                          <span>{ci.name}</span>
                          {ci.isbn && (
                            <div
                              style={{
                                fontSize: '0.75rem',
                                color: 'var(--color-text-secondary)',
                                marginTop: 2,
                              }}
                            >
                              ISBN: {ci.isbn}
                            </div>
                          )}
                        </>
                      ) : (
                        <span
                          style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}
                          title={it.item_id}
                        >
                          {shortId}
                        </span>
                      )}
                    </td>
                    <td className={styles.numCell}>{fmtIntegerQty(it.quantity)}</td>
                    {doc.doc_type === 'PZ' ? (
                      <>
                        <td className={styles.numCell}>{fmtMoney2(it.purchase_unit_price)}</td>
                        <td className={styles.numCell}>
                          {fmtVatRate(it.vat_rate ?? ci?.vat_rate)}
                        </td>
                        <td className={styles.numCell}>{fmtMoney2(it.suggested_sale_price)}</td>
                      </>
                    ) : doc.doc_type === 'WZ' ? (
                      <td className={styles.numCell}>{wzSalePriceGross(it, ci)}</td>
                    ) : doc.doc_type === 'KK' ? (
                      <td className={styles.numCell}>{fmtMoney2(it.purchase_unit_price)}</td>
                    ) : (
                      <>
                        <td className={styles.right}>{it.purchase_unit_price ?? '—'}</td>
                        <td className={styles.right}>{it.unit_price_net ?? '—'}</td>
                      </>
                    )}
                  </tr>
                  {showFifoMovements && (
                    <tr>
                      <td
                        colSpan={itemColSpan}
                        style={{ padding: '4px 8px 10px', background: 'var(--color-bg-subtle, #f8f9fa)' }}
                      >
                        <div
                          style={{
                            fontSize: '0.78rem',
                            color: 'var(--color-text-secondary)',
                            fontWeight: 600,
                            marginBottom: 4,
                          }}
                        >
                          {fifoSectionTitle(doc.doc_type)}
                        </div>
                        {it.fifo_movements.map((mv, idx) => (
                          <div
                            key={idx}
                            style={{
                              fontSize: '0.78rem',
                              color: 'var(--color-text-secondary)',
                              marginBottom: idx < it.fifo_movements.length - 1 ? 4 : 0,
                            }}
                          >
                            Dokument źródłowy:{' '}
                            <span style={{ color: 'var(--color-text-primary)' }}>
                              {mv.source_document_number ?? '—'}
                            </span>
                            {' · '}
                            Data dokumentu:{' '}
                            <span style={{ color: 'var(--color-text-primary)' }}>
                              {mv.source_document_date ? fmtDate(mv.source_document_date) : '—'}
                            </span>
                            {' · '}
                            Ilość zdjęta:{' '}
                            <span style={{ color: 'var(--color-text-primary)' }}>{mv.quantity_consumed}</span>
                            {' · '}
                            Cena netto warstwy:{' '}
                            <span style={{ color: 'var(--color-text-primary)' }}>
                              {mv.unit_price_net} zł
                            </span>
                          </div>
                        ))}
                      </td>
                    </tr>
                  )}
                  {isPositiveKkPosted && (
                    <tr>
                      <td
                        colSpan={itemColSpan}
                        style={{ padding: '4px 8px 10px', background: 'var(--color-bg-subtle, #f8f9fa)' }}
                      >
                        <div style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                          Korekta dodatnia tworzy nową warstwę magazynową.
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {error && (
        <p style={{ color: 'var(--color-error)', marginTop: 8, fontSize: '0.9rem' }}>{error}</p>
      )}

      {isDraft && (
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn btn-primary" onClick={handlePost} disabled={posting || cancelling}>
            {posting ? 'Księgowanie…' : '✓ Zaksięguj'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => onEdit?.(doc)}
            disabled={posting || cancelling}
          >
            Edytuj
          </button>
          <button
            className="btn btn-ghost"
            style={{ color: 'var(--color-error)' }}
            onClick={handleCancel}
            disabled={posting || cancelling}
          >
            {cancelling ? 'Usuwanie…' : 'Usuń draft'}
          </button>
        </div>
      )}
    </div>
  );
}

// ── DocumentsTab — zarządza widokiem list/form/detail ─────────────────────────

export default function DocumentsTab() {
  const [view, setView] = useState({ type: 'list' });
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <>
      {view.type === 'list' && (
        <DocList
          onNew={() => setView({ type: 'form' })}
          onOpen={(id) => setView({ type: 'detail', id })}
          refreshKey={refreshKey}
        />
      )}
      {view.type === 'form' && (
        <DocForm
          onSaved={(id) => setView({ type: 'detail', id })}
          onCancel={() => setView({ type: 'list' })}
        />
      )}
      {view.type === 'edit' && (
        <DocForm
          initial={view.doc}
          onSaved={(id) => { setRefreshKey((k) => k + 1); setView({ type: 'detail', id }); }}
          onCancel={() => setView({ type: 'detail', id: view.doc.id })}
        />
      )}
      {view.type === 'detail' && (
        <DocDetail
          docId={view.id}
          onBack={() => setView({ type: 'list' })}
          onChanged={() => setRefreshKey((k) => k + 1)}
          onEdit={(doc) => setView({ type: 'edit', doc })}
        />
      )}
    </>
  );
}
