const PLN_FORMATTER = new Intl.NumberFormat('pl-PL', {
  useGrouping: 'always',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const CURRENCY_SYMBOLS = {
  PLN: 'zł',
  EUR: '€',
  USD: '$',
};

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return 0;
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

export function formatCurrencyPLN(value) {
  const formatted = PLN_FORMATTER
    .format(toFiniteNumber(value))
    .replace(/\u00A0|\u202F/g, ' ');
  return `${formatted} zł`;
}

export function formatAmountNeutral(value) {
  return PLN_FORMATTER
    .format(toFiniteNumber(value))
    .replace(/\u00A0|\u202F/g, ' ');
}

export function formatAmountByCurrency(value, currency) {
  const code = String(currency || 'PLN').trim().toUpperCase();
  if (code === 'PLN') return formatCurrencyPLN(value);

  const formatted = formatAmountNeutral(value);
  const suffix = CURRENCY_SYMBOLS[code] || code;
  return `${formatted} ${suffix}`;
}

export function formatSignedCurrencyPLN(value, options = {}) {
  const { showPlus = true } = options;
  const num = toFiniteNumber(value);
  const sign = num > 0 && showPlus ? '+' : '';
  return `${sign}${formatCurrencyPLN(num)}`;
}
