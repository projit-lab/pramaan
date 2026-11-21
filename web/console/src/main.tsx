import { AuthProvider, RoleGate, setDevUser } from '@pramaan/shared';
import '@pramaan/shared/styles/tokens.css';
import '@pramaan/shared/styles/bundle.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';

setDevUser('cfo');

const container = document.getElementById('root');
if (!container) {
  throw new Error('No #root element in index.html.');
}

createRoot(container).render(
  <StrictMode>
    <AuthProvider demoRole="finance" demoUser="cfo">
      <RoleGate
        requires="finance"
        appName="Pramaan console"
        appDescription="Live view of every payment Pramaan is holding, and the evidence behind each decision."
      >
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </RoleGate>
    </AuthProvider>
  </StrictMode>,
);
