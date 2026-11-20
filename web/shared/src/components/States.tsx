/**
 * Loading, empty and error states.
 *
 * Every screen in Pramaan has all three designed before it is coded, so they live
 * here once instead of being improvised per screen.
 *
 * The error state never says "fraud" and never claims a check failed. An error is
 * an error: something could not be loaded.
 */

import type { ReactNode } from 'react';

export function LoadingState({ label = 'Loading' }: { label?: string }): ReactNode {
  return (
    <div className="pr-state" role="status" aria-live="polite">
      <span className="pr-spinner" aria-hidden="true" />
      <p className="pr-muted">{label}&hellip;</p>
    </div>
  );
}

export interface EmptyStateProps {
  /** The headline, written for the person reading it: "No payments held yet". */
  title: string;
  /** One line about what would make something appear here. */
  detail?: string;
  children?: ReactNode;
}

export function EmptyState({ title, detail, children }: EmptyStateProps): ReactNode {
  return (
    <div className="pr-state">
      <p className="pr-state__title">{title}</p>
      {detail ? <p className="pr-muted">{detail}</p> : null}
      {children}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  error?: Error | null;
  /** Shown when the person can do something about it. */
  onRetry?: () => void;
}

export function ErrorState({
  title = 'Could not load this',
  error,
  onRetry,
}: ErrorStateProps): ReactNode {
  return (
    <div className="pr-state pr-state--error" role="alert">
      <p className="pr-state__title">{title}</p>
      {error ? <p className="pr-muted pr-mono">{error.message}</p> : null}
      {onRetry ? (
        <button type="button" className="pr-button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

/**
 * What a screen shows where a security check did not run.
 *
 * Never "passed", never "failed", never "fraud". A check that did not run is a
 * check we cannot speak for, and the UI says exactly that.
 */
export function CouldNotVerify({ what }: { what?: string }): ReactNode {
  return (
    <span className="pr-unverified" title="Pramaan has no result for this check.">
      Couldn&rsquo;t verify{what ? ` ${what}` : ''}
    </span>
  );
}
