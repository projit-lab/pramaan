/**
 * Tests for the invoice panel.
 *
 * The claim being pinned: Gemini read the fields, a rule compared them. The panel
 * must label the reading as AI-written, show the comparison as a plain fact, and
 * never turn "the model could not find this" into "these disagree".
 */

import type { InvoiceExtraction } from '@pramaan/shared';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { InvoicePanel } from './InvoicePanel';

/** The poisoned Kaveri Steel invoice: the account does not match the master. */
const poisoned: InvoiceExtraction = {
  source: 'gemini',
  modelVersion: null,
  fileUrl: null,
  ref: 'KAVERI-4471',
  fields: {
    vendor_name: {
      extracted: 'Kaveri Steel Traders',
      onRecord: 'Kaveri Steel Traders',
      mismatch: false,
    },
    account: { extracted: '000123458117', onRecord: '556677885540', mismatch: true },
    ifsc: { extracted: 'EFGH0005540', onRecord: 'EFGH0005540', mismatch: false },
    amount_paise: { extracted: '184000000', onRecord: null, mismatch: false },
    invoice_date: { extracted: null, onRecord: null, mismatch: false },
  },
};

const clean: InvoiceExtraction = {
  source: 'gemini',
  fields: {
    vendor_name: {
      extracted: 'Sri Lakshmi Castings',
      onRecord: 'Sri Lakshmi Castings',
      mismatch: false,
    },
    account: { extracted: '000123457781', onRecord: '000123457781', mismatch: false },
  },
};

describe('with no invoice', () => {
  it('says there is nothing to compare, and claims nothing', () => {
    render(<InvoicePanel invoice={null} />);
    expect(screen.getByText(/No invoice was attached/)).toBeInTheDocument();
    expect(screen.queryByText(/mismatch/i)).not.toBeInTheDocument();
  });
});

describe('the poisoned invoice', () => {
  it('counts the mismatches', () => {
    render(<InvoicePanel invoice={poisoned} />);
    expect(screen.getByText('1 mismatch')).toBeInTheDocument();
  });

  it('shows the invoice account beside the one on record', () => {
    render(<InvoicePanel invoice={poisoned} />);
    const row = screen.getByRole('row', { name: /Bank account/ });
    expect(within(row).getByText('000123458117')).toBeInTheDocument();
    expect(within(row).getByText('556677885540')).toBeInTheDocument();
  });

  it('marks only the mismatching row', () => {
    const { container } = render(<InvoicePanel invoice={poisoned} />);
    const flagged = container.querySelectorAll('tr[data-mismatch="true"]');
    expect(flagged).toHaveLength(1);
    expect(flagged[0]?.textContent).toContain('000123458117');
  });

  it('labels the extracted fields as AI-written', () => {
    render(<InvoicePanel invoice={poisoned} />);
    expect(screen.getByText(/read by Gemini/)).toBeInTheDocument();
    expect(screen.getByText(/compared against the vendor master by rules/)).toBeInTheDocument();
  });

  it('says the comparison is a rule, not the model', () => {
    render(<InvoicePanel invoice={poisoned} />);
    expect(screen.getByText(/comparison is a rule, not a judgement by the model/)).toBeInTheDocument();
  });

  it('renders a paise amount as money, not as raw digits', () => {
    render(<InvoicePanel invoice={poisoned} />);
    expect(screen.getByText('₹18,40,000')).toBeInTheDocument();
    expect(screen.queryByText('184000000')).not.toBeInTheDocument();
  });

  it('treats a field the model could not find as absent, not as a mismatch', () => {
    render(<InvoicePanel invoice={poisoned} />);
    const row = screen.getByRole('row', { name: /Invoice date/ });
    expect(within(row).getByText('Not found on the invoice')).toBeInTheDocument();
    expect(row.getAttribute('data-mismatch')).toBeNull();
  });

  it('says when the file itself cannot be shown, rather than showing a blank box', () => {
    render(<InvoicePanel invoice={poisoned} />);
    expect(screen.getByText(/not available to show here/)).toBeInTheDocument();
    expect(screen.getByText(/KAVERI-4471/)).toBeInTheDocument();
  });

  it('never calls a mismatch fraud', () => {
    const { container } = render(<InvoicePanel invoice={poisoned} />);
    expect(container.textContent?.toLowerCase()).not.toContain('fraud');
  });
});

describe('a clean invoice', () => {
  it('says it matches the vendor master', () => {
    render(<InvoicePanel invoice={clean} />);
    expect(screen.getByText('Matches the vendor master')).toBeInTheDocument();
  });

  it('still labels the extraction as AI-written', () => {
    render(<InvoicePanel invoice={clean} />);
    expect(screen.getByText(/read by Gemini/)).toBeInTheDocument();
  });

  it('does not show the mismatch footnote', () => {
    render(<InvoicePanel invoice={clean} />);
    expect(screen.queryByText(/comparison is a rule/)).not.toBeInTheDocument();
  });
});

describe('several mismatches', () => {
  it('pluralises the count', () => {
    render(
      <InvoicePanel
        invoice={{
          source: 'gemini',
          fields: {
            account: { extracted: 'a', onRecord: 'b', mismatch: true },
            ifsc: { extracted: 'c', onRecord: 'd', mismatch: true },
          },
        }}
      />,
    );
    expect(screen.getByText('2 mismatches')).toBeInTheDocument();
  });
});
