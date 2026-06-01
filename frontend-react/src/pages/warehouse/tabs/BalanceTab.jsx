import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { warehouseItemsApi } from '../../../api/warehouseItems';
import styles from '../WarehousePage.module.css';
import logoIfg from '../../../assets/logo-ifg.png';

const DELIVERY_ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
const LS_VALUE_2025 = 'ifg.warehouse.balance.manual_value_2025';
const LS_INVENTORY_SEQ = 'ifg.warehouse.inventory_pdf_seq';

/** Wymagane pliki w public/fonts/ — CharisSIL-Regular/Bold/Italic.ttf */
const CHARIS_SIL_FONTS = [
  '/fonts/CharisSIL-Regular.ttf',
  '/fonts/CharisSIL-Bold.ttf',
  '/fonts/CharisSIL-Italic.ttf',
];
const CHARIS_SIL_AVAILABLE = true;

function charisSilFontFaceCss() {
  if (!CHARIS_SIL_AVAILABLE) return '';
  return `
  @font-face {
    font-family: 'CharisSIL';
    src: url('${CHARIS_SIL_FONTS[0]}') format('truetype');
    font-weight: 400;
    font-style: normal;
  }
  @font-face {
    font-family: 'CharisSIL';
    src: url('${CHARIS_SIL_FONTS[1]}') format('truetype');
    font-weight: 700;
    font-style: normal;
  }
  @font-face {
    font-family: 'CharisSIL';
    src: url('${CHARIS_SIL_FONTS[2]}') format('truetype');
    font-weight: 400;
    font-style: italic;
  }`;
}

function fmtAmount(v) {
  if (v == null || v === '') return '—';
  return parseFloat(v).toLocaleString('pl-PL', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtAmountZl(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return `${fmtAmount(v)} zł`;
}

function layerValueNet(entry) {
  if (entry.value_net != null && entry.value_net !== '') {
    const v = parseFloat(entry.value_net);
    if (!Number.isNaN(v)) return v;
  }
  const qty = parseFloat(entry.quantity_available);
  const price = parseFloat(entry.unit_price_net);
  if (Number.isNaN(qty) || Number.isNaN(price)) return 0;
  return qty * price;
}

function fmtQty(v) {
  if (v == null) return '—';
  return Math.round(parseFloat(v)).toLocaleString('pl-PL');
}

function fmtDate(v) {
  if (!v) return '—';
  return new Date(v).toLocaleDateString('pl-PL');
}

function deliveryLabel(n) {
  return DELIVERY_ROMAN[n - 1] ?? String(n);
}

function fmtDatePl(d = new Date()) {
  return d.toLocaleDateString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function nextInventoryFilename() {
  const today = fmtDatePl().replace(/\./g, '-');
  const key = `${LS_INVENTORY_SEQ}_${today}`;
  const seq = (parseInt(localStorage.getItem(key) ?? '0', 10) || 0) + 1;
  localStorage.setItem(key, String(seq));
  return `Inwentaryzacja_${today}_${seq}.pdf`;
}

function buildInventoryHtml(rows, totalNet, logoUrl) {
  const today = fmtDatePl();
  const fontFamily = CHARIS_SIL_AVAILABLE
    ? "'CharisSIL', Georgia, serif"
    : "Georgia, 'Times New Roman', serif";

  const tableRows = rows
    .map((e, idx) => {
      const qty = Math.round(parseFloat(e.quantity_available) || 0);
      const price = parseFloat(e.unit_price_net) || 0;
      const lineNet = layerValueNet(e);
      const name = e.deliveryLabel ? `${e.name} (${e.deliveryLabel})` : e.name;
      return `<tr>
        <td style="text-align:center">${idx + 1}</td>
        <td>${escHtml(name)}</td>
        <td style="text-align:center">${qty.toLocaleString('pl-PL')}</td>
        <td style="text-align:right">${fmtAmount(price)} zł</td>
        <td style="text-align:right">${fmtAmount(lineNet)} zł</td>
      </tr>`;
    })
    .join('');

  return `<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"/>
<title>Inwentaryzacja ${today}</title>
<style>
  ${charisSilFontFaceCss()}
  @page { size: A4; margin: 18mm; }
  body { font-family: ${fontFamily}; color: #111; margin: 0; padding: 24px; }
  .hdr-right { text-align: right; font-size: 10pt; margin-bottom: 24px; }
  .center { text-align: center; }
  .line12 { font-size: 12pt; margin: 6px 0; }
  .line14 { font-size: 14pt; margin: 8px 0; }
  .bold { font-weight: bold; }
  table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 11pt; }
  th, td { border: 1px solid #bbb; padding: 5px 8px; }
  th { background: #f5f5f5; font-weight: 600; }
  tfoot td { font-weight: bold; border-top: 2px solid #888; }
  .footer { margin-top: 32px; text-align: center; font-size: 10pt; font-style: italic; color: #444; }
  .logo { margin-top: 12px; text-align: center; }
  .logo img { height: 48px; filter: grayscale(1); opacity: 0.65; }
  .logo-fallback { font-size: 18pt; color: #999; letter-spacing: 4px; font-weight: 600; }
</style></head><body>
  <div class="hdr-right">Bydgoszcz ${today}</div>
  <div class="center line12">Ikona Małgorzata Katarzyna Krzyżanowska-Witkowska</div>
  <div class="center line12">NIP 957-040-28-57; ul. Kossaka 72, 85-307 Bydgoszcz</div>
  <div class="center line14 bold">Inwentaryzacja stanu magazynowego</div>
  <div class="center line14">na dzień: ${today}</div>
  <div class="center line14">wartość: ${fmtAmountZl(totalNet)}</div>
  <table>
    <thead><tr>
      <th style="width:36px">lp</th>
      <th>Towar</th>
      <th style="width:70px">liczba</th>
      <th style="width:100px">cena netto</th>
      <th style="width:110px">wartość netto</th>
    </tr></thead>
    <tbody>${tableRows}</tbody>
    <tfoot><tr>
      <td colspan="4" style="text-align:right">Razem</td>
      <td style="text-align:right">${fmtAmount(totalNet)} zł</td>
    </tr></tfoot>
  </table>
  <div class="footer">wygenerowano z systemu Imperium Faktur G, Ikona 2026</div>
  <div class="logo">${logoUrl ? `<img src="${logoUrl}" alt="IFG" />` : '<div class="logo-fallback">IFG</div>'}</div>
</body></html>`;
}

function saveInventoryPdf(_html, _filename) {
  window.alert(
    'Trwały zapis PDF w poolu inwentaryzacji wymaga backendowego endpointu ' +
      '(np. POST /warehouse/inventory-reports). W ETAP 1 użyj „Drukuj” → „Zapisz jako PDF” w przeglądarce.'
  );
}

function enrichEntries(entries) {
  const indicesByIsbn = new Map();
  entries.forEach((e, idx) => {
    if (!e.isbn) return;
    if (!indicesByIsbn.has(e.isbn)) indicesByIsbn.set(e.isbn, []);
    indicesByIsbn.get(e.isbn).push(idx);
  });

  return entries.map((e, idx) => {
    const group = e.isbn ? indicesByIsbn.get(e.isbn) : null;
    const isbnGrouped = group && group.length > 1;
    const posInGroup = isbnGrouped ? group.indexOf(idx) : -1;
    return {
      ...e,
      deliveryLabel:
        isbnGrouped && posInGroup >= 0
          ? `dostawa ${deliveryLabel(posInGroup + 1)}`
          : null,
      isbnGrouped: !!isbnGrouped,
    };
  });
}

export default function BalanceTab({ onAddItem }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [value2025, setValue2025] = useState(() => localStorage.getItem(LS_VALUE_2025) ?? '0');
  const [value2025Locked, setValue2025Locked] = useState(true);
  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false);
  const [pdfPreviewHtml, setPdfPreviewHtml] = useState('');
  const [pdfFilename, setPdfFilename] = useState('');
  const pdfIframeRef = useRef(null);

  const rows = useMemo(() => enrichEntries(entries), [entries]);
  const total2026 = useMemo(
    () => entries.reduce((sum, e) => sum + layerValueNet(e), 0),
    [entries]
  );
  const manual2025 = parseFloat(value2025) || 0;
  const valueDiff = total2026 - manual2025;
  const diffColor =
    valueDiff > 0
      ? 'var(--color-success, #15803d)'
      : valueDiff < 0
        ? 'var(--color-error, #e53e3e)'
        : 'var(--color-text-secondary)';

  const handleValue2025Change = (e) => {
    const next = e.target.value;
    setValue2025(next);
    localStorage.setItem(LS_VALUE_2025, next);
  };

  const handleGenerateInventory = useCallback(() => {
    const html = buildInventoryHtml(rows, total2026, logoIfg);
    setPdfPreviewHtml(html);
    setPdfFilename(nextInventoryFilename());
    setPdfPreviewOpen(true);
  }, [rows, total2026]);

  const handlePrintInventory = () => {
    pdfIframeRef.current?.contentWindow?.print();
  };

  const handleSaveInventory = () => {
    saveInventoryPdf(pdfPreviewHtml, pdfFilename);
  };

  const handleClosePreview = () => {
    setPdfPreviewOpen(false);
    setPdfPreviewHtml('');
  };

  useEffect(() => {
    warehouseItemsApi
      .listBalance()
      .then((r) => setEntries(r.items ?? []))
      .catch(() => setError('Błąd ładowania stanów magazynowych'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className={styles.emptyMsg}>Ładowanie…</p>;

  if (error)
    return <p style={{ color: 'var(--color-error)', padding: 16 }}>{error}</p>;

  if (entries.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyMsg}>Brak pozycji magazynowych</p>
        <button className="btn btn-primary" onClick={onAddItem}>
          Dodaj pozycję
        </button>
      </div>
    );
  }

  return (
    <div>
      <div
        className={styles.catalogToolbar}
        style={{ flexWrap: 'wrap', gap: 12, alignItems: 'center' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <span className={styles.sectionTitle} style={{ margin: 0 }}>
            Stan magazynowy: {entries.length} pozycji,{' '}
            <span style={{ color: 'var(--color-warning, #f59e0b)' }}>{fmtAmountZl(total2026)}</span>
          </span>
          <button
            className="btn btn-sm btn-primary"
            type="button"
            onClick={handleGenerateInventory}
          >
            Generuj inwentaryzację
          </button>
        </div>

        <div
          style={{
            marginLeft: 'auto',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 12,
            fontSize: '0.85rem',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: 'var(--color-text-secondary)' }}>magazyn 2025:</span>
            <input
              className="input"
              type="number"
              step="0.01"
              min="0"
              style={{ width: 110, textAlign: 'right', padding: '2px 6px', fontSize: '0.85rem' }}
              value={value2025}
              disabled={value2025Locked}
              onChange={handleValue2025Change}
            />
            <button
              className="btn btn-sm btn-secondary"
              type="button"
              onClick={() => setValue2025Locked((v) => !v)}
            >
              {value2025Locked ? 'Odblokuj' : 'Zablokuj'}
            </button>
          </span>
          <span>
            <span style={{ color: 'var(--color-text-secondary)' }}>Różnica: </span>
            <strong style={{ color: diffColor }}>
              {valueDiff > 0 ? '+' : ''}
              {fmtAmountZl(valueDiff)}
            </strong>
          </span>
        </div>
      </div>

      <table className={styles.catalogTable} style={{ tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: 40 }} />
          <col />
          <col style={{ width: 148 }} />
          <col style={{ width: 112 }} />
          <col style={{ width: 96 }} />
          <col style={{ width: 72 }} />
          <col style={{ width: 88 }} />
          <col style={{ width: 52 }} />
          <col style={{ width: 96 }} />
        </colgroup>
        <thead>
          <tr>
            <th style={{ textAlign: 'center' }}>LP</th>
            <th style={{ textAlign: 'left' }}>Towar</th>
            <th style={{ textAlign: 'left' }}>ISBN</th>
            <th style={{ textAlign: 'left' }}>Dokument źródłowy</th>
            <th style={{ textAlign: 'left' }}>Data dokumentu</th>
            <th style={{ textAlign: 'center' }}>Liczba dostępna</th>
            <th style={{ textAlign: 'center' }}>Cena netto</th>
            <th style={{ textAlign: 'center' }}>VAT</th>
            <th className={styles.right}>Wartość netto</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e, idx) => (
            <tr key={e.layer_id}>
              <td style={{ textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.85rem' }}>
                {idx + 1}
              </td>
              <td style={{ textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {e.name}
                {e.deliveryLabel && (
                  <div
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--color-text-secondary)',
                      marginTop: 2,
                      fontWeight: 400,
                    }}
                  >
                    {e.deliveryLabel}
                  </div>
                )}
              </td>
              <td
                style={{
                  textAlign: 'left',
                  whiteSpace: 'nowrap',
                  fontSize: '0.85rem',
                  color: e.isbnGrouped
                    ? 'var(--color-text-primary)'
                    : 'var(--color-text-secondary)',
                }}
              >
                {e.isbn ?? '—'}
              </td>
              <td style={{ textAlign: 'left', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                {e.source_document_number ?? '—'}
              </td>
              <td
                style={{
                  textAlign: 'left',
                  color: 'var(--color-text-secondary)',
                  fontSize: '0.85rem',
                }}
              >
                {fmtDate(e.source_document_date)}
              </td>
              <td style={{ textAlign: 'center' }}>{fmtQty(e.quantity_available)}</td>
              <td style={{ textAlign: 'center' }}>{fmtAmount(e.unit_price_net)} zł</td>
              <td style={{ textAlign: 'center' }}>
                {e.vat_rate != null ? `${e.vat_rate}%` : '—'}
              </td>
              <td className={styles.right}>{fmtAmount(e.value_net)} zł</td>
            </tr>
          ))}
        </tbody>
      </table>

      {pdfPreviewOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
          onClick={handleClosePreview}
        >
          <div
            style={{
              background: 'var(--color-bg, #fff)',
              borderRadius: 8,
              width: 'min(920px, 100%)',
              maxHeight: '90vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: 'flex',
                gap: 8,
                padding: '12px 16px',
                borderBottom: '1px solid var(--color-border, #ddd)',
                alignItems: 'center',
              }}
            >
              <span style={{ flex: 1, fontSize: '0.9rem', color: 'var(--color-text-secondary)' }}>
                Podgląd inwentaryzacji
                {!CHARIS_SIL_AVAILABLE && (
                  <span style={{ color: 'var(--color-warning, #f59e0b)', marginLeft: 8 }}>
                    (font CharisSIL niedostępny — fallback serif)
                  </span>
                )}
              </span>
              <button className="btn btn-sm btn-primary" type="button" onClick={handlePrintInventory}>
                Drukuj
              </button>
              <button className="btn btn-sm btn-secondary" type="button" onClick={handleSaveInventory}>
                Zapisz
              </button>
              <button className="btn btn-sm btn-ghost" type="button" onClick={handleClosePreview}>
                Anuluj
              </button>
            </div>
            <iframe
              ref={pdfIframeRef}
              title="Podgląd inwentaryzacji"
              srcDoc={pdfPreviewHtml}
              style={{ flex: 1, minHeight: 480, border: 'none', background: '#fff' }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
