import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { contractorsApi } from '../../api/contractors';
import { warehouseItemsApi } from '../../api/warehouseItems';
import styles from './InvoiceForm.module.css';

const TODAY = new Date().toISOString().split('T')[0];

const DUE_DATE_PRESET_DAYS = [3, 7, 14, 21, 30, 59];
const MAX_DUE_DAYS = 59;
const DEFAULT_DUE_PRESET = 14;

const PAYMENT_METHODS = [
  { value: 'transfer', label: 'Przelew' },
  { value: 'cash', label: 'Gotówka' },
];

function addDays(isoDate, days) {
  const d = new Date(`${isoDate}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
}

function daysBetween(startIso, endIso) {
  const start = new Date(`${startIso}T12:00:00`);
  const end = new Date(`${endIso}T12:00:00`);
  return Math.round((end - start) / 86400000);
}

function maxDueDate(issueDate) {
  return addDays(issueDate, MAX_DUE_DAYS);
}

function inferDueDateState(issueDate, dueDate) {
  if (!dueDate) {
    return {
      mode: 'preset',
      preset: DEFAULT_DUE_PRESET,
      custom: addDays(issueDate, DEFAULT_DUE_PRESET),
    };
  }
  const diffDays = daysBetween(issueDate, dueDate);
  if (DUE_DATE_PRESET_DAYS.includes(diffDays)) {
    return { mode: 'preset', preset: diffDays, custom: dueDate };
  }
  return { mode: 'custom', preset: DEFAULT_DUE_PRESET, custom: dueDate };
}

function validateDueDate(issueDate, dueDate) {
  if (!dueDate) return 'Termin płatności jest wymagany';
  if (dueDate < issueDate) {
    return 'Termin płatności nie może być wcześniejszy niż data wystawienia';
  }
  if (dueDate > maxDueDate(issueDate)) {
    return `Termin płatności nie może być późniejszy niż ${MAX_DUE_DAYS} dni od daty wystawienia`;
  }
  return '';
}

function sanitizeAmountInput(value) {
  const normalized = String(value ?? '').replace(',', '.').replace(/[^\d.]/g, '');
  const parts = normalized.split('.');
  if (parts.length <= 1) return normalized;
  return `${parts[0]}.${parts.slice(1).join('').slice(0, 2)}`;
}

function parseAmountInput(value) {
  const trimmed = String(value ?? '').trim();
  if (!trimmed) return null;
  const num = Number(trimmed.replace(',', '.'));
  return Number.isFinite(num) ? num : NaN;
}

function inferPaidAmountFromInvoice(invoice) {
  if (!invoice) return null;
  if (invoice.form_paid_amount != null && invoice.form_paid_amount !== '') {
    const formPaid = Number(invoice.form_paid_amount);
    if (Number.isFinite(formPaid)) return Math.max(0, formPaid);
  }
  return null;
}

function formatPaidAmountInput(value) {
  if (value == null || value <= 0) return '';
  return value.toFixed(2);
}

const EMPTY_ITEM = { name: '', isbn: '', quantity: '1', unit: 'szt.', unit_price_net: '', vat_rate: '23' };
const INVOICE_CURRENCY = 'PLN';

// ISBN format: 123-45-678912-3-4
function formatIsbn(raw) {
  const digits = raw.replace(/\D/g, '').slice(0, 13);
  if (!digits) return '';
  let r = digits.slice(0, 3);
  if (digits.length > 3) r += '-' + digits.slice(3, 5);
  if (digits.length > 5) r += '-' + digits.slice(5, 11);
  if (digits.length > 11) r += '-' + digits.slice(11, 12);
  if (digits.length > 12) r += '-' + digits.slice(12, 13);
  return r;
}

const VAT_RATES = ['0', '5', '8', '23', 'zw'];

/** Mapuje wartość z API (np. "23.00") na wartość opcji w <select>. */
function normalizeVatRateForSelect(value) {
  if (value === 'zw' || value === 'np') return value;
  const text = String(value ?? '').trim();
  if (!text) return '23';
  const n = Number.parseFloat(text.replace(',', '.'));
  if (!Number.isFinite(n)) return '23';
  if (n <= 0.5) return '0';
  if (n >= 22.5 && n <= 23.5) return '23';
  if (n >= 7.5 && n <= 8.5) return '8';
  if (n >= 4.5 && n <= 5.5) return '5';
  const rounded = String(Math.round(n));
  return VAT_RATES.includes(rounded) ? rounded : '23';
}

function parseVatRatePercent(value) {
  if (value === 'zw' || value === 'np') return 0;
  const n = Number.parseFloat(String(value ?? '').replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

const ITEM_TYPE_LABELS = { goods: 'Towar', service: 'Usługa' };

function filterCatalogItems(catalogItems, query) {
  const q = query.trim().toLowerCase();
  const sorted = [...catalogItems].sort((a, b) => a.name.localeCompare(b.name, 'pl'));
  if (!q) return sorted.slice(0, 12);
  return sorted
    .filter((item) => {
      const name = item.name.toLowerCase();
      const isbn = (item.isbn ?? '').toLowerCase();
      return name.includes(q) || isbn.includes(q);
    })
    .slice(0, 12);
}

function catalogItemToLineFields(catalogItem) {
  const price = catalogItem.suggested_sale_price ?? catalogItem.default_price_net;
  const fields = {
    name: catalogItem.name,
    isbn: catalogItem.isbn ?? '',
    unit: catalogItem.unit || 'szt.',
    unit_price_net: price != null ? String(price) : '',
  };
  if (catalogItem.vat_rate != null) {
    fields.vat_rate = normalizeVatRateForSelect(catalogItem.vat_rate);
  }
  return fields;
}

function useWarehouseCatalog() {
  const [catalogItems, setCatalogItems] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    setCatalogError('');

    warehouseItemsApi
      .list()
      .then((data) => {
        if (!cancelled) setCatalogItems(data.items ?? []);
      })
      .catch(() => {
        if (!cancelled) {
          setCatalogItems([]);
          setCatalogError('Nie udało się pobrać katalogu magazynu — wpisz nazwę ręcznie');
        }
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  return { catalogItems, catalogLoading, catalogError };
}

function ItemNameCombobox({
  value,
  onNameChange,
  onSelectCatalog,
  catalogItems,
  catalogLoading,
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapRef = useRef(null);
  const suggestions = useMemo(
    () => filterCatalogItems(catalogItems, value),
    [catalogItems, value],
  );

  const pickSuggestion = useCallback((item) => {
    onSelectCatalog(item);
    setOpen(false);
    setActiveIndex(-1);
  }, [onSelectCatalog]);

  const handleKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true);
      return;
    }
    if (!open || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      pickSuggestion(suggestions[activeIndex]);
    } else if (e.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  useEffect(() => {
    setActiveIndex(-1);
  }, [value, suggestions.length]);

  return (
    <div className={styles.nameCombobox} ref={wrapRef}>
      <input
        className="input"
        placeholder={catalogLoading ? 'Ładowanie katalogu…' : 'Wybierz z magazynu lub wpisz nazwę'}
        value={value}
        onChange={(e) => {
          onNameChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 150);
        }}
        onKeyDown={handleKeyDown}
        autoComplete="off"
        required
      />
      {open && suggestions.length > 0 && (
        <ul className={styles.nameSuggestions} role="listbox">
          {suggestions.map((item, idx) => (
            <li key={item.id} role="option" aria-selected={idx === activeIndex}>
              <button
                type="button"
                className={`${styles.nameSuggestionBtn} ${idx === activeIndex ? styles.nameSuggestionBtnActive : ''}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pickSuggestion(item);
                }}
              >
                <span className={styles.nameSuggestionTitle}>{item.name}</span>
                <span className={styles.nameSuggestionMeta}>
                  <span className={styles.nameSuggestionType}>
                    {ITEM_TYPE_LABELS[item.item_type] ?? item.item_type}
                  </span>
                  {item.isbn ? <span>{item.isbn}</span> : null}
                  {item.unit ? <span>{item.unit}</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function useDebounce(value, delay) {
  const [dv, setDv] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDv(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return dv;
}

function sanitizeQuantityInput(value) {
  const digits = String(value ?? '').replace(/\D/g, '');
  if (!digits) return '';
  return String(Math.min(999999, Number.parseInt(digits, 10)));
}

function parseQuantity(value) {
  const n = Number.parseInt(String(value ?? '').trim(), 10);
  return Number.isFinite(n) && n > 0 ? n : NaN;
}

function normalizeInitialItems(initialItems) {
  if (!initialItems?.length) {
    return [{ ...EMPTY_ITEM }];
  }
  return initialItems.map((i) => ({
    name: i.name,
    isbn: i.isbn ?? '',
    quantity: String(Math.max(1, Math.round(Number(i.quantity)) || 1)),
    unit: i.unit,
    unit_price_net: String(i.unit_price_net),
    vat_rate: normalizeVatRateForSelect(i.vat_rate),
  }));
}

function calcNet(it) {
  const q = parseFloat(it.quantity) || 0;
  const p = parseFloat(it.unit_price_net) || 0;
  return (q * p).toFixed(2);
}

function calcLineAmounts(it) {
  const net = parseFloat(calcNet(it)) || 0;
  const rate = parseVatRatePercent(it.vat_rate);
  const vat = (net * rate) / 100;
  return {
    net: net.toFixed(2),
    vat: vat.toFixed(2),
    gross: (net + vat).toFixed(2),
  };
}

function useBuyerLookup(initialBuyerNip) {
  const [buyerNip, setBuyerNip] = useState(initialBuyerNip ?? '');
  const [buyerInfo, setBuyerInfo] = useState(null);
  const [nipError, setNipError] = useState('');
  const debouncedNip = useDebounce(buyerNip, 600);

  useEffect(() => {
    const nip = String(initialBuyerNip ?? '').trim();
    if (nip.length !== 10) return undefined;

    let cancelled = false;
    contractorsApi.getByNip(nip)
      .then((contractor) => {
        if (!cancelled) setBuyerInfo(contractor);
      })
      .catch(() => {});

    return () => { cancelled = true; };
  }, [initialBuyerNip]);

  useEffect(() => {
    if (debouncedNip.length !== 10) {
      setBuyerInfo(null);
      return;
    }

    let cancelled = false;
    setNipError('');

    const lookup = async () => {
      // Próba 1: kontrahent w lokalnej bazie
      try {
        const c = await contractorsApi.getByNip(debouncedNip);
        if (!cancelled) setBuyerInfo(c);
        return;
      } catch (err) {
        if (cancelled) return;
        // Tylko przy 404 próbujemy REGON; inne błędy od razu jako błąd
        if (err.response?.status && err.response.status !== 404) {
          setBuyerInfo(null);
          setNipError('Błąd pobierania danych — spróbuj ponownie');
          return;
        }
      }

      // Próba 2: odśwież z REGON (refresh sam zwraca dane kontrahenta)
      try {
        const c = await contractorsApi.refresh(debouncedNip);
        if (!cancelled) setBuyerInfo(c);
      } catch {
        if (!cancelled) {
          setBuyerInfo(null);
          setNipError('Nie znaleziono kontrahenta — sprawdź NIP lub dodaj kontrahenta ręcznie');
        }
      }
    };

    lookup();
    return () => { cancelled = true; };
  }, [debouncedNip]);

  return {
    buyerNip,
    setBuyerNip,
    buyerInfo,
    nipError,
  };
}

function useInvoiceItems(initialItems, invoiceId) {
  const [items, setItems] = useState(() => normalizeInitialItems(initialItems));

  useEffect(() => {
    setItems(normalizeInitialItems(initialItems));
  }, [invoiceId]);

  const addItem = () => setItems((prev) => [...prev, { ...EMPTY_ITEM }]);
  const removeItem = (idx) => setItems((prev) => prev.filter((_, i) => i !== idx));
  const updateItem = (idx, field, val) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: val } : it)));
  };
  const updateItemFields = (idx, fields) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...fields } : it)));
  };
  const applyCatalogItem = (idx, catalogItem) => {
    updateItemFields(idx, catalogItemToLineFields(catalogItem));
  };

  const totals = useMemo(() => {
    const totalNet = items.reduce((sum, item) => sum + parseFloat(calcNet(item)), 0);
    const totalVat = items.reduce((sum, item) => {
      const net = parseFloat(calcNet(item));
      const rate = parseVatRatePercent(item.vat_rate);
      return sum + (net * rate) / 100;
    }, 0);
    return { totalNet, totalVat, totalGross: totalNet + totalVat };
  }, [items]);

  return {
    items,
    addItem,
    removeItem,
    updateItem,
    applyCatalogItem,
    totals,
  };
}

function mapItemsToPayload(items) {
  return items.map((it) => ({
    name: it.name,
    isbn: it.isbn || null,
    quantity: parseQuantity(it.quantity),
    unit: it.unit || 'szt.',
    unit_price_net: parseFloat(it.unit_price_net),
    vat_rate: parseVatRatePercent(it.vat_rate),
  }));
}

function BuyerFields({ buyerNip, setBuyerNip, nipError, buyerInfo }) {
  return (
    <>
      <div className={`form-group ${styles.compactField}`}>
        <label className="form-label">NIP nabywcy *</label>
        <input
          className="input"
          type="text"
          placeholder="10 cyfr"
          maxLength={10}
          value={buyerNip}
          onChange={(e) => setBuyerNip(e.target.value.replace(/\D/g, ''))}
        />
        {nipError && <span className="form-error">{nipError}</span>}
      </div>
      <div className={`form-group ${styles.compactField}`}>
        <label className="form-label">Nabywca</label>
        <input
          className="input"
          type="text"
          readOnly
          value={buyerInfo ? `${buyerInfo.name} (${buyerInfo.city})` : ''}
          placeholder={buyerNip.length === 10 ? 'Pobieranie...' : '—'}
        />
      </div>
    </>
  );
}

function DateFields({ issueDate, saleDate, setIssueDate, setSaleDate }) {
  return (
    <>
      <div className={`form-group ${styles.compactField}`}>
        <label className="form-label">Data wystawienia *</label>
        <input
          type="date"
          className="input"
          value={issueDate}
          onChange={(e) => setIssueDate(e.target.value)}
          required
        />
      </div>
      <div className={`form-group ${styles.compactField}`}>
        <label className="form-label">Data sprzedaży *</label>
        <input
          type="date"
          className="input"
          value={saleDate}
          onChange={(e) => setSaleDate(e.target.value)}
          required
        />
      </div>
    </>
  );
}

function InvoiceHeaderSection(props) {
  return (
    <div className={styles.block}>
      <h3 className={styles.blockTitle}>Dane faktury</h3>
      <div className={styles.headerGrid}>
        <div className={styles.headerRow}>
          <DateFields {...props} />
        </div>
        <div className={`${styles.headerRow} ${styles.headerRowBuyer}`}>
          <BuyerFields {...props} />
        </div>
      </div>
    </div>
  );
}

function PaymentSection({
  paymentMethod,
  setPaymentMethod,
  dueDateMode,
  setDueDateMode,
  dueDatePreset,
  setDueDatePreset,
  dueDateCustom,
  setDueDateCustom,
  dueDateSet,
  setDueDateSet,
  issueDate,
  dueDateError,
  paymentMethodError,
  amountPaid,
  setAmountPaid,
  amountPaidError,
  totalGross,
}) {
  const resolvedDueDate = dueDateSet
    ? (dueDateMode === 'preset' ? addDays(issueDate, dueDatePreset) : dueDateCustom)
    : '';
  const parsedAmountPaid = parseAmountInput(amountPaid);
  const remainingAfterPayment = parsedAmountPaid != null && parsedAmountPaid >= 0
    ? Math.max(0, totalGross - parsedAmountPaid)
    : totalGross;

  return (
    <div className={styles.block}>
      <div className={styles.paymentGrid}>
        <div className={styles.paymentMethodColumn}>
          <div className={`form-group ${styles.compactField}`}>
            <label className="form-label">Sposób płatności *</label>
            <div className={styles.radioGroup}>
              {PAYMENT_METHODS.map(({ value, label }) => (
                <label key={value} className={styles.radioOption}>
                  <input
                    type="radio"
                    name="payment_method"
                    value={value}
                    checked={paymentMethod === value}
                    onChange={() => setPaymentMethod(value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            {paymentMethodError && <span className="form-error">{paymentMethodError}</span>}
          </div>
          <div className={`form-group ${styles.compactField} ${styles.amountPaidField}`}>
            <label className="form-label" htmlFor="amount_paid">Wpłacono</label>
            <div className={styles.amountPaidRow}>
              <input
                id="amount_paid"
                type="text"
                inputMode="decimal"
                className="input"
                value={amountPaid}
                onChange={(e) => setAmountPaid(sanitizeAmountInput(e.target.value))}
                placeholder="0,00"
              />
              <span className={styles.amountPaidCurrency}>{INVOICE_CURRENCY}</span>
            </div>
            <span className={styles.amountPaidHint}>
              Pozostanie: {remainingAfterPayment.toFixed(2)} {INVOICE_CURRENCY}
            </span>
            {amountPaidError && <span className="form-error">{amountPaidError}</span>}
          </div>
        </div>
        <div className={`form-group ${styles.compactField}`}>
          <label className="form-label">
            Termin płatności *
            <span className={styles.dueDateInline}>
              → {resolvedDueDate || '—'}
            </span>
          </label>
          <div className={styles.presetRow}>
            {DUE_DATE_PRESET_DAYS.map((days) => (
              <button
                key={days}
                type="button"
                className={`${styles.presetBtn} ${dueDateSet && dueDateMode === 'preset' && dueDatePreset === days ? styles.presetBtnActive : ''}`}
                onClick={() => {
                  setDueDateSet(true);
                  setDueDateMode('preset');
                  setDueDatePreset(days);
                  setDueDateCustom(addDays(issueDate, days));
                }}
              >
                {days}d
              </button>
            ))}
            <button
              type="button"
              className={`${styles.presetBtn} ${dueDateSet && dueDateMode === 'custom' ? styles.presetBtnActive : ''}`}
              onClick={() => {
                setDueDateSet(true);
                setDueDateMode('custom');
                if (!dueDateCustom || dueDateCustom < issueDate) {
                  setDueDateCustom(addDays(issueDate, DEFAULT_DUE_PRESET));
                }
              }}
            >
              Inna
            </button>
            {dueDateSet && dueDateMode === 'custom' && (
              <input
                type="date"
                className={`input ${styles.customDueInput}`}
                value={dueDateCustom}
                min={issueDate}
                max={maxDueDate(issueDate)}
                onChange={(e) => {
                  setDueDateSet(true);
                  setDueDateCustom(e.target.value);
                }}
                required
              />
            )}
          </div>
          {dueDateError && <span className="form-error">{dueDateError}</span>}
        </div>
      </div>
    </div>
  );
}

function ItemsSection({
  items,
  addItem,
  removeItem,
  updateItem,
  applyCatalogItem,
  catalogItems,
  catalogLoading,
  catalogError,
}) {
  return (
    <div className={styles.block}>
      <div className={styles.blockHeader}>
        <h3 className={styles.blockTitle}>Pozycje faktury</h3>
        <button type="button" className={`btn btn-sm ${styles.addItemBtn}`} onClick={addItem}>
          + Dodaj pozycję
        </button>
      </div>
      {catalogError && (
        <div className={`alert alert-warning ${styles.catalogAlert}`}>{catalogError}</div>
      )}

      <div className={styles.itemsHeader}>
        <span>Nazwa</span>
        <span>Ilość</span>
        <span>J.m.</span>
        <span>Cena netto</span>
        <span>VAT %</span>
        <span>Kwota netto</span>
        <span>Kwota VAT</span>
        <span>Kwota brutto</span>
        <span></span>
      </div>

      {items.map((it, idx) => {
        const amounts = calcLineAmounts(it);
        return (
        <div key={idx} className={styles.itemRow}>
          <div className={styles.itemNameCell}>
            <ItemNameCombobox
              value={it.name}
              onNameChange={(val) => updateItem(idx, 'name', val)}
              onSelectCatalog={(catalogItem) => applyCatalogItem(idx, catalogItem)}
              catalogItems={catalogItems}
              catalogLoading={catalogLoading}
            />
            <input
              className={`input ${styles.isbnSubInput}`}
              placeholder="ISBN (opcjonalnie)"
              value={it.isbn}
              maxLength={17}
              onChange={(e) => updateItem(idx, 'isbn', formatIsbn(e.target.value))}
            />
          </div>
          <input
            className={`input ${styles.itemInputCompact}`}
            type="number"
            min="1"
            step="1"
            inputMode="numeric"
            pattern="[0-9]*"
            value={it.quantity}
            onChange={(e) => updateItem(idx, 'quantity', sanitizeQuantityInput(e.target.value))}
            required
          />
          <input
            className={`input ${styles.itemInputCompact}`}
            placeholder="szt."
            value={it.unit}
            onChange={(e) => updateItem(idx, 'unit', e.target.value)}
          />
          <input
            className={`input ${styles.itemInputCompact}`}
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
            value={it.unit_price_net}
            onChange={(e) => updateItem(idx, 'unit_price_net', e.target.value)}
            required
          />
          <select
            className={`select ${styles.itemInputCompact}`}
            value={it.vat_rate}
            onChange={(e) => updateItem(idx, 'vat_rate', e.target.value)}
          >
            {VAT_RATES.map((r) => (
              <option key={r} value={r}>{r === 'zw' ? 'zw.' : `${r}%`}</option>
            ))}
          </select>
          <input
            className={`input ${styles.amountField}`}
            readOnly
            tabIndex={-1}
            value={amounts.net}
            aria-label="Kwota netto"
          />
          <input
            className={`input ${styles.amountField}`}
            readOnly
            tabIndex={-1}
            value={amounts.vat}
            aria-label="Kwota VAT"
          />
          <input
            className={`input ${styles.amountField}`}
            readOnly
            tabIndex={-1}
            value={amounts.gross}
            aria-label="Kwota brutto"
          />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => removeItem(idx)}
            disabled={items.length === 1}
          >
            ✕
          </button>
        </div>
        );
      })}

    </div>
  );
}

function InvoiceFooter({ totals, loading }) {
  return (
    <div className={styles.footer}>
      <div className={styles.totals}>
        <span>Netto: <strong>{totals.totalNet.toFixed(2)} {INVOICE_CURRENCY}</strong></span>
        <span>VAT: <strong>{totals.totalVat.toFixed(2)} {INVOICE_CURRENCY}</strong></span>
        <span>Brutto: <strong>{totals.totalGross.toFixed(2)} {INVOICE_CURRENCY}</strong></span>
      </div>
      <button type="submit" className="btn btn-primary" disabled={loading}>
        {loading ? <span className="spinner" /> : null}
        Zapisz fakturę
      </button>
    </div>
  );
}

/**
 * @param {object|null} initial   - wypełnij przy edycji
 * @param {Function}    onSubmit  - (formData) => Promise
 * @param {bool}        loading
 */
export default function InvoiceForm({ initial = null, onSubmit, loading = false }) {
  const isNewInvoice = !initial?.id;
  const { buyerNip, setBuyerNip, buyerInfo, nipError } = useBuyerLookup(initial?.buyer_snapshot?.nip ?? '');
  const [issueDate, setIssueDate] = useState(initial?.issue_date ?? TODAY);
  const [saleDate, setSaleDate] = useState(initial?.sale_date ?? TODAY);
  const initialDue = inferDueDateState(
    initial?.issue_date ?? TODAY,
    initial?.due_date ?? addDays(initial?.issue_date ?? TODAY, DEFAULT_DUE_PRESET),
  );
  const [paymentMethod, setPaymentMethod] = useState(
    isNewInvoice ? '' : (initial?.payment_method ?? 'transfer'),
  );
  const [dueDateSet, setDueDateSet] = useState(!isNewInvoice);
  const [dueDateMode, setDueDateMode] = useState(initialDue.mode);
  const [dueDatePreset, setDueDatePreset] = useState(initialDue.preset);
  const [dueDateCustom, setDueDateCustom] = useState(initialDue.custom);
  const { catalogItems, catalogLoading, catalogError } = useWarehouseCatalog();
  const { items, addItem, removeItem, updateItem, applyCatalogItem, totals } = useInvoiceItems(initial?.items, initial?.id);
  const [error, setError] = useState('');
  const [paymentMethodError, setPaymentMethodError] = useState('');
  const [dueDateFieldError, setDueDateFieldError] = useState('');
  const [amountPaid, setAmountPaid] = useState(() => (
    isNewInvoice ? '' : formatPaidAmountInput(inferPaidAmountFromInvoice(initial))
  ));
  const [amountPaidError, setAmountPaidError] = useState('');
  const syncedInvoiceKeyRef = useRef('');

  useEffect(() => {
    if (dueDateSet && dueDateMode === 'preset') {
      setDueDateCustom(addDays(issueDate, dueDatePreset));
    }
  }, [issueDate, dueDateMode, dueDatePreset, dueDateSet]);

  useEffect(() => {
    if (!initial?.id) return;
    const syncKey = [
      initial.id,
      initial.updated_at ?? '',
      initial.form_paid_amount ?? '',
      initial.remaining_amount ?? '',
      initial.total_gross ?? '',
      initial.issue_date ?? '',
      initial.due_date ?? '',
      initial.payment_method ?? '',
    ].join('|');
    if (syncedInvoiceKeyRef.current === syncKey) return;
    syncedInvoiceKeyRef.current = syncKey;

    const due = inferDueDateState(initial.issue_date, initial.due_date);
    setPaymentMethod(initial.payment_method ?? 'transfer');
    setDueDateSet(true);
    setDueDateMode(due.mode);
    setDueDatePreset(due.preset);
    setDueDateCustom(due.custom);
    setAmountPaid(formatPaidAmountInput(inferPaidAmountFromInvoice(initial)));
  }, [initial]);

  const resolvedDueDate = dueDateSet
    ? (dueDateMode === 'preset' ? addDays(issueDate, dueDatePreset) : dueDateCustom)
    : '';
  const dueDateValidationError = dueDateSet ? validateDueDate(issueDate, resolvedDueDate) : '';
  const dueDateError = dueDateFieldError || dueDateValidationError;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setPaymentMethodError('');
    setDueDateFieldError('');
    setAmountPaidError('');
    if (!buyerNip || buyerNip.length !== 10) {
      setError('NIP nabywcy jest wymagany (10 cyfr)');
      return;
    }
    if (!paymentMethod) {
      setPaymentMethodError('Wybierz sposób płatności');
      setError('Wybierz sposób płatności');
      return;
    }
    if (!dueDateSet || !resolvedDueDate) {
      setDueDateFieldError('Wybierz termin płatności');
      setError('Wybierz termin płatności');
      return;
    }
    if (dueDateValidationError) {
      setDueDateFieldError(dueDateValidationError);
      setError(dueDateValidationError);
      return;
    }
    const parsedItems = mapItemsToPayload(items);

    if (parsedItems.some((i) => !Number.isInteger(i.quantity) || i.quantity < 1)) {
      setError('Ilość musi być liczbą całkowitą większą od zera');
      return;
    }

    if (parsedItems.some((i) => isNaN(i.unit_price_net) || isNaN(i.vat_rate))) {
      setError('Sprawdź ceny i stawki VAT');
      return;
    }

    const parsedAmountPaid = parseAmountInput(amountPaid);
    if (amountPaid.trim()) {
      if (Number.isNaN(parsedAmountPaid)) {
        setAmountPaidError('Podaj poprawną kwotę wpłaty');
        setError('Podaj poprawną kwotę wpłaty');
        return;
      }
      if (parsedAmountPaid < 0) {
        setAmountPaidError('Kwota wpłaty nie może być ujemna');
        setError('Kwota wpłaty nie może być ujemna');
        return;
      }
      if (parsedAmountPaid > totals.totalGross) {
        setAmountPaidError('Kwota wpłaty nie może przekraczać kwoty brutto faktury');
        setError('Kwota wpłaty nie może przekraczać kwoty brutto faktury');
        return;
      }
    }

    const payload = {
      buyer_id: buyerInfo?.id ?? initial?.buyer_id ?? null,
      issue_date: issueDate,
      sale_date: saleDate,
      due_date: resolvedDueDate,
      payment_method: paymentMethod,
      currency: INVOICE_CURRENCY,
      items: parsedItems,
      amount_paid: isNewInvoice
        ? (parsedAmountPaid != null && parsedAmountPaid > 0 ? parsedAmountPaid : undefined)
        : (amountPaid.trim() ? parsedAmountPaid : 0),
    };
    try {
      await onSubmit(payload);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.response?.data?.error?.message ?? 'Błąd zapisu');
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      {error && <div className="alert alert-error">{error}</div>}

      <div className={styles.card}>
        <InvoiceHeaderSection
          buyerNip={buyerNip}
          setBuyerNip={setBuyerNip}
          nipError={nipError}
          buyerInfo={buyerInfo}
          issueDate={issueDate}
          saleDate={saleDate}
          setIssueDate={setIssueDate}
          setSaleDate={setSaleDate}
        />

        <ItemsSection
          items={items}
          addItem={addItem}
          removeItem={removeItem}
          updateItem={updateItem}
          applyCatalogItem={applyCatalogItem}
          catalogItems={catalogItems}
          catalogLoading={catalogLoading}
          catalogError={catalogError}
        />

        <PaymentSection
          paymentMethod={paymentMethod}
          setPaymentMethod={setPaymentMethod}
          dueDateMode={dueDateMode}
          setDueDateMode={setDueDateMode}
          dueDatePreset={dueDatePreset}
          setDueDatePreset={setDueDatePreset}
          dueDateCustom={dueDateCustom}
          setDueDateCustom={setDueDateCustom}
          dueDateSet={dueDateSet}
          setDueDateSet={setDueDateSet}
          issueDate={issueDate}
          dueDateError={dueDateError}
          paymentMethodError={paymentMethodError}
          amountPaid={amountPaid}
          setAmountPaid={setAmountPaid}
          amountPaidError={amountPaidError}
          totalGross={totals.totalGross}
        />

        <InvoiceFooter totals={totals} loading={loading} />
      </div>
    </form>
  );
}
