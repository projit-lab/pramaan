/**
 * The file door, from the clerk's side.
 *
 * Finance uploads the same payment file they would hand to their bank. Every
 * line becomes a payment that meets the same gate as one somebody typed, which
 * is the point of having four doors at all.
 *
 * Two things this page is careful about:
 *
 * - It reads the file in the browser first and shows the clerk what it found,
 *   so they confirm their own file before anything is sent. The server parses
 *   it again and the server's answer is the one that counts; this preview is a
 *   courtesy, never the authority.
 * - After the upload it reports how many lines are still waiting for an
 *   approver, and says the file is not finished until none are. A tick the
 *   moment the upload succeeds would be a lie about where the money is.
 */

import { ErrorState, Money, firebaseAuth, formatIstTime, readEnv } from '@pramaan/shared';
import { type ChangeEvent, type ReactNode, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  try {
    const user = firebaseAuth().currentUser;
    if (user) {
      const token = await user.getIdToken();
      headers['Authorization'] = `Bearer ${token}`;
      return headers;
    }
  } catch {
    // fallback
  }
  headers['X-Dev-User'] = 'clerk@acme.example';
  return headers;
}

interface UploadedLine {
  line_no: number;
  intent_id: string;
  status?: string;
}

interface BankFileResult {
  file_id: string;
  filename: string;
  sha256: string;
  line_count: number;
  waiting_on_approval: number;
  settled: number;
  complete: boolean;
  lines: UploadedLine[];
}

interface PreviewLine {
  lineNo: number;
  payeeName: string;
  accountLast4: string;
  ifsc: string;
  amountPaise: string;
  purpose: string;
}

const REQUIRED = ['payee_name', 'account_last4', 'ifsc', 'amount_paise'] as const;

const SAMPLE = [
  'payee_name,account_last4,ifsc,amount_paise,purpose',
  'Sri Lakshmi Castings,7781,ABCD0123456,98000000,INV-2219',
  'Global Trade Solutions,9032,WXYZ0004411,465000000,INV-7741',
  'Kaveri Steel Traders,5540,EFGH0005540,184000000,KAVERI-4471',
].join('\n');

/**
 * A deliberately forgiving preview parser. It only decides what to SHOW; the
 * server decides what is accepted, and it is stricter. Anything this cannot
 * read is reported as a line it could not read, never silently dropped.
 */
function preview(text: string): { lines: PreviewLine[]; problem: string | null } {
  const rows = text.split(/\r?\n/).filter((row) => row.trim().length > 0);
  if (rows.length === 0) return { lines: [], problem: 'The file is empty.' };

  const headerRow = rows[0];
  if (headerRow === undefined) return { lines: [], problem: 'The file is empty.' };
  const headers = headerRow.split(',').map((h) => h.trim().toLowerCase());
  const missing = REQUIRED.filter((column) => !headers.includes(column));
  if (missing.length > 0) {
    return {
      lines: [],
      problem: `The header row is missing ${missing.join(', ')}.`,
    };
  }

  const at = (cells: string[], column: string): string =>
    (cells[headers.indexOf(column)] ?? '').trim();

  const lines: PreviewLine[] = [];
  for (let index = 1; index < rows.length; index += 1) {
    const cells = (rows[index] ?? '').split(',');
    lines.push({
      lineNo: index,
      payeeName: at(cells, 'payee_name'),
      accountLast4: at(cells, 'account_last4'),
      ifsc: at(cells, 'ifsc'),
      amountPaise: at(cells, 'amount_paise'),
      purpose: at(cells, 'purpose'),
    });
  }
  return { lines, problem: null };
}

export function BankFile(): ReactNode {
  const env = readEnv();
  const [text, setText] = useState('');
  const [filename, setFilename] = useState('payments.csv');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<BankFileResult | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const { lines, problem: previewProblem } = preview(text);

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0];
    if (!picked) return;
    setFilename(picked.name);
    setResult(null);
    setProblem(null);
    void picked.text().then(setText);
  };

  const send = useCallback(async () => {
    setSending(true);
    setProblem(null);
    try {
      const form = new FormData();
      form.append('file', new Blob([text], { type: 'text/csv' }), filename);
      // Plain fetch, not the generated client: this branch was cut before the
      // file door went into the contract, and a multipart upload is not what
      // the typed JSON client is for.
      const headers = await getAuthHeaders();
      const res = await fetch(`${env.apiBase}/v1/files/bank`, {
        method: 'POST',
        headers,
        body: form,
      });
      const body = (await res.json().catch(() => ({}))) as BankFileResult & { detail?: string };
      if (!res.ok) {
        setProblem(body.detail ?? `The file was not accepted (${res.status}).`);
        return;
      }
      setResult(body);
    } catch (caught) {
      setProblem((caught as Error).message);
    } finally {
      setSending(false);
    }
  }, [env.apiBase, filename, text]);

  // Once uploaded, keep the progress honest: poll until nothing is waiting.
  useEffect(() => {
    if (!result || result.complete) return;
    const timer = window.setInterval(async () => {
      const headers = await getAuthHeaders();
      void fetch(`${env.apiBase}/v1/files/bank/${result.file_id}`, { headers })
        .then((res) => (res.ok ? res.json() : null))
        .then((body) => {
          if (body) setResult(body as BankFileResult);
        })
        .catch(() => {
          /* A failed refresh is not a change in the file's state. */
        });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [env.apiBase, result]);

  return (
    <div>
      <h1>Bank payment file</h1>
      <p className="erp-hint" style={{ marginTop: 0 }}>
        Upload the payment file you would send to the bank. Every line becomes a
        payment, and every payment goes through Pramaan exactly as if you had
        typed it here.
      </p>

      <div className="erp-fieldset">
        <input type="file" accept=".csv,text/csv" onChange={onPick} className="erp-input" />
        <div className="erp-hint" style={{ marginTop: 6 }}>
          CSV with a header row naming {REQUIRED.join(', ')}. Or{' '}
          <button
            type="button"
            className="erp-linkbtn"
            onClick={() => {
              setText(SAMPLE);
              setFilename('november-run.csv');
              setResult(null);
              setProblem(null);
            }}
          >
            use the sample file
          </button>
          .
        </div>
      </div>

      {previewProblem && text.length > 0 ? (
        <div className="erp-note">{previewProblem}</div>
      ) : null}

      {lines.length > 0 && !result ? (
        <>
          <h2>
            {filename} &middot; {lines.length} payment{lines.length === 1 ? '' : 's'}
          </h2>
          <div className="erp-table-wrap">
            <table className="erp-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Payee</th>
                  <th>Account</th>
                  <th>IFSC</th>
                  <th>Amount</th>
                  <th>Purpose</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.lineNo}>
                    <td>{line.lineNo}</td>
                    <td>{line.payeeName || <em>missing</em>}</td>
                    <td>&bull;&bull;&bull;&bull; {line.accountLast4}</td>
                    <td>{line.ifsc}</td>
                    <td>
                      {/^[0-9]+$/.test(line.amountPaise) ? (
                        <Money paise={line.amountPaise} />
                      ) : (
                        <em>{line.amountPaise || 'missing'}</em>
                      )}
                    </td>
                    <td>{line.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="erp-hint">
            Pramaan reads the file again when it arrives and is stricter than this
            preview. If it refuses a line, nothing in the file is created.
          </p>
          <button
            type="button"
            className="erp-btn erp-btn--primary"
            onClick={() => void send()}
            disabled={sending}
          >
            {sending ? 'Sending…' : `Send ${lines.length} payments`}
          </button>
        </>
      ) : null}

      {problem ? (
        <ErrorState title="The file was not accepted" error={new Error(problem)} />
      ) : null}

      {result ? (
        <>
          <h2>{result.filename}</h2>
          <div className="erp-note">
            {result.complete ? (
              <>
                <strong>Finished.</strong> Every one of the {result.line_count} payments in
                this file has been decided.
              </>
            ) : (
              <>
                <strong>Not finished.</strong> {result.waiting_on_approval} of{' '}
                {result.line_count} payments are still waiting for an approver. The file
                is not done until they are.
              </>
            )}
          </div>

          <dl className="erp-admin__row">
            <dt>Lines</dt>
            <dd>{result.line_count}</dd>
            <dt>Decided</dt>
            <dd>{result.settled}</dd>
            <dt>Waiting</dt>
            <dd>{result.waiting_on_approval}</dd>
            <dt>File checksum</dt>
            <dd className="pm-mono" style={{ wordBreak: 'break-all' }}>
              {result.sha256}
            </dd>
          </dl>

          <div className="erp-table-wrap">
            <table className="erp-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Payment</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {result.lines.map((line) => (
                  <tr key={line.line_no}>
                    <td>{line.line_no}</td>
                    <td>
                      <Link to={`/payments/${line.intent_id}`}>{line.intent_id}</Link>
                    </td>
                    <td>{line.status ?? 'held'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="erp-hint">
            Uploaded {formatIstTime(new Date().toISOString()) ?? ''}. Nothing in this file
            can be released until its approver signs it on their phone.
          </p>
        </>
      ) : null}
    </div>
  );
}
