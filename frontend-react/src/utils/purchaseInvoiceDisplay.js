const IFG_PURCHASE_NUMBER_RE = /^FV\/[0-9]+\/[0-9]{2}\/[0-9]{4}$/i;
const UI_SEQUENCE_NUMBER_RE = /^[0-9]{2}\/[0-9]{2}\/[0-9]{4}$/;

export function getPurchaseDisplayNumber(invoice) {
  const rawNumber = String(invoice?.number_local || '').trim();
  const ksefRef = String(invoice?.ksef_reference_number || '').trim();
  const looksLikeIfgNumber = rawNumber
    && (IFG_PURCHASE_NUMBER_RE.test(rawNumber) || UI_SEQUENCE_NUMBER_RE.test(rawNumber));

  if (rawNumber && !looksLikeIfgNumber) {
    return { displayNumber: rawNumber, numberSource: 'ksef:P_2' };
  }
  if (ksefRef) {
    return { displayNumber: ksefRef, numberSource: 'ksef:reference' };
  }
  if (rawNumber) {
    return { displayNumber: rawNumber, numberSource: 'number_local:legacy' };
  }
  return { displayNumber: 'brak numeru', numberSource: 'missing' };
}
