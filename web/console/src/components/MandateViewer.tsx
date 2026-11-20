/**
 * The signed mandate, readable and copyable.
 *
 * Finance can read it, copy it, and hand it to an auditor who will check it
 * somewhere else entirely. That last part is the point: the copy button exists
 * so the evidence can leave Pramaan and still stand up.
 *
 * Collapsed by default. A wall of base64 above the timeline helps nobody, and
 * the people who want it know they want it.
 */

import { Icon, api, problemMessage, toProblem } from '@pramaan/shared';
import { type ReactNode, useCallback, useState } from 'react';

export function MandateViewer({ mandateId }: { mandateId: string }): ReactNode {
  const [open, setOpen] = useState(false);
  const [json, setJson] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setProblem(null);
    try {
      const { data, error, response } = await api().GET('/mandates/{mandateId}', {
        params: { path: { mandateId } },
      });
      if (error || !data) {
        setProblem(problemMessage(toProblem(error, response?.status)));
        return;
      }
      setJson(JSON.stringify(data, null, 2));
    } catch (caught) {
      setProblem(problemMessage(toProblem(caught)));
    } finally {
      setLoading(false);
    }
  }, [mandateId]);

  const toggle = useCallback(() => {
    const next = !open;
    setOpen(next);
    if (next && json === null && !loading) void load();
  }, [open, json, loading, load]);

  const copy = useCallback(async () => {
    if (!json) return;
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      // Clipboard access can be refused. Say nothing rather than claim a copy
      // that did not happen; the text is on screen and selectable anyway.
      setProblem('We could not copy it. Select the text and copy it yourself.');
    }
  }, [json]);

  return (
    <div className="pm-stack">
      <div className="pm-row">
        <button
          type="button"
          className="pm-btn pm-btn--text"
          onClick={toggle}
          aria-expanded={open}
          aria-controls="mandate-json"
          style={{ paddingLeft: 0 }}
        >
          <Icon name={open ? 'expand_less' : 'expand_more'} size="sm" />
          {open ? 'Hide the full record' : 'View the full record'}
        </button>

        {open && json ? (
          <button type="button" className="pm-btn pm-btn--text" onClick={() => void copy()}>
            <Icon name={copied ? 'check' : 'content_copy'} size="sm" />
            {copied ? 'Copied' : 'Copy'}
          </button>
        ) : null}
      </div>

      {open ? (
        <div id="mandate-json">
          {loading ? (
            <div className="pm-muted">Loading the mandate&hellip;</div>
          ) : problem ? (
            <div className="pm-banner pm-banner--blocked" role="alert">
              <Icon name="error" />
              <div>{problem}</div>
            </div>
          ) : json ? (
            <>
              <pre className="pm-json">{json}</pre>
              <div className="pm-hint" style={{ marginTop: 'var(--space-2)' }}>
                Anyone can check this record&rsquo;s countersignature on the public
                verifier without signing in to Pramaan.
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
