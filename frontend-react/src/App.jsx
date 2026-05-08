import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/useAuthStore';
import { useAppStore } from './store/useAppStore';
import AppLayout from './components/layout/AppLayout';
import LoginPage from './pages/LoginPage';
import SimpleView from './pages/simple/SimpleView';
import AdvancedDashboard from './pages/advanced/AdvancedDashboard';
import PaymentsPage from './pages/payments/PaymentsPage';
import StockPage from './pages/stock/StockPage';

function PrivateRoute({ children }) {
  const token = useAuthStore((s) => s.token);
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const refreshAllInvoicePools = useAppStore((s) => s.refreshAllInvoicePools);

  useEffect(() => {
    const handler = () => {
      refreshAllInvoicePools().catch(() => null);
    };
    window.addEventListener('ksef:invoices-synced', handler);
    return () => window.removeEventListener('ksef:invoices-synced', handler);
  }, [refreshAllInvoicePools]);

  return (
    <BrowserRouter basename="/ui">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/invoices" replace />} />
          <Route path="invoices" element={<SimpleView />} />
          <Route path="dashboard" element={<AdvancedDashboard />} />
          <Route path="simple" element={<Navigate to="/invoices" replace />} />
          <Route path="advanced" element={<Navigate to="/dashboard" replace />} />
          <Route path="payments" element={<PaymentsPage />} />
          <Route path="stock" element={<StockPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/invoices" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
