/**
 * The mandate viewer.
 *
 * Finance can read the signed mandate, copy it, and hand it to an auditor who
 * will check it somewhere else entirely. That last part is the point: the copy
 * button exists so the evidence can leave Pramaan and still stand up.
 *
 * Collapsed by default. A wall of base64 above the timeline helps nobody, and the
 * people who want it know they want it.
 */

import { api, problemMessage, toProblem } from '@pramaan/shared';
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
      setProblem('Could not copy. Select the text and copy it yourself.');
    }
  }, [json]);

  return (
    <div className="pr-stack">
      <div className="pr-row">
        <button
          type="button"
          className="pr-button pr-button--small"
          onClick={toggle}
          aria-expanded={open}
          aria-controls="mandate-json"
        >
          {open ? 'Hide the mandate' : 'Show the mandate'}
        </button>

        {open && json ? (
          <button type="button" className="pr-button pr-button--small" onClick={() => void copy()}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        ) : null}
      </div>

      {open ? (
        <div id="mandate-json">
          {loading ? (
            <p className="pr-muted">Loading the mandate&hellip;</p>
          ) : problem ? (
            <div className="pr-error" role="alert">
              {problem}
            </div>
          ) : json ? (
            <>
              <pre className="pr-mono pr-json">{json}</pre>
              <p className="pr-fineprint">
                This is the whole signed record. Anyone can check its countersignature
                on the public verifier without signing in to Pramaan.
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
