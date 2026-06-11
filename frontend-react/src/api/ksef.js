import client from './client';

let statusInFlightPromise = null;
let statusDebouncedPromise = null;
let statusRequestId = 0;
let statusMutationVersion = 0;
let statusInFlightNip = null;
let statusDebouncedNip = null;

export const PURCHASE_SYNC_DAYS_BACK = 90;
export const PURCHASE_SYNC_POLL_INTERVAL_MS = 3000;
export const PURCHASE_SYNC_MAX_POLL_ATTEMPTS = 120;

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

export function formatPurchaseSyncDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function purchaseSyncDateRange(daysBack = PURCHASE_SYNC_DAYS_BACK) {
  const dateTo = new Date();
  const dateFrom = new Date();
  dateFrom.setDate(dateFrom.getDate() - daysBack);
  return {
    dateFrom: formatPurchaseSyncDate(dateFrom),
    dateTo: formatPurchaseSyncDate(dateTo),
  };
}

export function normalizePurchaseSyncCounts(raw = {}) {
  const saved = Number.isFinite(Number(raw.saved ?? raw.created))
    ? Number(raw.saved ?? raw.created)
    : 0;
  const received = Number.isFinite(Number(raw.received ?? raw.ksef_returned))
    ? Number(raw.received ?? raw.ksef_returned)
    : 0;
  const skippedExisting = Number.isFinite(Number(raw.skipped_existing))
    ? Number(raw.skipped_existing)
    : 0;
  const skippedParse = Number.isFinite(Number(raw.skipped_parse ?? raw.errors))
    ? Number(raw.skipped_parse ?? raw.errors)
    : 0;
  return { saved, received, skippedExisting, skippedParse };
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function pollPurchaseSyncJob(
  jobId,
  {
    onProgress,
    intervalMs = PURCHASE_SYNC_POLL_INTERVAL_MS,
    maxAttempts = PURCHASE_SYNC_MAX_POLL_ATTEMPTS,
  } = {},
) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await sleep(intervalMs);
    const jobStatus = await client
      .get(`/ksef-sessions/sync-purchase/jobs/${jobId}`)
      .then((r) => r.data);
    if (onProgress) {
      onProgress(jobStatus);
    }
    if (jobStatus.status === 'done') {
      return jobStatus;
    }
    if (jobStatus.status === 'failed') {
      const err = new Error(jobStatus.error || 'Synchronizacja zakończona błędem.');
      err.jobStatus = jobStatus;
      throw err;
    }
  }
  const err = new Error('Przekroczono czas oczekiwania na synchronizację KSeF.');
  err.timedOut = true;
  throw err;
}

/**
 * Uruchamia synchronizację zakupów KSeF bez blokowania UI na cały import.
 * Preferuje async job (202); fallback na synchroniczny endpoint tylko gdy job API = 404.
 */
async function runPurchaseSync(
  nip,
  {
    daysBack = PURCHASE_SYNC_DAYS_BACK,
    forceFull = false,
    onStarted,
    onProgress,
  } = {},
) {
  const { dateFrom, dateTo } = purchaseSyncDateRange(daysBack);

  try {
    const { job_id: jobId } = await client
      .post('/ksef-sessions/sync-purchase', { nip, date_from: dateFrom, date_to: dateTo })
      .then((r) => r.data);
    if (onStarted) {
      onStarted({ mode: 'async', jobId });
    }
    const jobStatus = await pollPurchaseSyncJob(jobId, { onProgress });
    return {
      mode: 'async',
      jobId,
      counts: normalizePurchaseSyncCounts(jobStatus.result || {}),
      jobStatus,
    };
  } catch (err) {
    if (err.response?.status !== 404) {
      throw err;
    }
  }

  if (onStarted) {
    onStarted({ mode: 'sync' });
  }
  const payload = await client
    .post(
      '/ksef/sync/purchases',
      {
        force_full: forceFull,
        incremental: false,
        nip,
        date_from: dateFrom,
        date_to: dateTo,
        days_back: daysBack,
      },
      { timeout: 600000 },
    )
    .then((r) => r.data);

  const rawCounts = payload?.counts || payload;
  return {
    mode: 'sync',
    counts: normalizePurchaseSyncCounts(rawCounts),
    report: payload,
  };
}

export const ksefApi = {
  getStatus,
  markStatusMutation,
  runPurchaseSync,
  normalizePurchaseSyncCounts,
  purchaseSyncDateRange,

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

  /** @deprecated Użyj runPurchaseSync — synchroniczny endpoint przekracza timeout UI. */
  syncPurchasesNow: (forceFull = false, nip = null) =>
    client
      .post('/ksef/sync/purchases', {
        force_full: forceFull,
        incremental: false,
        ...(nip ? { nip } : {}),
      })
      .then((r) => r.data),
};
