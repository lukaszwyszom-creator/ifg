export type Invoice = {
  id: string;
  number: string;
  direction: 'sale' | 'purchase';
  contractorName: string;
  contractorNip: string;
  issueDate: string;
  dueDate: string;
  gross: number;
  paid: number;
  status: 'paid' | 'partial' | 'unpaid';
  ksefNumber?: string;
  items: { name: string; qty: number; unit: string; net: number; vat: number }[];
  history: { date: string; label: string; amount?: number }[];
};

export type Debtor = {
  id: string;
  name: string;
  totalDue: number;
  overdueDue: number;
  invoicesCount: number;
  overdueInvoicesCount: number;
  lastNote: { date: string; time: string; text: string } | null;
  notes: { id: string; date: string; time: string; text: string }[];
  invoices: { invoiceId: string; number: string; issueDate: string; dueDate: string; amountDue: number; overdueDays: number | null }[];
};

export type UnassignedPayment = {
  id: string;
  date: string;
  counterparty: string;
  title: string;
  amount: number;
};

export const dashboardMock = {
  period: '2026-05',
  periodLabel: 'maj 2026',
  salesNet: 125430,
  purchaseNet: 48200,
  vatBalance: 8940,
  vatLabel: 'due' as 'due' | 'refund',
  debtors: { count: 7, total: 23100, overdue: 4850 },
  creditors: { count: 5, total: 8700, overdue: 1200 },
  unassigned: { count: 3, total: 12500 },
  ksef: {
    status: 'connected' as const,
    statusLabel: 'KSeF OK',
    newCount: 3,
    lastSync: '2026-05-22T08:02:00',
    lastSyncLabel: '22.05.2026, 08:02',
  },
  recentPurchases: [
    { id: 'p1', supplier: 'ORLEN S.A.', number: 'FZ/2026/05/1847', gross: 1842.5, date: '2026-05-28' },
    { id: 'p2', supplier: 'Orange Polska', number: 'FV/2026/05/991', gross: 489.0, date: '2026-05-27' },
    { id: 'p3', supplier: 'InPost Sp. z o.o.', number: 'FZ/2026/05/044', gross: 1250.0, date: '2026-05-26' },
  ],
};

export const salesInvoices: Invoice[] = [
  {
    id: 'inv-s1',
    number: 'FV/7/05/2026',
    direction: 'sale',
    contractorName: 'ABC Sp. z o.o.',
    contractorNip: '5250001001',
    issueDate: '2026-05-18',
    dueDate: '2026-06-01',
    gross: 2460,
    paid: 0,
    status: 'unpaid',
    items: [{ name: 'Usługa konsultingowa', qty: 10, unit: 'godz.', net: 2000, vat: 460 }],
    history: [{ date: '2026-05-18', label: 'Wystawiono fakturę' }],
  },
  {
    id: 'inv-s2',
    number: 'FV/6/05/2026',
    direction: 'sale',
    contractorName: 'Delta Trading',
    contractorNip: '7890002002',
    issueDate: '2026-05-10',
    dueDate: '2026-05-24',
    gross: 6150,
    paid: 3000,
    status: 'partial',
    items: [{ name: 'Szkolenie B2B', qty: 1, unit: 'szt.', net: 5000, vat: 1150 }],
    history: [
      { date: '2026-05-10', label: 'Wystawiono fakturę' },
      { date: '2026-05-15', label: 'Wpłata częściowa', amount: 3000 },
    ],
  },
  {
    id: 'inv-s3',
    number: 'FV/5/05/2026',
    direction: 'sale',
    contractorName: 'Gamma IT',
    contractorNip: '9510003003',
    issueDate: '2026-05-05',
    dueDate: '2026-05-19',
    gross: 1230,
    paid: 1230,
    status: 'paid',
    items: [{ name: 'Licencja roczna', qty: 1, unit: 'szt.', net: 1000, vat: 230 }],
    history: [
      { date: '2026-05-05', label: 'Wystawiono fakturę' },
      { date: '2026-05-12', label: 'Opłacono w całości', amount: 1230 },
    ],
  },
];

export const purchaseInvoices: Invoice[] = [
  {
    id: 'inv-p1',
    number: 'FZ/2026/05/1847',
    direction: 'purchase',
    contractorName: 'ORLEN S.A.',
    contractorNip: '7740001454',
    issueDate: '2026-05-28',
    dueDate: '2026-06-11',
    gross: 1842.5,
    paid: 0,
    status: 'unpaid',
    ksefNumber: 'KSeF-20260528-001',
    items: [{ name: 'Paliwo służbowe', qty: 1, unit: 'kpl.', net: 1498, vat: 344.5 }],
    history: [{ date: '2026-05-28', label: 'Pobrano z KSeF' }],
  },
  {
    id: 'inv-p2',
    number: 'FV/2026/05/991',
    direction: 'purchase',
    contractorName: 'Orange Polska',
    contractorNip: '5260250995',
    issueDate: '2026-05-27',
    dueDate: '2026-06-10',
    gross: 489,
    paid: 489,
    status: 'paid',
    ksefNumber: 'KSeF-20260527-002',
    items: [{ name: 'Abonament telekom.', qty: 1, unit: 'm-c', net: 397.56, vat: 91.44 }],
    history: [
      { date: '2026-05-27', label: 'Pobrano z KSeF' },
      { date: '2026-05-28', label: 'Opłacono', amount: 489 },
    ],
  },
];

export const debtors: Debtor[] = [
  {
    id: 'd1',
    name: 'ABC Sp. z o.o.',
    totalDue: 12500,
    overdueDue: 4850,
    invoicesCount: 3,
    overdueInvoicesCount: 2,
    lastNote: { date: '12.06', time: '10:15', text: 'Obiecali przelew do piątku. Kontakt: K. Nowak.' },
    notes: [
      { id: 'n1', date: '12.06.2026', time: '10:15', text: 'Obiecali przelew do piątku. Kontakt: K. Nowak.' },
      { id: 'n2', date: '05.06.2026', time: '14:30', text: 'Brak odpowiedzi na mail — dzwonić ponownie.' },
      { id: 'n3', date: '28.05.2026', time: '09:00', text: 'Pierwsze przypomnienie wysłane.' },
    ],
    invoices: [
      { invoiceId: 'inv-s1', number: '45/2026', issueDate: '2026-04-15', dueDate: '2026-04-29', amountDue: 4850, overdueDays: 18 },
      { invoiceId: 'inv-s4', number: '38/2026', issueDate: '2026-03-10', dueDate: '2026-03-24', amountDue: 3200, overdueDays: 54 },
      { invoiceId: 'inv-s5', number: '52/2026', issueDate: '2026-05-20', dueDate: '2026-06-03', amountDue: 4450, overdueDays: null },
    ],
  },
  {
    id: 'd2',
    name: 'Delta Trading',
    totalDue: 6150,
    overdueDue: 0,
    invoicesCount: 1,
    overdueInvoicesCount: 0,
    lastNote: null,
    notes: [],
    invoices: [
      { invoiceId: 'inv-s2', number: 'FV/6/05/2026', issueDate: '2026-05-10', dueDate: '2026-05-24', amountDue: 3150, overdueDays: null },
    ],
  },
];

export const unassignedPayments: UnassignedPayment[] = [
  { id: 'pay1', date: '2026-05-21', counterparty: 'ABC Sp. z o.o.', title: 'FV 45/2026 częściowa', amount: 5000 },
  { id: 'pay2', date: '2026-05-20', counterparty: 'Nieznany nadawca', title: 'Przelew zbiorczy', amount: 4200 },
  { id: 'pay3', date: '2026-05-19', counterparty: 'Gamma IT', title: 'Zwrot nadpłaty', amount: 3300 },
];

export const allInvoices = [...salesInvoices, ...purchaseInvoices];

export function formatPln(value: number | string): string {
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (Number.isNaN(n)) return '0 zł';
  return `${n.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} zł`;
}

export function dueLabel(dueDate: string): string {
  const due = new Date(dueDate);
  const today = new Date('2026-05-22');
  const diff = Math.round((due.getTime() - today.getTime()) / 86400000);
  if (diff > 0) return `za ${diff} dni`;
  if (diff < 0) return `${Math.abs(diff)} dni po terminie`;
  return 'termin dziś';
}
