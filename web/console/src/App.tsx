import { DemoModeChip, Icon, PramaanLockup, readEnv, useAuth } from '@pramaan/shared';
import type { ReactNode } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { Devices } from './pages/Devices';
import { HoldsBoard } from './pages/HoldsBoard';
import { PaymentDetail } from './pages/PaymentDetail';

/**
 * The finance console.
 *
 * A left nav drawer on `surface-container` with the lockup at the top and the
 * current page in a `secondary-container` pill, and a white content area.
 *
 * There is no Approve button anywhere in this console, at any role. An
 * approval is a hardware signature made on a phone, and no amount of being
 * signed in to a web console can produce one. That absence is the product.
 */
export function App(): ReactNode {
  const { user, signOut } = useAuth();
  const env = readEnv();

  return (
    <div className="pm-shell">
      <nav className="pm-side" aria-label="Console sections">
        <div className="pm-side__brand" style={{ padding: '8px 12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <PramaanLockup size={28} />
          {env.demoMode ? <DemoModeChip /> : null}
        </div>

        {/* NavLink sets aria-current="page" itself, which is what the active
            pill in bundle.css keys off. */}
        <NavLink to="/" end>
          <Icon name="inbox" />
          Holds
        </NavLink>
        <NavLink to="/devices">
          <Icon name="smartphone" />
          Devices
        </NavLink>

        <div className="pm-grow" />

        <div className="pm-side__account">
          {user?.email ? <div className="pm-hint pm-side__email">{user.email}</div> : null}
          <button
            type="button"
            className="pm-btn pm-btn--text"
            onClick={() => void signOut()}
            style={{ paddingLeft: 0 }}
          >
            <Icon name="logout" size="sm" />
            Sign out
          </button>
        </div>
      </nav>

      <main className="pm-page">
        <Routes>
          <Route path="/" element={<HoldsBoard />} />
          <Route path="/payments/:intentId" element={<PaymentDetail />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
