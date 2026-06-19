/** Mapowanie pozycji kartoteki magazynowej na pola linii FV sprzedaży. */

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
  return String(Math.round(n));
}

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

function grossToNet(gross, vatRate) {
  const rate = Number.parseFloat(String(vatRate ?? '').replace(',', '.'));
  const g = Number.parseFloat(String(gross ?? '').replace(',', '.'));
  if (!Number.isFinite(g)) return '';
  if (!Number.isFinite(rate) || rate <= 0) return g.toFixed(2);
  return roundMoney(g / (1 + rate / 100)).toFixed(2);
}

/**
 * @param {object} catalogItem
 * @param {{ supportsGrossMode?: boolean }} [options]
 */
export function catalogItemToLineFields(catalogItem, options = {}) {
  const supportsGrossMode = options.supportsGrossMode !== false;
  const priceMode = catalogItem.suggested_sale_price_mode ?? 'net';
  const fields = {
    name: catalogItem.name,
    isbn: catalogItem.isbn ?? '',
    unit: catalogItem.unit || 'szt.',
    price_mode: 'net',
    unit_price_net: '',
    unit_price_gross: '',
    vat_rate: catalogItem.vat_rate != null
      ? normalizeVatRateForSelect(catalogItem.vat_rate)
      : '23',
  };

  if (catalogItem.suggested_sale_price != null && catalogItem.suggested_sale_price !== '') {
    const price = String(catalogItem.suggested_sale_price);
    if (priceMode === 'gross') {
      if (supportsGrossMode) {
        fields.price_mode = 'gross';
        fields.unit_price_gross = price;
      } else {
        fields.unit_price_net = grossToNet(price, fields.vat_rate);
      }
    } else {
      fields.unit_price_net = price;
    }
  } else if (catalogItem.default_price_net != null && catalogItem.default_price_net !== '') {
    fields.unit_price_net = String(catalogItem.default_price_net);
  }

  return fields;
}

export { grossToNet, normalizeVatRateForSelect };
