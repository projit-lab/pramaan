/**
 * The Pramaan logo: a solid blue circle with one white pen stroke ending in a
 * dot, the moment of signing.
 *
 * Inline SVG rather than an <img>, so it needs no bundler asset handling and
 * cannot flash in late on a projector. The same artwork is saved as
 * assets/pramaan-mark.svg and assets/pramaan-lockup.svg for Android and design.
 *
 * Never recolour it red, amber or green.
 */

import type { ReactNode } from 'react';

function Glyph({ size }: { size: number }): ReactNode {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Pramaan"
      focusable="false"
    >
      <circle cx="32" cy="32" r="30" fill="#0B57D0" />
      <path
        d="M17 35c3.6-0.5 5.8 1.8 8.2 6.2 2.7-9.3 8.4-17.3 20.6-23.4"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="46.6" cy="17.4" r="3" fill="#FFFFFF" />
    </svg>
  );
}

/** The mark alone. Smallest usable size is 20px. */
export function PramaanMark({ size = 32 }: { size?: number }): ReactNode {
  return <Glyph size={size} />;
}

/** The mark with the wordmark beside it, in live text. */
export function PramaanLockup({ size = 32, href }: { size?: number; href?: string }): ReactNode {
  const content = (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
      }}
    >
      <Glyph size={size} />
      <span
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: Math.round(size * 0.66),
          fontWeight: 500,
          color: 'var(--ink)',
          letterSpacing: '-0.01em',
        }}
      >
        Pramaan
      </span>
    </span>
  );

  if (href) {
    return (
      <a
        href={href}
        className="pm-lockup-link"
        style={{
          textDecoration: 'none',
          display: 'inline-flex',
          borderRadius: 'var(--radius-sm)',
        }}
        aria-label="Pramaan home"
      >
        {content}
      </a>
    );
  }

  return content;
}
