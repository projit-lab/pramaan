import '@pramaan/shared/styles/tokens.css';
import '@pramaan/shared/styles/bundle.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';

const container = document.getElementById('root');
if (!container) {
  throw new Error('No #root element in index.html.');
}

// No AuthProvider and no router: the verifier is one public page with no sign-in,
// so it carries no Firebase dependency at all. An auditor who has never heard of
// Acme must be able to check a mandate they were handed.
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
