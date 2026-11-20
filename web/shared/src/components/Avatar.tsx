/**
 * A payee's initial in a circle, the way a payments app shows who you are
 * paying. Never a real company logo.
 */

import type { ReactNode } from 'react';

export function Avatar({
  name,
  size = 'md',
  onBand = false,
}: {
  name: string | null | undefined;
  size?: 'sm' | 'md';
  /** On a coloured band the avatar goes white, so it stays legible. */
  onBand?: boolean;
}): ReactNode {
  // Take the first letter of the first word that starts with one.
  const initial = (name ?? '').trim().replace(/[^\p{L}\p{N}]/gu, '').charAt(0).toUpperCase();

  return (
    <span
      className={`pm-avatar${size === 'sm' ? ' pm-avatar--sm' : ''}`}
      style={onBand ? { background: 'var(--background)', color: 'var(--ink)' } : undefined}
      aria-hidden="true"
    >
      {initial || '?'}
    </span>
  );
}
