/**
 * New payment, in Acme's own ERP.
 *
 * This is where the boss scam starts. A clerk keys a payment, and the Pay
 * button goes to Pramaan rather than to the bank. Nothing here can approve
 * anything: the clerk's job ends at "sent for approval".
 *
 * The form carries the facts the policy engine needs to be any good: not just
 * who and how much, but **how the instruction arrived** and **what it said**.
 * Those two fields turn "a payment to a new payee" into "a payment to a new
 * payee, asked for on WhatsApp, marked urgent and confidential".
 */

import {
  ErrorState,
  InvalidRupeeInputError,
  LoadingState,
  api,
  fieldErrors,
  formatMoney,
  maskAccount,
  problemMessage,
  rupeesToPaise,
  toProblem,
  useAuth,
} from '@pramaan/shared';
import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface VendorRow {
  vendor_id: string;
  legal_name: string;
  account_last4: string;
  ifsc: string;
  is_new_payee: boolean;
  bank_changed_at?: string | null;
}

type Channel = 'portal' | 'email' | 'chat' | 'phone';

const CHANNELS: Array<{ value: Channel; label: string }> = [
  { value: 'portal', label: 'I keyed it from an invoice' },
  { value: 'email', label: 'Asked for by email' },
  { value: 'chat', label: 'Asked for on WhatsApp or chat' },
  { value: 'phone', label: 'Asked for by phone' },
];

/** SHA-256 of the uploaded invoice, computed in the browser. */
async function hashFile(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

export function NewPayment(): ReactNode {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [vendors, setVendors] = useState<VendorRow[] | null>(null);
  const [vendorsProblem, setVendorsProblem] = useState<string | null>(null);

  const [vendorId, setVendorId] = useState('');
  const [amount, setAmount] = useState('');
  const [purpose, setPurpose] = useState('');
  const [channel, setChannel] = useState<Channel>('portal');
  const [note, setNote] = useState('');
  const [invoice, setInvoice] = useState<{ name: string; sha256: string } | null>(null);
  const [hashing, setHashing] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [handingToAgent, setHandingToAgent] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [serverFieldErrors, setServerFieldErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const loadVendors = useCallback(async () => {
    setVendorsProblem(null);
    try {
      const { data, error, response } = await api().GET('/vendors');
      if (error || !data) {
        setVendorsProblem(problemMessage(toProblem(error, response?.status)));
        return;
      }
      setVendors((data.vendors ?? []) as VendorRow[]);
    } catch (caught) {
      setVendorsProblem(problemMessage(toProblem(caught)));
    }
  }, []);

  useEffect(() => {
    void loadVendors();
  }, [loadVendors]);

  const selectedVendor = useMemo(
    () => vendors?.find((vendor) => vendor.vendor_id === vendorId) ?? null,
    [vendors, vendorId],
  );

  const amountError = useMemo(() => {
    if (amount.trim() === '') return 'Enter an amount.';
    try {
      rupeesToPaise(amount);
      return null;
    } catch (error) {
      return error instanceof InvalidRupeeInputError ? error.message : 'Enter a valid amount.';
    }
  }, [amount]);

  const vendorError = vendorId === '' ? 'Choose who is being paid.' : null;
  const formValid = !amountError && !vendorError && !hashing;

  const amountPreview = useMemo(() => {
    try {
      return formatMoney(rupeesToPaise(amount));
    } catch {
      return null;
    }
  }, [amount]);

  const onFile = useCallback(async (file: File | null) => {
    if (!file) {
      setInvoice(null);
      return;
    }
    setHashing(true);
    try {
      setInvoice({ name: file.name, sha256: await hashFile(file) });
    } catch {
      setBanner('That file could not be read. Try another.');
      setInvoice(null);
    } finally {
      setHashing(false);
    }
  }, []);

  const submit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setTouched({ vendor: true, amount: true });
      if (!formValid) return;

      setSubmitting(true);
      setBanner(null);
      setServerFieldErrors({});

      try {
        const { data, error, response } = await api().POST('/intents', {
          body: {
            payee_vendor_id: vendorId,
            amount_paise: rupeesToPaise(amount),
            currency: 'INR',
            purpose: purpose.trim() || undefined,
            invoice_sha256: invoice?.sha256,
            instruction_channel: channel,
            instruction_note: note.trim() || null,
            initiator: { type: 'human', id: user?.email ?? 'clerk@acme.example' },
          },
        });

        if (error || !data) {
          // Keep everything the clerk typed. Re-keying a payment because of a
          // server error is how a digit gets changed by accident.
          const problem = toProblem(error, response?.status);
          setBanner(problemMessage(problem));
          setServerFieldErrors(fieldErrors(problem));
          return;
        }

        navigate(`/payments/${data.intent_id}`);
      } catch (caught) {
        setBanner(problemMessage(toProblem(caught)));
      } finally {
        setSubmitting(false);
      }
    },
    [formValid, vendorId, amount, purpose, invoice, channel, note, user, navigate],
  );

  /**
   * Hand the invoice to the payables agent instead of keying the payment.
   *
   * The agent reads the invoice, looks the vendor up and asks Pramaan for a
   * mandate. It cannot release money, and this button does not approve
   * anything. It needs an uploaded invoice, because reading it is the job.
   */
  const handToAgent = useCallback(async () => {
    if (!invoice) return;
    setHandingToAgent(true);
    setBanner(null);

    try {
      const { data, error, response } = await api().POST('/agent/pay', {
        body: {
          invoice_ref: purpose.trim() || invoice.name,
          ...(vendorId ? { vendor_id: vendorId } : {}),
        },
      });

      if (error || !data) {
        setBanner(problemMessage(toProblem(error, response?.status)));
        return;
      }

      navigate(`/agent-runs/${data.agent_request_id}`);
    } catch (caught) {
      setBanner(problemMessage(toProblem(caught)));
    } finally {
      setHandingToAgent(false);
    }
  }, [invoice, purpose, vendorId, navigate]);

  if (vendorsProblem) {
    return (
      <ErrorState
        title="We could not load the vendor master"
        error={new Error(vendorsProblem)}
        onRetry={() => void loadVendors()}
      />
    );
  }

  if (vendors === null) return <LoadingState label="Loading vendors" />;

  const showVendorError = touched['vendor'] && vendorError;
  const showAmountError = touched['amount'] && amountError;

  return (
    <div>
      <h1>New payment</h1>
      <p className="erp-hint" style={{ marginBottom: 10 }}>
        Acme pays from its sandbox bank account. Every payment goes to Pramaan
        first, and nothing reaches the bank without a matching mandate.
      </p>

      {banner ? (
        <div className="erp-note" role="alert" style={{ borderColor: '#B3261E', background: '#FFF6F5' }}>
          <strong>The payment was not sent.</strong> {banner}
          <div className="erp-hint">Nothing you typed has been lost. Try again.</div>
        </div>
      ) : null}

      <form onSubmit={(event) => void submit(event)} noValidate style={{ maxWidth: 560 }}>
        <div className="erp-field">
          <label htmlFor="vendor">Who is being paid</label>
          <select
            id="vendor"
            className="erp-select"
            value={vendorId}
            aria-invalid={showVendorError ? true : undefined}
            aria-describedby={showVendorError ? 'vendor-error' : undefined}
            onBlur={() => setTouched((state) => ({ ...state, vendor: true }))}
            onChange={(event) => setVendorId(event.target.value)}
          >
            <option value="">Choose a vendor</option>
            {vendors.map((vendor) => (
              <option key={vendor.vendor_id} value={vendor.vendor_id}>
                {vendor.legal_name}
              </option>
            ))}
          </select>
          {showVendorError ? (
            <div className="erp-err" id="vendor-error">
              {vendorError}
            </div>
          ) : null}
          {serverFieldErrors['payee_vendor_id'] ? (
            <div className="erp-err">{serverFieldErrors['payee_vendor_id']}</div>
          ) : null}
          {selectedVendor ? (
            <div className="erp-hint">
              Paying {maskAccount(selectedVendor.account_last4)} &middot;{' '}
              {selectedVendor.ifsc}
              {selectedVendor.is_new_payee ? ' · no payment history' : ''}
            </div>
          ) : null}
        </div>

        <div className="erp-field">
          <label htmlFor="amount">Amount in rupees</label>
          <input
            id="amount"
            className="erp-input"
            inputMode="decimal"
            placeholder="9,80,000"
            value={amount}
            aria-invalid={showAmountError ? true : undefined}
            aria-describedby={showAmountError ? 'amount-error' : 'amount-preview'}
            onBlur={() => setTouched((state) => ({ ...state, amount: true }))}
            onChange={(event) => setAmount(event.target.value)}
          />
          {showAmountError ? (
            <div className="erp-err" id="amount-error">
              {amountError}
            </div>
          ) : amountPreview ? (
            <div className="erp-hint" id="amount-preview">
              {amountPreview}
            </div>
          ) : null}
          {serverFieldErrors['amount_paise'] ? (
            <div className="erp-err">{serverFieldErrors['amount_paise']}</div>
          ) : null}
        </div>

        <div className="erp-field">
          <label htmlFor="purpose">Invoice number or purpose (optional)</label>
          <input
            id="purpose"
            className="erp-input"
            placeholder="INV-2219"
            value={purpose}
            onChange={(event) => setPurpose(event.target.value)}
          />
        </div>

        <div className="erp-field">
          <label htmlFor="invoice">Invoice (optional)</label>
          <input
            id="invoice"
            className="erp-input"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(event) => void onFile(event.target.files?.[0] ?? null)}
          />
          {hashing ? <div className="erp-hint">Reading the invoice&hellip;</div> : null}
          {invoice ? (
            <div className="erp-hint">
              {invoice.name}
              <br />
              SHA-256 {invoice.sha256}
            </div>
          ) : (
            <div className="erp-hint">
              Pramaan reads the invoice and checks it against the vendor master. The
              file is fingerprinted here in your browser, so the approver can see it
              is the same document.
            </div>
          )}
        </div>

        <fieldset className="erp-fieldset">
          <legend>How did this payment come to you?</legend>
          {CHANNELS.map((option) => (
            <label key={option.value} className="erp-radio">
              <input
                type="radio"
                name="channel"
                value={option.value}
                checked={channel === option.value}
                onChange={() => setChannel(option.value)}
              />{' '}
              {option.label}
            </label>
          ))}
          <div className="erp-hint">
            Answer honestly. Pramaan weighs a chat message differently from an
            invoice, and that is the point.
          </div>
        </fieldset>

        <div className="erp-field">
          <label htmlFor="note">What were you told? (optional)</label>
          <textarea
            id="note"
            className="erp-textarea"
            rows={3}
            placeholder="Paste or summarise the message you were sent."
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          <button
            type="submit"
            className="erp-btn erp-btn--go"
            disabled={!formValid || submitting}
            title={formValid ? undefined : 'Choose a vendor and enter a valid amount first.'}
          >
            {submitting ? 'Sending to Pramaan…' : 'Pay'}
          </button>

          <button
            type="button"
            className="erp-btn"
            disabled={!invoice || handingToAgent || submitting}
            onClick={() => void handToAgent()}
            title={
              invoice
                ? 'The agent reads the invoice and asks Pramaan for a mandate. It cannot release money.'
                : 'Upload an invoice first: the agent reads the invoice.'
            }
          >
            {handingToAgent ? 'Handing it over…' : 'Let the AI agent pay this'}
          </button>
        </div>

        <p className="erp-hint" style={{ marginTop: 10 }}>
          Pay sends this to Pramaan for a decision. It does not move money, and you
          cannot approve your own payment.
        </p>
      </form>
    </div>
  );
}
