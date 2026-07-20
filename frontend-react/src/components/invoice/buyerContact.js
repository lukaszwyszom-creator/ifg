/**
 * Kontakt nabywcy/sprzedawcy z snapshotu faktury — wyłącznie pola kontaktowe.
 * Bez NIP, adresu i pozostałych danych firmowych.
 */

const CONTACT_KEY_RE = /^(phone|telefon|tel|mobile|komorka|komórka|email|e[_-]?mail|mail|fax|kontakt)$/i;

const CONTACT_EXCLUDE_RE = /nip|regon|krs|name|street|postal|city|country|address|adres|payment|legal|voivod|county|commune|building|apartment/i;

/**
 * Tytuł popupu kontrahenta: „Nazwa, Miejscowość”.
 * Miejscowość pochodzi z tego samego snapshotu co nazwa (pole `city`).
 * IFG zakłada, że city zawsze jest obecne — bez fallbacków UI.
 *
 * @param {string} name
 * @param {Record<string, unknown>|null|undefined} snapshot
 * @returns {string}
 */
export function formatContractorPopupTitle(name, snapshot) {
  return `${name}, ${snapshot.city}`;
}

/**
 * @param {Record<string, unknown>|null|undefined} snapshot
 * @returns {string[]}
 */
export function extractBuyerContactLines(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return [];

  const lines = [];
  const seen = new Set();

  for (const [rawKey, rawValue] of Object.entries(snapshot)) {
    const key = String(rawKey || '').trim();
    if (!key || CONTACT_EXCLUDE_RE.test(key)) continue;
    if (!CONTACT_KEY_RE.test(key)) continue;

    const value = String(rawValue ?? '').trim();
    if (!value) continue;

    const dedupe = value.toLowerCase();
    if (seen.has(dedupe)) continue;
    seen.add(dedupe);
    lines.push(value);
  }

  return lines;
}
