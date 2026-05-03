import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { invoicesApi } from '../api/invoices';
import { buildInvoicePoolKey, buildInvoicePoolQuery } from '../components/dashboard/dashboardQuery';

function disconnectedKsefConnection() {
  return {
    ui_status: 'DISCONNECTED',
    details: {
      reason: 'NO_SESSION',
      has_session: false,
      session_expires_at: null,
      last_error: null,
    },
  };
}

function currentMonthValue() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

function emptyInvoicePool() {
  return { sale: {}, purchase: {} };
}

const INVOICE_POOL_TTL_MS = 60_000;

async function fetchInvoicesAllPages(baseQuery) {
  const size = 100;
  let page = 1;
  let total = 0;
  const items = [];

  do {
    const response = await invoicesApi.list({ ...baseQuery, page, size });
    const pageItems = Array.isArray(response?.items) ? response.items : [];
    total = Number(response?.total ?? pageItems.length);
    items.push(...pageItems);
    if (page * size >= total) break;
    page += 1;
  } while (true);

  return items;
}

export const useAppStore = create(
  persist(
    (set, get) => ({
      // NIP sprzedawcy zapamiętany do operacji KSeF
      sellerNip: '',
      ksefConnection: disconnectedKsefConnection(),

      invoicePool: emptyInvoicePool(),
      invoicePoolLoading: {},
      invoicePoolErrors: {},

      // Filtry wspólne
      filters: {
        month: currentMonthValue(),
        status: '',
        issue_date_from: '',
        issue_date_to: '',
        contractor: '',
      },

      setSellerNip: (nip) => set({ sellerNip: nip }),
      setKsefConnection: (nextConnection) => set((state) => {
        if (import.meta.env.DEV && state.ksefConnection.ui_status !== nextConnection.ui_status) {
          console.log('KSeF status:', state.ksefConnection.ui_status, '→', nextConnection.ui_status);
        }
        return { ksefConnection: nextConnection };
      }),

      setFilters: (patch) =>
        set((s) => ({ filters: { ...s.filters, ...patch } })),

      loadInvoicePool: async ({ direction = 'sale', filters = {}, options = {}, force = false } = {}) => {
        const query = buildInvoicePoolQuery(filters, direction, options);
        const key = buildInvoicePoolKey(query);
        const requestKey = `${direction}:${key}`;

        const inFlight = get().invoicePoolLoading?.[requestKey];
        if (inFlight) {
          return inFlight;
        }

        if (!force) {
          const cacheEntry = get().invoicePool?.[direction]?.[key];
          const cachedItems = cacheEntry?.items;
          const loadedAt = Number(cacheEntry?.loadedAt ?? 0);
          const isFresh = loadedAt > 0 && Date.now() - loadedAt < INVOICE_POOL_TTL_MS;
          if (Array.isArray(cachedItems) && isFresh) {
            return cachedItems;
          }
        }

        const request = (async () => {
          try {
            const items = await fetchInvoicesAllPages(query);
            set((state) => {
              const byDirection = state.invoicePool?.[direction] || {};
              const nextDirectionPool = {
                ...byDirection,
                [key]: {
                  key,
                  query,
                  direction,
                  items,
                  total: items.length,
                  loadedAt: Date.now(),
                },
              };
              const nextErrors = { ...(state.invoicePoolErrors || {}) };
              delete nextErrors[requestKey];
              return {
                invoicePool: {
                  ...(state.invoicePool || emptyInvoicePool()),
                  [direction]: nextDirectionPool,
                },
                invoicePoolErrors: nextErrors,
              };
            });
            return items;
          } catch (error) {
            set((state) => ({
              invoicePoolErrors: {
                ...(state.invoicePoolErrors || {}),
                [requestKey]: error,
              },
            }));
            throw error;
          } finally {
            set((state) => {
              const nextLoading = { ...(state.invoicePoolLoading || {}) };
              delete nextLoading[requestKey];
              return { invoicePoolLoading: nextLoading };
            });
          }
        })();

        set((state) => ({
          invoicePoolLoading: {
            ...(state.invoicePoolLoading || {}),
            [requestKey]: request,
          },
        }));

        return request;
      },

      refreshAllInvoicePools: async ({ force = true } = {}) => {
        const pool = get().invoicePool || emptyInvoicePool();
        const tasks = [];

        for (const direction of ['sale', 'purchase']) {
          const entries = Object.values(pool?.[direction] || {});
          for (const entry of entries) {
            const query = entry?.query;
            if (!query) continue;
            tasks.push(
              get().loadInvoicePool({
                direction,
                filters: {
                  month: '',
                  issue_date_from: query.issue_date_from || '',
                  issue_date_to: query.issue_date_to || '',
                  issue_date_before: query.issue_date_before || '',
                  status: query.status || '',
                  contractor: query.number_filter || '',
                },
                options: { defaultToCurrentMonth: false },
                force,
              }).catch(() => null)
            );
          }
        }

        if (tasks.length === 0) return;
        await Promise.all(tasks);
      },

      clearInvoicePool: () => set({ invoicePool: emptyInvoicePool(), invoicePoolLoading: {}, invoicePoolErrors: {} }),

      resetFilters: () =>
        set({
          filters: { month: currentMonthValue(), status: '', issue_date_from: '', issue_date_to: '', contractor: '' },
        }),
    }),
    {
      name: 'faktura-app',
      version: 2,
      migrate: (persistedState) => ({
        sellerNip: persistedState?.sellerNip ?? '',
        ksefConnection: disconnectedKsefConnection(),
      }),
      partialize: (s) => ({ sellerNip: s.sellerNip }),
    }
  )
);
