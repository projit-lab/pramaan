import { AppHeader, useAuth } from '@pramaan/shared';
import type { ReactNode } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { Devices } from './pages/Devices';
import { HoldsBoard } from './pages/HoldsBoard';
import { PaymentDetail } from './pages/PaymentDetail';

export function App(): ReactNode {
  const { user, signOut } = useAuth();

  return (
    <div className="pr-shell">
      <AppHeader
        appName="Console"
        email={user?.email ?? null}
        onSignOut={signOut}
        nav={
          <>
            <NavLink to="/" className="pr-navlink" end>
              Holds
            </NavLink>
            <NavLink to="/devices" className="pr-navlink">
              Devices
            </NavLink>
          </>
        }
      />

      <main className="pr-main">
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
