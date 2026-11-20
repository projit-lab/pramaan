/**
 * The reasons a payment was held, as chips.
 *
 * Written by rules, never by Gemini. A reason that records a change gets the
 * ChangedField treatment instead: old struck through, arrow, new, on a soft red
 * card. That is the single most important element on an approval screen,
 * because the fake-invoice scam works by changing bank details.
 */

import { Icon, type Reason, reasonIcon } from '@pramaan/shared';
import type { ReactNode } from 'react';

export function ReasonChips({
  reasons,
  showCodes = false,
}: {
  reasons: Reason[];
  /** The console may show the rule code in mono for finance staff. */
  showCodes?: boolean;
}): ReactNode {
  if (reasons.length === 0) {
    return <span className="pm-muted">No rules matched</span>;
  }

  const changed = reasons.filter((reason) => reason.changedFrom || reason.changedTo);
  const plain = reasons.filter((reason) => !reason.changedFrom && !reason.changedTo);

  return (
    <div className="pm-stack">
      {changed.map((reason) => (
        <div className="pm-changed" key={reason.code}>
          <Icon name="warning" fill />
          <div className="pm-changed__body">
            <span className="pm-changed__title">{reason.text}</span>
            <span className="pm-changed__vals">
              {reason.changedFrom ? (
                <span className="pm-changed__old">{reason.changedFrom}</span>
              ) : null}
              {reason.changedFrom && reason.changedTo ? (
                <Icon name="arrow_forward" size="sm" />
              ) : null}
              {reason.changedTo ? (
                <span className="pm-changed__new">{reason.changedTo}</span>
              ) : null}
            </span>
          </div>
        </div>
      ))}

      {plain.length > 0 ? (
        <div className="pm-row">
          {plain.map((reason) => (
            <span className="pm-reason" key={reason.code}>
              <Icon name={reasonIcon(reason.code)} size="sm" />
              {reason.text}
              {showCodes ? <b>{reason.code}</b> : null}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
