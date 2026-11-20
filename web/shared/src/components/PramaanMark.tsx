/**
 * The Pramaan wordmark.
 *
 * Placeholder until the Stitch design lands: inline SVG so it needs no asset and
 * scales on a projector. Replace the glyph and the colours with the Stitch values.
 */

import type { ReactNode } from 'react';

export function PramaanMark({ size = 32 }: { size?: number }): ReactNode {
  return (
    <span className="pr-mark">
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        role="img"
        aria-label="Pramaan"
        focusable="false"
      >
        {/* A seal: a closed ring with a tick, for an approval that was proved. */}
        <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="2.5" />
        <path
          d="M10 16.5l4 4 8-8.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="pr-mark__word">Pramaan</span>
    </span>
  );
}
