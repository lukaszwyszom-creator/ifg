import { useState, useEffect, useCallback } from 'react';
import { warehouseItemsApi } from '../../../api/warehouseItems';
import styles from '../WarehousePage.module.css';

const ITEM_TYPE_LABELS = {
  goods: 'Towar',
  service: 'Usługa',
};

function formatCatalogVat(item) {
  if (item?.vat_rate == null) return 'ustali PZ';
  return `${item.vat_rate}%`;
}

function formatCatalogPrice(item) {
  if (item?.default_price_net == null) return 'ustali PZ';
  return `${parseFloat(item.default_price_net).toLocaleString('pl-PL', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} zł`;
}

// ISBN format: 123-45-678912-3-4  (13 cyfr + 4 myślniki = 17 znaków)
function formatIsbn(raw) {
  const digits = raw.replace(/\D/g, '').slice(0, 13);
  if (!digits) return '';
  let result = digits.slice(0, 3);
  if (digits.length > 3) result += '-' + digits.slice(3, 5);
  if (digits.length > 5) result += '-' + digits.slice(5, 11);
  if (digits.length > 11) result += '-' + digits.slice(11, 12);
  if (digits.length > 12) result += '-' + digits.slice(12, 13);
  return result;
}

const ISBN_RE = /^\d{3}-\d{2}-\d{6}-\d-\d$/;

function ItemForm({ initial, onSave, onCancel }) {
  const [name, setName] = useState(initial?.name ?? '');
  const [isbn, setIsbn] = useState(initial?.isbn ?? '');
  const [itemType, setItemType] = useState(initial?.item_type ?? 'goods');
  const [unit, setUnit] = useState(initial?.unit ?? 'szt.');
  const [isWarehouseActive, setIsWarehouseActive] = useState(
    initial?.is_warehouse_active ?? true
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // Usługa → magazynowa disabled + odptaszony
  const isService = itemType === 'service';
  const effectiveWarehouseActive = isService ? false : isWarehouseActive;

  const handleIsbnChange = (e) => {
    setIsbn(formatIsbn(e.target.value));
  };

  const isbnValid = !isbn || ISBN_RE.test(isbn);
  const isbnLen = isbn.replace(/\D/g, '').length;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !isbnValid) return;
    setBusy(true);
    setError('');
    try {
      const body = {
        name: name.trim(),
        isbn: isbn || null,
        item_type: itemType,
        unit: unit.trim() || 'szt.',
        is_warehouse_active: effectiveWarehouseActive,
      };
      const saved = initial
        ? await warehouseItemsApi.update(initial.id, body)
        : await warehouseItemsApi.create(body);
      onSave(saved);
    } catch (err) {
      setError(
        err.response?.data?.error?.message ??
          err.response?.data?.detail ??
          'Błąd zapisu'
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.card}>
      <h3 className={styles.sectionTitle}>
        {initial ? 'Edytuj pozycję' : 'Nowa pozycja'}
      </h3>
      {initial && (
        <div
          style={{
            display: 'flex',
            gap: 24,
            marginBottom: 12,
            fontSize: '0.85rem',
            color: 'var(--color-text-secondary)',
          }}
        >
          <span>
            Cena netto:{' '}
            <strong style={{ color: 'var(--color-text-primary)' }}>
              {formatCatalogPrice(initial)}
            </strong>
          </span>
          <span>
            VAT:{' '}
            <strong style={{ color: 'var(--color-text-primary)' }}>
              {formatCatalogVat(initial)}
            </strong>
          </span>
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <div className={styles.formRowMain}>
          {/* Nazwa — max priorytet szerokości */}
          <div className={styles.fieldName}>
            <input
              className="input"
              placeholder="Nazwa pozycji *"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          {/* ISBN — opcjonalne */}
          <div className={styles.fieldIsbn}>
            <input
              className={`input${!isbnValid ? ' input-error' : ''}`}
              placeholder="123-45-678912-3-4"
              value={isbn}
              onChange={handleIsbnChange}
              maxLength={17}
              style={{ borderColor: !isbnValid ? 'var(--color-error, #e53e3e)' : undefined }}
            />
            <span className={styles.isbnCounter}>{isbnLen}/13</span>
          </div>

          {/* Rodzaj */}
          <div className={styles.fieldType}>
            <select
              className="input"
              value={itemType}
              onChange={(e) => setItemType(e.target.value)}
            >
              <option value="goods">Towar</option>
              <option value="service">Usługa</option>
            </select>
          </div>

          {/* Jednostka */}
          <div className={styles.fieldUnit}>
            <input
              className="input"
              placeholder="J.m."
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            />
          </div>

          {/* Magazynowa */}
          <div className={styles.fieldWarehouse}>
            <label
              className={`${styles.checkboxLabel} ${isService ? styles.checkboxDisabled : ''}`}
              title={isService ? 'Usługi nie wpływają na stany magazynowe' : ''}
            >
              <input
                type="checkbox"
                checked={effectiveWarehouseActive}
                disabled={isService}
                onChange={(e) => setIsWarehouseActive(e.target.checked)}
              />
              Magazynowa
            </label>
          </div>

          {/* Akcje */}
          <div className={styles.fieldActions}>
            <button className="btn btn-primary" type="submit" disabled={busy || !name.trim() || !isbnValid}>
              {busy ? <span className="spinner" /> : initial ? 'Zapisz' : 'Dodaj'}
            </button>
            {onCancel && (
              <button className="btn" type="button" onClick={onCancel}>
                Anuluj
              </button>
            )}
          </div>
        </div>

        {!isbnValid && isbn && (
          <div className="alert alert-error" style={{ marginTop: 6, fontSize: '0.8rem' }}>
            ISBN musi mieć format 123-45-678912-3-4
          </div>
        )}
        {error && (
          <div className="alert alert-error" style={{ marginTop: 8 }}>
            {error}
          </div>
        )}
      </form>
    </div>
  );
}

export default function CatalogTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [includeInactive, setIncludeInactive] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await warehouseItemsApi.list(includeInactive);
      setItems(data.items ?? []);
    } catch {
      setError('Błąd ładowania kartoteki');
    } finally {
      setLoading(false);
    }
  }, [includeInactive]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaved = () => {
    setShowAddForm(false);
    setEditingItem(null);
    load();
  };

  const handleDeactivate = async (item) => {
    if (!window.confirm(`Dezaktywuj pozycję „${item.name}"?`)) return;
    try {
      await warehouseItemsApi.deactivate(item.id);
      load();
    } catch {
      alert('Nie udało się dezaktywować pozycji');
    }
  };

  return (
    <div>
      <div className={styles.catalogToolbar}>
        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
          />
          Pokaż nieaktywne
        </label>
        {!showAddForm && !editingItem && (
          <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
            + Dodaj pozycję
          </button>
        )}
      </div>

      {showAddForm && (
        <ItemForm onSave={handleSaved} onCancel={() => setShowAddForm(false)} />
      )}
      {editingItem && (
        <ItemForm
          initial={editingItem}
          onSave={handleSaved}
          onCancel={() => setEditingItem(null)}
        />
      )}

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center' }}>
          <span className="spinner" />
        </div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyMsg}>Brak pozycji w kartotece</p>
        </div>
      ) : (
        <table className={styles.catalogTable}>
          <thead>
            <tr>
              <th>Nazwa</th>
              <th>Indeks (ISBN)</th>
              <th>Typ</th>
              <th className={styles.right}>VAT %</th>
              <th className={styles.right}>Cena netto</th>
              <th>J.m.</th>
              <th>Mag.</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className={!item.is_active ? styles.rowInactive : ''}>
                <td>{item.name}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                  {item.isbn ?? '—'}
                </td>
                <td>{ITEM_TYPE_LABELS[item.item_type] ?? item.item_type}</td>
                <td
                  className={styles.right}
                  style={item.vat_rate == null ? { color: 'var(--color-text-secondary)' } : undefined}
                >
                  {formatCatalogVat(item)}
                </td>
                <td
                  className={styles.right}
                  style={item.default_price_net == null ? { color: 'var(--color-text-secondary)' } : undefined}
                >
                  {formatCatalogPrice(item)}
                </td>
                <td>{item.unit}</td>
                <td>{item.is_warehouse_active ? 'Tak' : 'Nie'}</td>
                <td>
                  <span className={item.is_active ? styles.badgeActive : styles.badgeInactive}>
                    {item.is_active ? 'Aktywna' : 'Nieaktywna'}
                  </span>
                </td>
                <td className={styles.actions}>
                  <button
                    className="btn btn-sm"
                    onClick={() => setEditingItem(item)}
                    disabled={!item.is_active}
                  >
                    Edytuj
                  </button>
                  {item.is_active && (
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDeactivate(item)}
                    >
                      Dezaktywuj
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
