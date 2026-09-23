/**
 * FA(3) AdresL1 helpers — muszą być zsynchronizowane z app/domain/party_address.py
 */

function stripField(value) {
  const text = String(value ?? '').trim();
  if (!text) return '';
  const lower = text.toLowerCase();
  if (lower === 'none' || lower === 'null' || lower === 'undefined') return '';
  return text;
}

export function formatAdresL1(snapshot = {}) {
  const addressText = stripField(snapshot.address);
  if (addressText) return addressText;

  const street = stripField(snapshot.street);
  const buildingNo = stripField(snapshot.building_no);
  const apartmentNo = stripField(snapshot.apartment_no);
  const postalCode = stripField(snapshot.postal_code);
  const city = stripField(snapshot.city);

  let streetLine = '';
  if (street) {
    streetLine = [street, buildingNo].filter(Boolean).join(' ');
  } else if (buildingNo && city) {
    streetLine = `${city} ${buildingNo}`;
  } else if (buildingNo) {
    streetLine = buildingNo;
  }

  if (apartmentNo) {
    streetLine = `${streetLine} m. ${apartmentNo}`.trim();
  }

  const cityLine = [postalCode, city].filter(Boolean).join(' ');
  if (streetLine && cityLine) return `${streetLine}, ${cityLine}`;
  return streetLine || cityLine || '-';
}

export function canBuildAdresL1(snapshot = {}) {
  if (stripField(snapshot.address)) return true;

  const street = stripField(snapshot.street);
  const buildingNo = stripField(snapshot.building_no);
  const apartmentNo = stripField(snapshot.apartment_no);
  const postalCode = stripField(snapshot.postal_code);
  const city = stripField(snapshot.city);

  const hasPlaceLine = Boolean(street || buildingNo || apartmentNo);
  const hasLocality = Boolean(postalCode && city);
  if (!hasPlaceLine || !hasLocality) return false;

  const line = formatAdresL1(snapshot);
  return Boolean(line && line !== '-');
}

/** Opis braków pod UI / komunikat KSeF (zgodny z canBuildAdresL1). */
export function missingAdresL1Hints(snapshot = {}) {
  if (stripField(snapshot.address) || canBuildAdresL1(snapshot)) return [];

  const street = stripField(snapshot.street);
  const buildingNo = stripField(snapshot.building_no);
  const apartmentNo = stripField(snapshot.apartment_no);
  const postalCode = stripField(snapshot.postal_code);
  const city = stripField(snapshot.city);

  const hints = [];
  if (!postalCode || !city) {
    hints.push('kod pocztowy i miejscowość');
  }
  if (!street && !buildingNo && !apartmentNo) {
    hints.push('ulicę/miejscowość z numerem albo sam nr budynku');
  }
  return hints;
}

export function buyerAddressIncompleteMessage(snapshot = {}) {
  const hints = missingAdresL1Hints(snapshot);
  if (!hints.length) {
    return 'Uzupełnij Adres nabywcy na fakturze — kliknij, aby otworzyć edycję.';
  }
  return `Uzupełnij Adres nabywcy (${hints.join('; ')}). Kliknij, aby otworzyć edycję.`;
}

/** Sekcja adresu ma być widoczna gdy znamy NIP / kontrahenta / jakiekolwiek pola adresu. */
export function shouldShowBuyerAddressEditor({
  buyerInfo = null,
  buyerNip = '',
  buyerAddress = {},
} = {}) {
  if (buyerInfo) return true;
  if (String(buyerNip || '').replace(/\D/g, '').length === 10) return true;
  return ['street', 'building_no', 'apartment_no', 'postal_code', 'city'].some(
    (key) => Boolean(stripField(buyerAddress?.[key])),
  );
}
