const UNSENT_STATUSES = new Set([
  '',
  'ready_for_submission',
  'ready',
  'gotowa',
]);

const PROCESSING_STATUSES = new Set([
  'sending',
  'in_progress',
  'processing',
  'queued',
  'submitted',
  'waiting_status',
  'failed_temporary',
]);

const REJECTED_STATUSES = new Set([
  'rejected',
  'failed_permanent',
  'failed_retryable',
]);

const UPO_STATUSES = new Set([
  'accepted',
  'upo_received',
  'delivered',
  'success',
]);

/**
 * Zwraca znormalizowany stan KSeF faktury do użycia w UI.
 *
 * @param {string}  status   - invoice.status z backendu
 * @param {object}  invoice  - pełny obiekt faktury (opcjonalny, do tooltip)
 * @returns {{ kind: string, label: string, tooltip: string|null }}
 */
export function resolveKsefState(status, invoice = {}) {
  const normalized = (status ?? '').toString().trim().toLowerCase();

  if (UNSENT_STATUSES.has(normalized)) {
    return { kind: 'send', label: 'Wyślij', tooltip: null };
  }
  if (PROCESSING_STATUSES.has(normalized)) {
    return {
      kind: 'processing',
      label: 'W toku',
      tooltip: 'Faktura przekazana do KSeF – oczekiwanie na wynik',
    };
  }
  if (REJECTED_STATUSES.has(normalized)) {
    return {
      kind: 'rejected',
      label: 'Odrzucona',
      tooltip: 'Faktura odrzucona przez KSeF – sprawdź zakładkę Monitor KSeF po szczegóły błędu',
    };
  }
  if (UPO_STATUSES.has(normalized)) {
    const ref = invoice?.ksef_reference_number;
    return {
      kind: 'upo',
      label: 'OK (UPO)',
      tooltip: ref ? `Ref KSeF: ${ref}` : 'Faktura zaakceptowana przez KSeF',
    };
  }

  return { kind: 'send', label: 'Wyślij', tooltip: null };
}

/**
 * Określa edytowalność faktury na podstawie statusu.
 * 
 * Edytowalne:
 * - READY_FOR_SUBMISSION (gotowa do wysyłki)
 * - REJECTED (odrzucona, wymaga poprawy)
 * 
 * Nieedytowalne:
 * - SENDING (wysyłanie do KSeF / analiza)
 * - ACCEPTED (zaakceptowana przez KSeF)
 */
export function isInvoiceEditable(status) {
  const normalized = (status ?? '').toString().trim().toLowerCase();
  
  // Edytowalne statusy
  const EDITABLE_STATUSES = new Set([
    'ready_for_submission',
    'rejected',
  ]);
  
  return EDITABLE_STATUSES.has(normalized);
}

export function getInvoiceOpenMode(status) {
  return isInvoiceEditable(status) ? 'edit' : 'preview';
}
