/**
 * The reasons a payment was held, as chips.
 *
 * A reason that records a change shows what it changed from and to, with the
 * change in red, because "bank details changed three days ago" is the sentence
 * that saves the money.
 */

import { ReasonSourceTag, type Reason } from '@pramaan/shared';
import type { ReactNode } from 'react';

export function ReasonChips({
  reasons,
  showSource = false,
}: {
  reasons: Reason[];
  showSource?: boolean;
}): ReactNode {
  if (reasons.length === 0) {
    return <span className="pr-muted">No rules matched</span>;
  }

  return (
    <ul className="pr-reasons">
      {reasons.map((reason) => (
        <li key={reason.code} className="pr-reason">
          <span>{reason.text}</span>
          {reason.changedFrom || reason.changedTo ? (
            <span className="pr-reason__change">
              {reason.changedFrom ? <s>{reason.changedFrom}</s> : null}
              {reason.changedFrom && reason.changedTo ? ' → ' : null}
              {reason.changedTo ? <strong>{reason.changedTo}</strong> : null}
            </span>
          ) : null}
          {showSource ? <ReasonSourceTag source={reason.source} /> : null}
        </li>
      ))}
    </ul>
  );
}
