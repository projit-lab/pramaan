/**
 * Material Symbols Rounded, by ligature name.
 *
 * One icon set across the whole product, as the brand kit requires. Outlined at
 * rest, filled when selected or for a warning.
 *
 * Icons are always decorative here: every status, reason and check also carries
 * a word, so an icon never has to be read on its own. That is why `aria-hidden`
 * is on by default rather than something each caller has to remember.
 */

import type { ReactNode } from 'react';

export interface IconProps {
  /** The Material Symbols ligature, for example `schedule` or `check_circle`. */
  name: string;
  /** Filled rather than outlined. Used for warnings and selected states. */
  fill?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** Give the icon a label only when it is the sole carrier of meaning. */
  label?: string;
}

export function Icon({ name, fill, size = 'md', className, label }: IconProps): ReactNode {
  const classes = [
    'pm-ico',
    fill ? 'pm-ico--fill' : '',
    size === 'sm' ? 'pm-ico--sm' : '',
    size === 'lg' ? 'pm-ico--lg' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span
      className={classes}
      aria-hidden={label ? undefined : true}
      role={label ? 'img' : undefined}
      aria-label={label}
    >
      {name}
    </span>
  );
}
