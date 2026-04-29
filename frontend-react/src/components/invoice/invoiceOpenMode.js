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

export function resolveKsefState(status) {
  const normalized = (status ?? '').toString().trim().toLowerCase();

  if (UNSENT_STATUSES.has(normalized)) {
    return { kind: 'send', label: 'Wyślij' };
  }
  if (PROCESSING_STATUSES.has(normalized)) {
    return { kind: 'processing', label: 'Analiza' };
  }
  if (REJECTED_STATUSES.has(normalized)) {
    return { kind: 'rejected', label: 'Odrzucona' };
  }
  if (UPO_STATUSES.has(normalized)) {
    return { kind: 'upo', label: 'OK (UPO)' };
  }

  return { kind: 'send', label: 'Wyślij' };
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
