/**
 * Acme ERP, the mock customer system.
 *
 * Two products are on screen in this demo. This app is the customer's own
 * software: deliberately older-looking, grey, square and dense, so it never
 * reads as Pramaan. That contrast is the point. When the friendly Pramaan
 * pieces appear inside it, the "Protected by Pramaan" badge and the Held
 * status, they stand out as something else entirely.
 *
 * The fictional company is Acme Auto Components Pvt Ltd.
 *
 * The clerk can never approve. That is not a missing feature; it is the point.
 */

import { DemoModeChip, PramaanMark, RoleGate, readEnv, useAuth } from '@pramaan/shared';
import type { ReactNode } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { AgentRun } from './pages/AgentRun';
import { BankFile } from './pages/BankFile';
import { NewPayment } from './pages/NewPayment';
import { PaymentStatus } from './pages/PaymentStatus';
import { Payments } from './pages/Payments';
import { SandboxBank } from './pages/SandboxBank';
import { Vendors } from './pages/Vendors';

function ErpShell({ children }: { children: ReactNode }): ReactNode {
  const { user, signOut } = useAuth();
  const env = readEnv();

  return (
    <div className="erp-shell">
      <nav className="erp-side" aria-label="Acme ERP sections">
        <strong>ACME ERP</strong>
        <NavLink to="/" end>
          Payment run
        </NavLink>
        <NavLink to="/vendors">Vendors</NavLink>
        <NavLink to="/new">New payment</NavLink>
        <NavLink to="/bank-file">Bank file</NavLink>
        <a href="/bank">Sandbox bank</a>
        <div style={{ flex: 1 }} />
        {user?.email ? (
          <span style={{ fontSize: 11, opacity: 0.8, wordBreak: 'break-all' }}>
            {user.email}
          </span>
        ) : null}
        <button
          type="button"
          onClick={() => void signOut()}
        >
          Sign out
        </button>
      </nav>

      <main className="erp-main">
        <div className="erp-bar">
          <span style={{ fontSize: 12, color: '#5A6169' }}>
            Acme Auto Components Pvt Ltd &middot; Accounts payable
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {env.demoMode ? <DemoModeChip /> : null}
            <span className="pm-protected">
              <PramaanMark size={18} />
              Protected by Pramaan
            </span>
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}

function ClerkRoute({ children }: { children: ReactNode }): ReactNode {
  return (
    <RoleGate
      requires="clerk"
      appName="Acme ERP"
      appDescription="Accounts payable for Acme Auto Components. Payments go through Pramaan before any money moves."
    >
      <ErpShell>{children}</ErpShell>
    </RoleGate>
  );
}

export function App(): ReactNode {
  return (
    <Routes>
      {/* Public: no sign-in, by design. The sandbox bank is a Pramaan surface. */}
      <Route path="/bank" element={<SandboxBank />} />

      <Route
        path="/"
        element={
          <ClerkRoute>
            <Payments />
          </ClerkRoute>
        }
      />
      <Route
        path="/payments/:intentId"
        element={
          <ClerkRoute>
            <PaymentStatus />
          </ClerkRoute>
        }
      />
      <Route
        path="/agent-runs/:agentRequestId"
        element={
          <ClerkRoute>
            <AgentRun />
          </ClerkRoute>
        }
      />
      <Route
        path="/vendors"
        element={
          <ClerkRoute>
            <Vendors />
          </ClerkRoute>
        }
      />
      <Route
        path="/new"
        element={
          <ClerkRoute>
            <NewPayment />
          </ClerkRoute>
        }
      />
      <Route
        path="/bank-file"
        element={
          <ClerkRoute>
            <BankFile />
          </ClerkRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
