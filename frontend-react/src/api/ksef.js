import client from './client';

let statusInFlightPromise = null;
let statusDebounceTimer = null;
let statusDebouncedPromise = null;
let statusRequestId = 0;
let statusMutationVersion = 0;

function fetchStatusNow() {
  if (statusInFlightPromise) {
    return statusInFlightPromise;
  }

  statusInFlightPromise = client
    .get('/ksef/status')
    .then((r) => r.data)
    .finally(() => {
      statusInFlightPromise = null;
    });

  return statusInFlightPromise;
}

function getStatusDebounced() {
  if (statusInFlightPromise) {
    return statusInFlightPromise;
  }

  if (statusDebouncedPromise) {
    return statusDebouncedPromise;
  }

  statusDebouncedPromise = new Promise((resolve, reject) => {
    statusDebounceTimer = window.setTimeout(() => {
      statusDebounceTimer = null;
      fetchStatusNow()
        .then(resolve)
        .catch(reject)
        .finally(() => {
          statusDebouncedPromise = null;
        });
    }, 400);
  });

  return statusDebouncedPromise;
}

function markStatusMutation() {
  statusMutationVersion += 1;
}

function getStatus() {
  const currentRequestId = ++statusRequestId;
  const currentMutationVersion = statusMutationVersion;

  return getStatusDebounced().then((result) => {
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
    client.delete('/ksef-sessions/', { params: { nip } }).then((r) => r.data),

  syncPurchaseInvoices: (nip, dateFrom, dateTo) =>
    client
      .post('/ksef-sessions/sync-purchase', { nip, date_from: dateFrom, date_to: dateTo })
      .then((r) => r.data),
};
