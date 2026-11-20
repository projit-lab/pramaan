/**
 * Loading, empty and error states, plus the one that matters most:
 * "couldn't verify".
 *
 * The brand kit's voice rules apply here more than anywhere: say what we
 * checked and what did not match, never "fraud", never "Error!", never
 * "Success!". An empty board is not a failure, so it does not look like one.
 */

import type { ReactNode } from 'react';
import { Icon } from './Icon';

export function LoadingState({ label = 'Loading' }: { label?: string }): ReactNode {
  return (
    <div className="pm-empty" role="status" aria-live="polite">
      <span className="pm-spinner" aria-hidden="true" style={{ margin: '0 auto 12px' }} />
      <div className="pm-muted">{label}&hellip;</div>
    </div>
  );
}

export interface EmptyStateProps {
  /** Written for the person reading it: "Nothing is waiting". */
  title: string;
  /** One line about what would make something appear here. */
  detail?: string;
  /** A Material Symbols ligature. Defaults to an inbox. */
  icon?: string;
  children?: ReactNode;
}

export function EmptyState({
  title,
  detail,
  icon = 'inbox',
  children,
}: EmptyStateProps): ReactNode {
  return (
    <div className="pm-card pm-empty">
      <span className="pm-empty__art">
        <Icon name={icon} />
      </span>
      <div className="pm-heading" style={{ color: 'var(--ink)' }}>
        {title}
      </div>
      {detail ? <div>{detail}</div> : null}
      {children ? <div style={{ marginTop: 'var(--space-4)' }}>{children}</div> : null}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  error?: Error | null;
  onRetry?: () => void;
}

/**
 * Something could not be loaded. That is all this says: it is never evidence
 * about a payment, and it never uses the word fraud.
 */
export function ErrorState({
  title = 'We could not load this',
  error,
  onRetry,
}: ErrorStateProps): ReactNode {
  return (
    <div className="pm-stack" role="alert">
      <div className="pm-banner pm-banner--blocked">
        <Icon name="error" />
        <div>
          <strong style={{ fontWeight: 500 }}>{title}.</strong>{' '}
          {error ? error.message : 'Please try again.'}
        </div>
      </div>
      {onRetry ? (
        <div>
          <button type="button" className="pm-btn pm-btn--tonal" onClick={onRetry}>
            <Icon name="refresh" />
            Try again
          </button>
        </div>
      ) : null}
    </div>
  );
}

/**
 * A check Pramaan has no result for.
 *
 * Never "passed", never "failed", never "fraud". A check that did not run is a
 * check we cannot speak for, and the screen says exactly that.
 */
export function CouldNotVerify({ what }: { what?: string }): ReactNode {
  return (
    <span className="pm-unverified" title="Pramaan has no result for this check.">
      <Icon name="help" size="sm" />
      Couldn&rsquo;t verify{what ? ` ${what}` : ''}
    </span>
  );
}

export type BannerTone = 'held' | 'blocked' | 'released' | 'info';

/**
 * A one-line message at the top of a page or card.
 *
 * Lead with the fact, then one detail, and always say whether money moved.
 */
export function Banner({
  tone,
  icon,
  children,
}: {
  tone: BannerTone;
  icon?: string;
  children: ReactNode;
}): ReactNode {
  const defaults: Record<BannerTone, string> = {
    held: 'schedule',
    blocked: 'block',
    released: 'check_circle',
    info: 'info',
  };
  return (
    <div className={`pm-banner pm-banner--${tone}`}>
      <Icon name={icon ?? defaults[tone]} />
      <div>{children}</div>
    </div>
  );
}
