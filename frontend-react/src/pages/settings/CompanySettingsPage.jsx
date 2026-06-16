import { useEffect, useState } from 'react';
import { settingsApi } from '../../api/settings';
import styles from './CompanySettingsPage.module.css';

function formatBankAccountForInput(digits) {
  const d = String(digits ?? '').replace(/\s/g, '');
  if (d.length !== 26) return d;
  return `${d.slice(0, 2)} ${d.slice(2, 6)} ${d.slice(6, 10)} ${d.slice(10, 14)} ${d.slice(14, 18)} ${d.slice(18, 22)} ${d.slice(22, 26)}`;
}

function sanitizeBankAccountInput(value) {
  return String(value ?? '').replace(/[^\d\s]/g, '').slice(0, 32);
}

const EMPTY_FORM = {
  seller_nip: '',
  seller_name: '',
  seller_street: '',
  seller_building_no: '',
  seller_apartment_no: '',
  seller_postal_code: '',
  seller_city: '',
  seller_country: 'PL',
  seller_bank_account: '',
};

export default function CompanySettingsPage() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    settingsApi
      .get()
      .then((data) => {
        if (cancelled) return;
        setForm({
          seller_nip: data.seller_nip ?? '',
          seller_name: data.seller_name ?? '',
          seller_street: data.seller_street ?? '',
          seller_building_no: data.seller_building_no ?? '',
          seller_apartment_no: data.seller_apartment_no ?? '',
          seller_postal_code: data.seller_postal_code ?? '',
          seller_city: data.seller_city ?? '',
          seller_country: data.seller_country ?? 'PL',
          seller_bank_account: formatBankAccountForInput(data.seller_bank_account),
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.error?.message
            ?? err.response?.data?.detail
            ?? 'Nie udało się pobrać ustawień',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: '' }));
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    setFieldErrors({});

    const payload = {
      ...form,
      seller_bank_account: form.seller_bank_account.trim() || null,
    };

    try {
      const data = await settingsApi.update(payload);
      setForm({
        seller_nip: data.seller_nip ?? '',
        seller_name: data.seller_name ?? '',
        seller_street: data.seller_street ?? '',
        seller_building_no: data.seller_building_no ?? '',
        seller_apartment_no: data.seller_apartment_no ?? '',
        seller_postal_code: data.seller_postal_code ?? '',
        seller_city: data.seller_city ?? '',
        seller_country: data.seller_country ?? 'PL',
        seller_bank_account: formatBankAccountForInput(data.seller_bank_account),
      });
      setSuccess('Ustawienia zapisane.');
    } catch (err) {
      const apiError = err.response?.data?.error?.message ?? err.response?.data?.detail;
      if (typeof apiError === 'string' && apiError.includes('seller_bank_account')) {
        setFieldErrors({ seller_bank_account: apiError });
      } else if (Array.isArray(err.response?.data?.detail)) {
        const next = {};
        err.response.data.detail.forEach((item) => {
          const field = item.loc?.[item.loc.length - 1];
          if (field) next[field] = item.msg;
        });
        setFieldErrors(next);
        setError('Popraw błędy w formularzu.');
      } else {
        setError(apiError ?? 'Nie udało się zapisać ustawień');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.page}>
        <h1 className={styles.pageTitle}>Ustawienia firmy</h1>
        <p className={styles.loading}>Ładowanie…</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Ustawienia firmy</h1>
      <p className={styles.subtitle}>
        Dane sprzedawcy używane na fakturach sprzedaży oraz numer rachunku bankowego Ikony.
      </p>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <form className={styles.form} onSubmit={handleSubmit}>
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Dane sprzedawcy</h2>
          <div className={styles.grid2}>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_nip">NIP</label>
              <input
                id="seller_nip"
                className="input"
                value={form.seller_nip}
                maxLength={10}
                onChange={(e) => updateField('seller_nip', e.target.value.replace(/\D/g, ''))}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_name">Nazwa</label>
              <input
                id="seller_name"
                className="input"
                value={form.seller_name}
                onChange={(e) => updateField('seller_name', e.target.value)}
              />
            </div>
          </div>
          <div className={styles.grid3}>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_street">Ulica</label>
              <input
                id="seller_street"
                className="input"
                value={form.seller_street}
                onChange={(e) => updateField('seller_street', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_building_no">Nr budynku</label>
              <input
                id="seller_building_no"
                className="input"
                value={form.seller_building_no}
                onChange={(e) => updateField('seller_building_no', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_apartment_no">Nr lokalu</label>
              <input
                id="seller_apartment_no"
                className="input"
                value={form.seller_apartment_no}
                onChange={(e) => updateField('seller_apartment_no', e.target.value)}
              />
            </div>
          </div>
          <div className={styles.grid3}>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_postal_code">Kod pocztowy</label>
              <input
                id="seller_postal_code"
                className="input"
                value={form.seller_postal_code}
                onChange={(e) => updateField('seller_postal_code', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_city">Miasto</label>
              <input
                id="seller_city"
                className="input"
                value={form.seller_city}
                onChange={(e) => updateField('seller_city', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="seller_country">Kraj</label>
              <input
                id="seller_country"
                className="input"
                value={form.seller_country}
                maxLength={2}
                onChange={(e) => updateField('seller_country', e.target.value.toUpperCase())}
              />
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Rachunek bankowy</h2>
          <div className="form-group">
            <label className="form-label" htmlFor="seller_bank_account">Rachunek bankowy</label>
            <input
              id="seller_bank_account"
              className="input"
              placeholder="12 3456 7890 1234 5678 9012 3456"
              value={form.seller_bank_account}
              onChange={(e) => updateField('seller_bank_account', sanitizeBankAccountInput(e.target.value))}
            />
            <span className={styles.fieldHint}>
              26 cyfr — spacje są opcjonalne, zostaną usunięte przy zapisie.
            </span>
            {fieldErrors.seller_bank_account && (
              <span className="form-error">{fieldErrors.seller_bank_account}</span>
            )}
          </div>
        </section>

        <div className={styles.actions}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? <span className="spinner" /> : null}
            Zapisz ustawienia
          </button>
        </div>
      </form>
    </div>
  );
}
