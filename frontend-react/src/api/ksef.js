import client from './client';

let statusInFlightPromise = null;
let statusDebouncedPromise = null;
let statusRequestId = 0;
let statusMutationVersion = 0;
let statusInFlightNip = null;
let statusDebouncedNip = null;

function fetchStatusNow(nip = null) {
  const normalizedNip = nip || null;
  if (statusInFlightPromise && statusInFlightNip === normalizedNip) {
    return statusInFlightPromise;
  }

  statusInFlightNip = normalizedNip;
  statusInFlightPromise = client
    .get('/ksef/status', { params: normalizedNip ? { nip: normalizedNip } : {} })
    .then((r) => r.data)
    .finally(() => {
      statusInFlightPromise = null;
      statusInFlightNip = null;
    });

  return statusInFlightPromise;
}

function getStatusDebounced(nip = null) {
  const normalizedNip = nip || null;
  if (statusInFlightPromise && statusInFlightNip === normalizedNip) {
    return statusInFlightPromise;
  }

  if (statusDebouncedPromise && statusDebouncedNip === normalizedNip) {
    return statusDebouncedPromise;
  }

  statusDebouncedNip = normalizedNip;
  statusDebouncedPromise = new Promise((resolve, reject) => {
    window.setTimeout(() => {
      fetchStatusNow(normalizedNip)
        .then(resolve)
        .catch(reject)
        .finally(() => {
          statusDebouncedPromise = null;
          statusDebouncedNip = null;
        });
    }, 400);
  });

  return statusDebouncedPromise;
}

function markStatusMutation() {
  statusMutationVersion += 1;
}

function getStatus(nip = null) {
  const currentRequestId = ++statusRequestId;
  const currentMutationVersion = statusMutationVersion;

  return getStatusDebounced(nip).then((result) => {
    if (currentRequestId !== statusRequestId) {
      return null;
    }
    if (currentMutationVersion !== statusMutationVersion) {
      return null;
    }
    return result;
  });
}

export const ksefApi = {
  getStatus,
  markStatusMutation,

  openSession: (nip) =>
    client.post('/ksef-sessions/', { nip }).then((r) => r.data),

  getActiveSession: (nip) =>
    client.get('/ksef-sessions/active', { params: { nip } }).then((r) => r.data),

  closeSession: (nip) =>
    client.post('/ksef-sessions/close', { nip }).then((r) => r.data),

  syncPurchaseInvoices: (nip, dateFrom, dateTo) =>
    client
      .post('/ksef-sessions/sync-purchase', { nip, date_from: dateFrom, date_to: dateTo })
      .then((r) => r.data),

  getSyncPurchaseJobStatus: (jobId) =>
    client.get(`/ksef-sessions/sync-purchase/jobs/${jobId}`).then((r) => r.data),

  getPurchaseSyncStatus: () =>
    client.get('/ksef/sync/status').then((r) => r.data),

  syncPurchasesNow: (force = false, nip = null) =>
    client.post('/ksef/sync/purchases', { force, nip }).then((r) => r.data),
};
