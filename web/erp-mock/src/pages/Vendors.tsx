/**
 * Acme's vendor master, read through the typed API client.
 *
 * The first screen in the web lane that calls the REST API rather than reading
 * Firestore, so it is also the proof that the generated client works: against
 * the Prism mock today, against Cloud Run once VITE_API_BASE changes.
 */

import {
  ErrorState,
  LoadingState,
  api,
  formatIfsc,
  maskAccount,
  problemMessage,
  toProblem,
} from '@pramaan/shared';
import { type ReactNode, useCallback, useEffect, useState } from 'react';

interface VendorRow {
  vendor_id: string;
  legal_name: string;
  gstin?: string | null;
  account_last4: string;
  ifsc: string;
  bank_changed_at?: string | null;
  is_new_payee: boolean;
  months_of_history?: number;
}

export function Vendors(): ReactNode {
  const [rows, setRows] = useState<VendorRow[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    setProblem(null);
    setRows(null);
    try {
      const { data, error, response } = await api().GET('/vendors');
      if (error || !data) {
        setProblem(problemMessage(toProblem(error, response?.status)));
        return;
      }
      setRows((data.vendors ?? []) as VendorRow[]);
    } catch (caught) {
      setProblem(problemMessage(toProblem(caught)));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (problem) {
    return (
      <ErrorState
        title="We could not load the vendor master"
        error={new Error(problem)}
        onRetry={() => void load()}
      />
    );
  }

  if (rows === null) return <LoadingState label="Loading vendors" />;

  return (
    <div>
      <h1>Vendors</h1>
      <p className="erp-hint" style={{ marginBottom: 10 }}>
        Acme&rsquo;s vendor master. Pramaan compares every payment against it.
      </p>

      {rows.length === 0 ? (
        <div className="erp-empty">The vendor master is empty.</div>
      ) : (
        <div className="erp-table-wrap">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>GSTIN</th>
                <th>Account</th>
                <th>IFSC</th>
                <th>History</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((vendor) => (
                <tr key={vendor.vendor_id}>
                  <td>{vendor.legal_name}</td>
                  <td>{vendor.gstin ?? '—'}</td>
                  <td>{maskAccount(vendor.account_last4)}</td>
                  <td>{formatIfsc(vendor.ifsc)}</td>
                  <td>
                    {vendor.months_of_history
                      ? `${vendor.months_of_history} months`
                      : 'No history'}
                  </td>
                  <td>
                    {vendor.is_new_payee ? 'New payee. ' : ''}
                    {vendor.bank_changed_at ? 'Bank details changed recently.' : ''}
                    {!vendor.is_new_payee && !vendor.bank_changed_at ? '—' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
