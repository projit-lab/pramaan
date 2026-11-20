/**
 * The state band: the coloured header at the top of every page, with fine
 * white seal lines and a dashed ring in the corner, the security-paper texture
 * of a cheque.
 *
 * **Its colour is the payment's state.** Blue at rest, amber held, green
 * released, red stopped. You know what is happening before you read a word.
 *
 * It always also carries the state as a chip on white, because colour never
 * carries meaning alone. One band per page, only at the top, never as a card
 * in the middle.
 */

import type { ReactNode } from 'react';
import type { HoldStatus } from '../types/firestore';
import { bandModifier } from './Badges';

export interface StateBandProps {
  /** The payment's status, which picks the colour. Omit for the blue resting band. */
  status?: HoldStatus | null;
  /** A small label above the heading. */
  eyebrow?: ReactNode;
  /** The hero: a count, a payee, an amount. */
  children: ReactNode;
  /** Rounded corners, for a band that sits inside a page rather than at its very top. */
  rounded?: boolean;
}

export function StateBand({
  status,
  eyebrow,
  children,
  rounded = true,
}: StateBandProps): ReactNode {
  const modifier = bandModifier(status);
  return (
    <div className={`pm-band ${modifier} ${rounded ? 'pm-band--page' : ''}`.trim()}>
      <div className="pm-band__inner">
        {eyebrow ? <div className="pm-row">{eyebrow}</div> : null}
        {children}
      </div>
    </div>
  );
}
