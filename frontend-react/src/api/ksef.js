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
export const PURCHASE_SYNC_ENQUEUE_ENDPOINT = '/api/v1/ksef-sessions/sync-purchase';
export const PURCHASE_SYNC_JOB_STATUS_PREFIX = '/api/v1/ksef-sessions/sync-purchase/jobs/';

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

/** Produkcyjnie bezpieczny log diagnostyczny (bez tokenów — tylko endpoint/NIP/daty/jobId). */
function logPurchaseSyncPath(step, detail) {
  console.info('[ksef-purchase-sync]', step, detail ?? '');
}

export function formatPurchaseSyncError(err, endpoint = PURCHASE_SYNC_ENQUEUE_ENDPOINT) {
  const status = err.response?.status ?? (err.timedOut ? 'timeout' : '—');
  const apiMsg = err.response?.data?.error?.message ?? err.response?.data?.detail;
  const message = apiMsg ?? err.message ?? 'Unknown error';
  return `${status} ${endpoint}: ${message}`;
}

function attachSyncErrorMeta(err, endpoint) {
  err.syncEndpoint = endpoint;
  return err;
}

async function pollPurchaseSyncJob(
  jobId,
  getJobStatus,
  {
    onProgress,
    intervalMs = PURCHASE_SYNC_POLL_INTERVAL_MS,
    maxAttempts = PURCHASE_SYNC_MAX_POLL_ATTEMPTS,
  } = {},
) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await sleep(intervalMs);
    const jobStatus = await getJobStatus(jobId);
    if (onProgress) {
      onProgress(jobStatus);
    }
    if (jobStatus.status === 'done') {
      return jobStatus;
    }
    if (jobStatus.status === 'failed') {
      const err = new Error(jobStatus.error || 'Synchronizacja zakończona błędem.');
      err.jobStatus = jobStatus;
      attachSyncErrorMeta(err, `${PURCHASE_SYNC_JOB_STATUS_PREFIX}${jobId}`);
      throw err;
    }
  }
  const err = new Error('Przekroczono czas oczekiwania na synchronizację KSeF.');
  err.timedOut = true;
  attachSyncErrorMeta(err, `${PURCHASE_SYNC_JOB_STATUS_PREFIX}${jobId}`);
  throw err;
}

async function syncPurchasesNowFallback(
  nip,
  { dateFrom, dateTo, daysBack, forceFull },
) {
  logPurchaseSyncPath('fallback-sync', 'POST /ksef/sync/purchases (404 na job API)');
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

/**
 * Uruchamia synchronizację zakupów KSeF bez blokowania UI na cały import.
 * Zawsze zaczyna od async job (POST /ksef-sessions/sync-purchase).
 * Fallback synchroniczny tylko gdy enqueue zwróci HTTP 404.
 */
async function runPurchaseSync(
  nip,
  syncPurchaseInvoices,
  getSyncPurchaseJobStatus,
  {
    daysBack = PURCHASE_SYNC_DAYS_BACK,
    forceFull = false,
    onStarted,
    onProgress,
  } = {},
) {
  const { dateFrom, dateTo } = purchaseSyncDateRange(daysBack);

  let jobId;
  try {
    logPurchaseSyncPath('enqueue', {
      endpoint: PURCHASE_SYNC_ENQUEUE_ENDPOINT,
      nip,
      dateFrom,
      dateTo,
    });
    const enqueueResponse = await syncPurchaseInvoices(nip, dateFrom, dateTo);
    jobId = enqueueResponse.job_id;
    if (!jobId) {
      throw attachSyncErrorMeta(
        new Error('Brak job_id w odpowiedzi POST /ksef-sessions/sync-purchase'),
        PURCHASE_SYNC_ENQUEUE_ENDPOINT,
      );
    }
    logPurchaseSyncPath('enqueue-ok', {
      endpoint: PURCHASE_SYNC_ENQUEUE_ENDPOINT,
      nip,
      dateFrom,
      dateTo,
      jobId,
    });
  } catch (err) {
    if (err.response?.status === 404) {
      logPurchaseSyncPath('fallback-404', PURCHASE_SYNC_ENQUEUE_ENDPOINT);
      if (onStarted) {
        onStarted({ mode: 'sync' });
      }
      return syncPurchasesNowFallback(nip, { dateFrom, dateTo, daysBack, forceFull });
    }
    logPurchaseSyncPath('enqueue-error', {
      endpoint: PURCHASE_SYNC_ENQUEUE_ENDPOINT,
      status: err.response?.status,
      message: err.message,
    });
    attachSyncErrorMeta(err, PURCHASE_SYNC_ENQUEUE_ENDPOINT);
    throw err;
  }

  logPurchaseSyncPath('async-started', { jobId });
  if (onStarted) {
    onStarted({ mode: 'async', jobId });
  }

  const jobStatus = await pollPurchaseSyncJob(jobId, getSyncPurchaseJobStatus, { onProgress });
  logPurchaseSyncPath('async-done', { jobId, status: jobStatus.status });
  return {
    mode: 'async',
    jobId,
    counts: normalizePurchaseSyncCounts(jobStatus.result || {}),
    jobStatus,
  };
}

export const ksefApi = {
  getStatus,
  markStatusMutation,
  normalizePurchaseSyncCounts,
  purchaseSyncDateRange,
  formatPurchaseSyncError,

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

  /** Jedyny punkt wejścia UI dla „Odśwież KSeF” — zawsze async job, fallback sync tylko przy 404. */
  runPurchaseSync: (nip, options = {}) =>
    runPurchaseSync(
      nip,
      (n, from, to) => ksefApi.syncPurchaseInvoices(n, from, to),
      (jobId) => ksefApi.getSyncPurchaseJobStatus(jobId),
      options,
    ),

  /** @deprecated Nie używać z UI — tylko wewnętrzny fallback runPurchaseSync (404). */
  syncPurchasesNow: (forceFull = false, nip = null) =>
    client
      .post('/ksef/sync/purchases', {
        force_full: forceFull,
        incremental: false,
        ...(nip ? { nip } : {}),
      })
      .then((r) => r.data),
};
