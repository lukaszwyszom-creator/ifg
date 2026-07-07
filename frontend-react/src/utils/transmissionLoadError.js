/** Diagnostyka błędów ładowania Monitora KSeF — log do konsoli, komunikat dla użytkownika. */
export function resolveTransmissionLoadError(err) {
  const status = err?.response?.status;
  const data = err?.response?.data;
  const url = err?.config?.url ?? '/transmissions/';
  const authHeader = err?.config?.headers?.Authorization;

  console.error('[Monitor KSeF] Błąd ładowania danych:', {
    url,
    status,
    responseData: data,
    authHeaderPresent: !!authHeader,
    authHeaderPrefix: authHeader ? `${String(authHeader).slice(0, 15)}…` : 'brak',
    err,
  });

  if (status === 401) {
    return 'Brak autoryzacji — zaloguj się ponownie, aby zobaczyć Monitor KSeF.';
  }
  if (status === 403) {
    return 'Brak uprawnień do podglądu Monitora KSeF.';
  }
  if (status === 404) {
    return 'Endpoint Monitora KSeF nie został znaleziony — sprawdź wersję backendu.';
  }
  if (status === 500) {
    const serverMsg = data?.error?.message || data?.detail;
    const suffix = serverMsg ? ` (${String(serverMsg).slice(0, 120)})` : '';
    return `Błąd serwera podczas ładowania Monitora KSeF${suffix}. Spróbuj odświeżyć za chwilę.`;
  }
  if (status) {
    return `Nie udało się załadować Monitora KSeF (HTTP ${status}). Sprawdź połączenie z serwerem.`;
  }
  return 'Nie udało się załadować Monitora KSeF. Sprawdź połączenie z serwerem.';
}
