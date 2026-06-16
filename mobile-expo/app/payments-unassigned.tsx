import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import {
  allocatePayment,
  contractorNameFromListItem,
  fetchInvoicePaymentHistory,
  fetchPaymentsForAssignment,
  formatIssueDate,
  InvoiceListItem,
  invoiceDisplayNumber,
  invoiceListDisplayAmount,
  parseAmount,
  PaymentAllocation,
  reversePaymentAllocation,
  searchInvoices,
  UnassignedPayment,
  unassignedPaymentCounterparty,
  unassignedPaymentDisplayAmount,
} from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { SearchBar } from '@/components/SearchBar';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

type ModalMode = 'assign' | 'reassign_old' | 'reassign_new';

function canAssign(payment: UnassignedPayment): boolean {
  return parseAmount(unassignedPaymentDisplayAmount(payment)) > 0;
}

function canReassign(payment: UnassignedPayment): boolean {
  const status = payment.match_status?.toLowerCase();
  return status === 'partial' || status === 'manual_review' || status === 'matched';
}

export default function PaymentsUnassignedScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const [payments, setPayments] = useState<UnassignedPayment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [activePayment, setActivePayment] = useState<UnassignedPayment | null>(null);
  const [modalMode, setModalMode] = useState<ModalMode | null>(null);
  const [invoiceQuery, setInvoiceQuery] = useState('');
  const [invoiceResults, setInvoiceResults] = useState<InvoiceListItem[]>([]);
  const [invoiceSearchLoading, setInvoiceSearchLoading] = useState(false);
  const [selectedAllocation, setSelectedAllocation] = useState<PaymentAllocation | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPaymentsForAssignment();
      setPayments(res.items);
      setTotal(res.total);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setPayments([]);
      setTotal(0);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać płatności');
    } finally {
      setLoading(false);
    }
  }, [logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!modalMode) {
      return;
    }
    const q = invoiceQuery.trim();
    if (q.length < 2) {
      setInvoiceResults([]);
      setInvoiceSearchLoading(false);
      return;
    }
    let cancelled = false;
    setInvoiceSearchLoading(true);
    setModalError(null);
    const timer = setTimeout(async () => {
      try {
        const items = await searchInvoices(q);
        if (!cancelled) {
          setInvoiceResults(items);
        }
      } catch (err) {
        if (!cancelled) {
          if (isAuthFailure(err)) {
            logout();
            router.replace('/login');
            return;
          }
          setModalError(err instanceof Error ? err.message : 'Nie udało się wyszukać faktur');
          setInvoiceResults([]);
        }
      } finally {
        if (!cancelled) {
          setInvoiceSearchLoading(false);
        }
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [invoiceQuery, modalMode, logout, router]);

  const totalAmount = useMemo(
    () => payments.reduce((sum, p) => sum + parseAmount(unassignedPaymentDisplayAmount(p)), 0),
    [payments],
  );

  const subtitle =
    !loading && !error ? `${total} transakcji · ${formatPln(totalAmount)}` : undefined;

  const closeModal = () => {
    setActivePayment(null);
    setModalMode(null);
    setInvoiceQuery('');
    setInvoiceResults([]);
    setSelectedAllocation(null);
    setModalError(null);
    setActionLoading(false);
  };

  const openAssignModal = (payment: UnassignedPayment) => {
    setActivePayment(payment);
    setModalMode('assign');
    setInvoiceQuery('');
    setInvoiceResults([]);
    setSelectedAllocation(null);
    setModalError(null);
  };

  const openReassignModal = (payment: UnassignedPayment) => {
    setActivePayment(payment);
    setModalMode('reassign_old');
    setInvoiceQuery('');
    setInvoiceResults([]);
    setSelectedAllocation(null);
    setModalError(null);
  };

  const handleAuthError = (err: unknown): boolean => {
    if (isAuthFailure(err)) {
      logout();
      router.replace('/login');
      return true;
    }
    return false;
  };

  const handleAssign = async (payment: UnassignedPayment, invoice: InvoiceListItem) => {
    setActionLoading(true);
    setModalError(null);
    try {
      const amount = unassignedPaymentDisplayAmount(payment);
      await allocatePayment(payment.id, invoice.id, amount);
      closeModal();
      setSuccessMessage(`Przypisano ${formatPln(amount)} do ${invoiceDisplayNumber(invoice)}`);
      await load();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      setModalError(err instanceof Error ? err.message : 'Nie udało się przypisać płatności');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReassignOldInvoice = async (payment: UnassignedPayment, invoice: InvoiceListItem) => {
    setActionLoading(true);
    setModalError(null);
    try {
      const history = await fetchInvoicePaymentHistory(invoice.id);
      const allocation = history.find(
        (item) => item.transaction_id === payment.id && !item.is_reversed,
      );
      if (!allocation) {
        setModalError('Brak aktywnego przypisania tej płatności do wybranej faktury');
        return;
      }
      setSelectedAllocation(allocation);
      setModalMode('reassign_new');
      setInvoiceQuery('');
      setInvoiceResults([]);
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      setModalError(err instanceof Error ? err.message : 'Nie udało się pobrać historii płatności');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReassignNewInvoice = async (payment: UnassignedPayment, invoice: InvoiceListItem) => {
    if (!selectedAllocation) {
      setModalError('Brak przypisania do zmiany');
      return;
    }
    setActionLoading(true);
    setModalError(null);
    try {
      await reversePaymentAllocation(selectedAllocation.id);
      await allocatePayment(payment.id, invoice.id, selectedAllocation.allocated_amount);
      closeModal();
      setSuccessMessage(
        `Zmieniono przypisanie na ${invoiceDisplayNumber(invoice)} (${formatPln(selectedAllocation.allocated_amount)})`,
      );
      await load();
    } catch (err) {
      if (handleAuthError(err)) {
        return;
      }
      setModalError(err instanceof Error ? err.message : 'Nie udało się zmienić przypisania');
    } finally {
      setActionLoading(false);
    }
  };

  const handleInvoicePick = async (invoice: InvoiceListItem) => {
    if (!activePayment || actionLoading) {
      return;
    }
    if (modalMode === 'assign') {
      await handleAssign(activePayment, invoice);
      return;
    }
    if (modalMode === 'reassign_old') {
      await handleReassignOldInvoice(activePayment, invoice);
      return;
    }
    if (modalMode === 'reassign_new') {
      await handleReassignNewInvoice(activePayment, invoice);
    }
  };

  const modalTitle =
    modalMode === 'assign'
      ? 'Wybierz fakturę'
      : modalMode === 'reassign_old'
        ? 'Faktura z błędnym przypisaniem'
        : modalMode === 'reassign_new'
          ? 'Nowa faktura'
          : '';

  return (
    <ScreenShell title="Płatności do przypisania" subtitle={subtitle} showBack scroll>
      {successMessage ? (
        <View style={styles.successBox}>
          <Text style={styles.successText}>{successMessage}</Text>
          <Pressable onPress={() => setSuccessMessage(null)}>
            <Text style={styles.successDismiss}>Zamknij</Text>
          </Pressable>
        </View>
      ) : null}

      {loading ? (
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie płatności…</Text>
        </View>
      ) : null}

      {!loading && error ? (
        <View style={styles.stateBox}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryText}>Spróbuj ponownie</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !error && payments.length === 0 ? (
        <Text style={styles.emptyText}>Brak płatności do przypisania</Text>
      ) : null}

      {!loading && !error
        ? payments.map((p) => (
            <View key={p.id} style={styles.card}>
              <View style={styles.cardTop}>
                <Text style={styles.counterparty}>{unassignedPaymentCounterparty(p)}</Text>
                <Text style={styles.amount}>{formatPln(unassignedPaymentDisplayAmount(p))}</Text>
              </View>
              <Text style={styles.title}>{p.title?.trim() || '—'}</Text>
              <Text style={styles.date}>{formatIssueDate(p.transaction_date)}</Text>
              {p.counterparty_account ? (
                <Text style={styles.account}>{p.counterparty_account}</Text>
              ) : null}
              <View style={styles.actions}>
                {canAssign(p) ? (
                  <Pressable style={styles.actionBtn} onPress={() => openAssignModal(p)}>
                    <Text style={styles.actionBtnText}>Przypisz do faktury →</Text>
                  </Pressable>
                ) : null}
                {canReassign(p) ? (
                  <Pressable style={styles.actionBtnSecondary} onPress={() => openReassignModal(p)}>
                    <Text style={styles.actionBtnSecondaryText}>Zmień przypisanie</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
          ))
        : null}

      <Modal visible={modalMode !== null} animationType="slide" transparent onRequestClose={closeModal}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{modalTitle}</Text>
            {activePayment ? (
              <Text style={styles.modalMeta}>
                {unassignedPaymentCounterparty(activePayment)} ·{' '}
                {formatPln(unassignedPaymentDisplayAmount(activePayment))}
              </Text>
            ) : null}

            <SearchBar
              value={invoiceQuery}
              onChangeText={setInvoiceQuery}
              placeholder="Numer faktury lub kontrahent…"
            />

            {invoiceSearchLoading ? (
              <ActivityIndicator color={colors.gold} style={styles.modalSpinner} />
            ) : null}

            {modalError ? <Text style={styles.modalError}>{modalError}</Text> : null}

            {actionLoading ? (
              <View style={styles.modalActionBox}>
                <ActivityIndicator color={colors.gold} />
                <Text style={styles.modalActionText}>Przetwarzanie…</Text>
              </View>
            ) : (
              invoiceResults.map((inv) => (
                <Pressable
                  key={inv.id}
                  style={styles.invoiceRow}
                  onPress={() => handleInvoicePick(inv)}
                >
                  <Text style={styles.invoiceNumber}>{invoiceDisplayNumber(inv)}</Text>
                  <Text style={styles.invoiceContractor}>{contractorNameFromListItem(inv)}</Text>
                  <Text style={styles.invoiceAmount}>{formatPln(invoiceListDisplayAmount(inv))}</Text>
                </Pressable>
              ))
            )}

            {invoiceQuery.trim().length >= 2 &&
            !invoiceSearchLoading &&
            !actionLoading &&
            invoiceResults.length === 0 &&
            !modalError ? (
              <Text style={styles.modalEmpty}>Brak faktur dla podanego wyszukiwania</Text>
            ) : null}

            <Pressable style={styles.modalCloseBtn} onPress={closeModal} disabled={actionLoading}>
              <Text style={styles.modalCloseText}>Anuluj</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  stateBox: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingVertical: 32,
  },
  stateText: { color: colors.textMuted, fontSize: 16 },
  errorText: { color: colors.danger, fontSize: 16, textAlign: 'center' },
  retryBtn: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  retryText: { color: colors.gold, fontSize: 15, fontWeight: '600' },
  emptyText: { color: colors.textMuted, fontSize: 15, paddingVertical: 8 },
  successBox: {
    backgroundColor: colors.goldGlow,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.goldDim,
    padding: 12,
    gap: 6,
  },
  successText: { color: colors.text, fontSize: 14 },
  successDismiss: { color: colors.gold, fontSize: 13, fontWeight: '600' },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 6,
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  counterparty: { color: colors.text, fontSize: 16, fontWeight: '700', flex: 1 },
  amount: { color: colors.gold, fontSize: 17, fontWeight: '800' },
  title: { color: colors.textMuted, fontSize: 13 },
  date: { color: colors.textDim, fontSize: 11 },
  account: { color: colors.textDim, fontSize: 10 },
  actions: { marginTop: 6, paddingTop: 8, borderTopWidth: 1, borderTopColor: colors.border, gap: 8 },
  actionBtn: { paddingVertical: 4 },
  actionBtnText: { color: colors.gold, fontSize: 13, fontWeight: '600' },
  actionBtnSecondary: { paddingVertical: 2 },
  actionBtnSecondaryText: { color: colors.textMuted, fontSize: 12, fontWeight: '600' },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 16,
    gap: 10,
    maxHeight: '85%',
  },
  modalTitle: { color: colors.text, fontSize: 18, fontWeight: '700' },
  modalMeta: { color: colors.textMuted, fontSize: 13 },
  modalSpinner: { marginVertical: 8 },
  modalError: { color: colors.danger, fontSize: 14 },
  modalActionBox: { alignItems: 'center', gap: 8, paddingVertical: 12 },
  modalActionText: { color: colors.textMuted, fontSize: 14 },
  modalEmpty: { color: colors.textDim, fontSize: 13, fontStyle: 'italic' },
  invoiceRow: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    gap: 3,
  },
  invoiceNumber: { color: colors.text, fontSize: 14, fontWeight: '600' },
  invoiceContractor: { color: colors.textMuted, fontSize: 12 },
  invoiceAmount: { color: colors.gold, fontSize: 13, fontWeight: '700' },
  modalCloseBtn: {
    marginTop: 4,
    paddingVertical: 12,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  modalCloseText: { color: colors.textMuted, fontSize: 15, fontWeight: '600' },
});
