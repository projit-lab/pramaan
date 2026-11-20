/**
 * The header every signed-in Pramaan app wears: the wordmark, the app's own name,
 * whatever navigation that app has, and who is signed in with a way out.
 *
 * Router-agnostic on purpose: each app passes its own links as `nav`, so this
 * component does not care whether it sits above React Router or plain anchors.
 */

import type { ReactNode } from 'react';
import { PramaanMark } from './PramaanMark';

export interface AppHeaderProps {
  /** What this app is called, beside the wordmark. */
  appName: string;
  /** This app's navigation, usually NavLink elements. */
  nav?: ReactNode;
  /** The signed-in account, or null on a public page. */
  email?: string | null;
  onSignOut?: () => void | Promise<void>;
  /** Anything extra on the right: a presenter-mode toggle, a demo-mode chip. */
  children?: ReactNode;
}

export function AppHeader({
  appName,
  nav,
  email,
  onSignOut,
  children,
}: AppHeaderProps): ReactNode {
  return (
    <header className="pr-header">
      <div className="pr-header__inner">
        <div className="pr-row">
          <PramaanMark size={26} />
          <span className="pr-muted" aria-hidden="true">
            /
          </span>
          <span className="pr-h3">{appName}</span>
        </div>

        {nav ? (
          <nav className="pr-header__nav" aria-label={`${appName} sections`}>
            {nav}
          </nav>
        ) : null}

        <div className="pr-row">
          {children}
          {email ? <span className="pr-fineprint">{email}</span> : null}
          {onSignOut ? (
            <button
              type="button"
              className="pr-button pr-button--small"
              onClick={() => void onSignOut()}
            >
              Sign out
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
