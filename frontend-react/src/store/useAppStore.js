import { create } from 'zustand';
import { persist } from 'zustand/middleware';

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

export const useAppStore = create(
  persist(
    (set) => ({
      // NIP sprzedawcy zapamiętany do operacji KSeF
      sellerNip: '',
      ksefConnection: disconnectedKsefConnection(),

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
