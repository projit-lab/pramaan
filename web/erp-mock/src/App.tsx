/**
 * Acme ERP, the mock customer system.
 *
 * Two products are on screen in this demo. This app is the customer's own
 * software: a fictional company, Acme Auto Components Pvt Ltd, with an accounts
 * clerk who keys payments. Pramaan is the control it plugs into, and the ERP's
 * Pay button goes through Pramaan.
 *
 * The clerk can never approve. That is not a missing feature; it is the point.
 */

import { AppHeader, RoleGate, useAuth } from '@pramaan/shared';
import type { ReactNode } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { AgentRun } from './pages/AgentRun';
import { NewPayment } from './pages/NewPayment';
import { PaymentStatus } from './pages/PaymentStatus';
import { Payments } from './pages/Payments';
import { SandboxBank } from './pages/SandboxBank';
import { Vendors } from './pages/Vendors';

function ErpShell({ children }: { children: ReactNode }): ReactNode {
  const { user, signOut } = useAuth();
  return (
    <div className="pr-shell">
      <AppHeader
        appName="Acme ERP"
        email={user?.email ?? null}
        onSignOut={signOut}
        nav={
          <>
            <NavLink to="/" className="pr-navlink" end>
              Payments
            </NavLink>
            <NavLink to="/vendors" className="pr-navlink">
              Vendors
            </NavLink>
            <NavLink to="/new" className="pr-navlink">
              New payment
            </NavLink>
          </>
        }
      >
        <span className="pr-badge pr-badge--grey">Protected by Pramaan</span>
      </AppHeader>
      <main className="pr-main">{children}</main>
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
      {/* Public: no sign-in, by design. */}
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
