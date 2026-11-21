import { AuthProvider, setDevUser } from '@pramaan/shared';
import '@pramaan/shared/styles/tokens.css';
import '@pramaan/shared/styles/bundle.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';

setDevUser('clerk');

const container = document.getElementById('root');
if (!container) {
  throw new Error('No #root element in index.html.');
}

// The role gate is applied per route rather than around the whole app, because
// the sandbox bank page is public: an auditor or a judge must be able to open it
// without signing in to anything.
createRoot(container).render(
  <StrictMode>
    <AuthProvider demoRole="clerk" demoUser="clerk">
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
