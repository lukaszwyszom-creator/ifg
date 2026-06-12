export const MISSING_KSEF_SYNC_NIP_MESSAGE = 'Brak NIP sprzedawcy — uzupełnij w ustawieniach.';

export async function resolveKsefSyncNip(
  sellerNip,
  { getSettings, getActiveSession },
) {
  if (sellerNip?.length === 10) return sellerNip;
  try {
    const settings = await getSettings();
    if (settings?.seller_nip?.length === 10) return settings.seller_nip;
  } catch {
    // brak ustawień — spróbuj aktywnej sesji
  }
  try {
    const session = await getActiveSession(sellerNip || undefined);
    if (session?.nip?.length === 10) return session.nip;
  } catch {
    // brak sesji
  }
  return '';
}

export function evaluateKsefSyncTrigger({
  isConnected,
  syncBusy,
  syncRunning,
  nip,
}) {
  if (!isConnected || syncBusy || syncRunning) {
    return { action: 'blocked' };
  }
  if (nip.length !== 10) {
    return { action: 'user_error', message: MISSING_KSEF_SYNC_NIP_MESSAGE };
  }
  return { action: 'proceed', nip };
}
