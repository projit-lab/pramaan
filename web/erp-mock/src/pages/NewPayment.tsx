/**
 * New payment, in Acme's own ERP.
 *
 * This is where the boss scam starts. A clerk keys a payment, and the Pay button
 * goes to Pramaan rather than to the bank. Nothing here can approve anything: the
 * clerk's job ends at "sent for approval".
 *
 * The form carries the facts the policy engine needs to be any good: not just
 * who and how much, but **how the instruction arrived** and **what it said**.
 * Those two fields are what turn "a payment to a new payee" into "a payment to a
 * new payee, asked for on WhatsApp, marked urgent and confidential".
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

  // Validate as we go, so Pay is disabled until the form is actually payable and
  // the clerk can see why.
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

  if (vendorsProblem) {
    return (
      <ErrorState
        title="Could not load the vendor master"
        error={new Error(vendorsProblem)}
        onRetry={() => void loadVendors()}
      />
    );
  }

  if (vendors === null) return <LoadingState label="Loading vendors" />;

  const showVendorError = touched['vendor'] && vendorError;
  const showAmountError = touched['amount'] && amountError;

  return (
    <div className="pr-stack">
      <div>
        <h1 className="pr-h1">New payment</h1>
        <p className="pr-muted">
          Acme pays from its sandbox bank account. Every payment goes to Pramaan
          first, and nothing reaches the bank without a matching mandate.
        </p>
      </div>

      {banner ? (
        <div className="pr-error" role="alert">
          <strong>The payment was not sent.</strong> {banner}
          <div className="pr-fineprint">Nothing you typed has been lost. Try again.</div>
        </div>
      ) : null}

      <form className="pr-card pr-stack" onSubmit={(event) => void submit(event)} noValidate>
        {/* Payee */}
        <div className="pr-field">
          <label className="pr-label" htmlFor="vendor">
            Who is being paid
          </label>
          <select
            id="vendor"
            className="pr-select"
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
            <p className="pr-fielderror" id="vendor-error">
              {vendorError}
            </p>
          ) : null}
          {serverFieldErrors['payee_vendor_id'] ? (
            <p className="pr-fielderror">{serverFieldErrors['payee_vendor_id']}</p>
          ) : null}

          {selectedVendor ? (
            <p className="pr-fineprint">
              Paying {maskAccount(selectedVendor.account_last4)} &middot;{' '}
              {selectedVendor.ifsc}
              {selectedVendor.is_new_payee ? ' · this payee has no payment history' : ''}
            </p>
          ) : null}
        </div>

        {/* Amount */}
        <div className="pr-field">
          <label className="pr-label" htmlFor="amount">
            Amount in rupees
          </label>
          <input
            id="amount"
            className="pr-input"
            inputMode="decimal"
            placeholder="9,80,000"
            value={amount}
            aria-invalid={showAmountError ? true : undefined}
            aria-describedby={showAmountError ? 'amount-error' : 'amount-preview'}
            onBlur={() => setTouched((state) => ({ ...state, amount: true }))}
            onChange={(event) => setAmount(event.target.value)}
          />
          {showAmountError ? (
            <p className="pr-fielderror" id="amount-error">
              {amountError}
            </p>
          ) : amountPreview ? (
            <p className="pr-fineprint" id="amount-preview">
              {amountPreview}
            </p>
          ) : null}
          {serverFieldErrors['amount_paise'] ? (
            <p className="pr-fielderror">{serverFieldErrors['amount_paise']}</p>
          ) : null}
        </div>

        {/* Purpose */}
        <div className="pr-field">
          <label className="pr-label" htmlFor="purpose">
            Invoice number or purpose <span className="pr-muted">(optional)</span>
          </label>
          <input
            id="purpose"
            className="pr-input"
            placeholder="INV-2219"
            value={purpose}
            onChange={(event) => setPurpose(event.target.value)}
          />
        </div>

        {/* Invoice */}
        <div className="pr-field">
          <label className="pr-label" htmlFor="invoice">
            Invoice <span className="pr-muted">(optional)</span>
          </label>
          <input
            id="invoice"
            className="pr-input"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(event) => void onFile(event.target.files?.[0] ?? null)}
          />
          {hashing ? <p className="pr-fineprint">Reading the invoice&hellip;</p> : null}
          {invoice ? (
            <p className="pr-fineprint">
              {invoice.name}
              <br />
              SHA-256 <code className="pr-mono">{invoice.sha256}</code>
            </p>
          ) : (
            <p className="pr-fineprint">
              Pramaan reads the invoice and checks it against the vendor master. The
              file is fingerprinted here in your browser, so the approver can see it
              is the same document.
            </p>
          )}
        </div>

        {/* How the instruction arrived. This is the policy engine's best signal. */}
        <fieldset className="pr-field">
          <legend className="pr-label">How did this payment come to you?</legend>
          {CHANNELS.map((option) => (
            <label key={option.value} className="pr-radio">
              <input
                type="radio"
                name="channel"
                value={option.value}
                checked={channel === option.value}
                onChange={() => setChannel(option.value)}
              />
              {option.label}
            </label>
          ))}
          <p className="pr-fineprint">
            Answer honestly. Pramaan weighs a chat message differently from an
            invoice, and that is the point.
          </p>
        </fieldset>

        {/* The note */}
        <div className="pr-field">
          <label className="pr-label" htmlFor="note">
            What were you told? <span className="pr-muted">(optional)</span>
          </label>
          <textarea
            id="note"
            className="pr-textarea"
            rows={3}
            placeholder="Paste or summarise the message you were sent."
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </div>

        <div className="pr-row">
          <button
            type="submit"
            className="pr-button pr-button--primary"
            disabled={!formValid || submitting}
            title={formValid ? undefined : 'Choose a vendor and enter a valid amount first.'}
          >
            {submitting ? 'Sending to Pramaan…' : 'Pay'}
          </button>

          <button
            type="button"
            className="pr-button"
            disabled
            title={
              invoice
                ? 'The payables agent arrives in M3.'
                : 'Upload an invoice first: the agent reads the invoice.'
            }
          >
            Let the AI agent pay this
          </button>
        </div>

        <p className="pr-fineprint">
          Pay sends this to Pramaan for a decision. It does not move money, and you
          cannot approve your own payment.
        </p>
      </form>
    </div>
  );
}
