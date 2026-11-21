import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '@pramaan/shared';
import { App } from './App';

describe('ERP App', () => {
  const originalEnv = process.env.VITE_DEMO_MODE;

  beforeEach(() => {
    process.env.VITE_DEMO_MODE = originalEnv;
  });

  it('renders Demo mode chip when demoMode is true', () => {
    process.env.VITE_DEMO_MODE = 'true';

    render(
      <AuthProvider demoRole="clerk" demoUser="clerk">
        <MemoryRouter initialEntries={['/']}>
          <App />
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(screen.getByTestId('demo-mode-chip')).toHaveTextContent('Demo mode');
    expect(screen.getByText('ACME ERP')).toBeInTheDocument();
  });

  it('hides Demo mode chip when demoMode is false', () => {
    process.env.VITE_DEMO_MODE = 'false';

    render(
      <AuthProvider demoRole="clerk" demoUser="clerk">
        <MemoryRouter initialEntries={['/bank']}>
          <App />
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(screen.queryByTestId('demo-mode-chip')).not.toBeInTheDocument();
  });
});
