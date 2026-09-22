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
