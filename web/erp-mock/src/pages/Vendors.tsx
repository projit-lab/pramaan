/**
 * The vendor master, read through the typed API client.
 *
 * This is the first screen in the web lane that calls the REST API rather than
 * reading Firestore, so it is also the proof that the generated client works:
 * against the Prism mock today, against Prajit's Cloud Run service once
 * VITE_API_BASE changes.
 */

import {
  EmptyState,
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
        title="Could not load the vendor master"
        error={new Error(problem)}
        onRetry={() => void load()}
      />
    );
  }

  if (rows === null) return <LoadingState label="Loading vendors" />;

  if (rows.length === 0) {
    return <EmptyState title="No vendors yet" detail="The vendor master is empty." />;
  }

  return (
    <div className="pr-stack">
      <div>
        <h1 className="pr-h1">Vendors</h1>
        <p className="pr-muted">
          Acme&rsquo;s vendor master. Pramaan compares every payment against it.
        </p>
      </div>

      <table className="pr-table">
        <thead>
          <tr>
            <th scope="col">Vendor</th>
            <th scope="col">GSTIN</th>
            <th scope="col">Bank account</th>
            <th scope="col">History</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((vendor) => (
            <tr key={vendor.vendor_id}>
              <td>
                {vendor.legal_name}
                {vendor.is_new_payee ? (
                  <span className="pr-badge pr-badge--amber">New payee</span>
                ) : null}
                {vendor.bank_changed_at ? (
                  <span className="pr-badge pr-badge--amber">Bank details changed</span>
                ) : null}
              </td>
              <td>{vendor.gstin ?? <span className="pr-muted">Not on record</span>}</td>
              <td>
                {maskAccount(vendor.account_last4)}
                <div className="pr-fineprint">{formatIfsc(vendor.ifsc)}</div>
              </td>
              <td>
                {vendor.months_of_history
                  ? `${vendor.months_of_history} months`
                  : 'No payment history'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
