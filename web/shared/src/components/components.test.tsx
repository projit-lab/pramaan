/**
 * Component tests for the pieces that carry Pramaan's honesty rules.
 *
 * These are not styling tests, and they survived the brand restyle on purpose:
 * each one pins a claim the product makes, not a colour. Colour never carries
 * meaning alone, anything Gemini wrote is labelled, a check that did not run
 * says so rather than passing, and an amount a person approves is shown in
 * words as well as figures.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  AiLabel,
  ChannelBadge,
  ModelArmorBadge,
  ReasonSourceTag,
  StatusBadge,
  TierBadge,
  bandModifier,
} from './Badges';
import { AmountBlock, Money } from './Money';
import { Banner, CouldNotVerify, EmptyState, ErrorState, LoadingState } from './States';

describe('StatusBadge', () => {
  it('always carries a word, so colour never carries meaning alone', () => {
    for (const [status, label] of [
      ['held', 'Held'],
      ['released', 'Released'],
      ['blocked', 'Blocked'],
      ['declined', 'Declined'],
      ['approved', 'Approved'],
      ['expired', 'Expired'],
    ] as const) {
      const { unmount } = render(<StatusBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it('always carries an icon beside the word', () => {
    const { container } = render(<StatusBadge status="held" />);
    expect(container.querySelector('.pm-ico')?.textContent).toBe('schedule');
  });

  it('keeps approved blue and released green, because only one means money moved', () => {
    const tone = (status: 'approved' | 'released') => {
      const { container, unmount } = render(<StatusBadge status={status} />);
      const className = container.firstElementChild?.className ?? '';
      unmount();
      return className;
    };
    expect(tone('approved')).toContain('pm-chip--approved');
    expect(tone('released')).toContain('pm-chip--released');
    expect(tone('approved')).not.toContain('released');
  });
});

describe('bandModifier', () => {
  it('maps a status to the band colour: amber held, green released, red stopped', () => {
    expect(bandModifier('held')).toBe('pm-band--held');
    expect(bandModifier('released')).toBe('pm-band--released');
    expect(bandModifier('blocked')).toBe('pm-band--blocked');
    expect(bandModifier('declined')).toBe('pm-band--blocked');
  });

  it('leaves the band blue at rest', () => {
    expect(bandModifier('approved')).toBe('');
    expect(bandModifier(null)).toBe('');
  });
});

describe('TierBadge', () => {
  it('names the tier', () => {
    render(<TierBadge tier={2} />);
    expect(screen.getByText(/Tier 2/)).toBeInTheDocument();
  });

  it('explains what the tier means, without shouting it', () => {
    const { container } = render(<TierBadge tier={2} />);
    expect(container.firstElementChild?.getAttribute('title')).toBe('Spoken confirmation');
  });

  it('renders a tier it has no name for without inventing one', () => {
    render(<TierBadge tier={9} />);
    expect(screen.getByText(/Tier 9/)).toBeInTheDocument();
  });
});

describe('AiLabel', () => {
  it('uses the brand kit wording', () => {
    render(<AiLabel />);
    expect(screen.getByText('AI summary · Gemini')).toBeInTheDocument();
  });

  it('distinguishes reading fields from writing an explanation', () => {
    render(<AiLabel variant="extraction" />);
    expect(screen.getByText('AI extraction · Gemini')).toBeInTheDocument();
  });
});

describe('ReasonSourceTag', () => {
  it('distinguishes a rule from something Gemini wrote', () => {
    const { unmount } = render(<ReasonSourceTag source="rule" />);
    expect(screen.getByText('rule')).toBeInTheDocument();
    unmount();

    render(<ReasonSourceTag source="gemini" />);
    expect(screen.getByText('AI-written')).toBeInTheDocument();
  });

  it('marks a Model Armor finding as its own source, not as Gemini', () => {
    render(<ReasonSourceTag source="model_armor" />);
    expect(screen.getByText('Model Armor')).toBeInTheDocument();
  });
});

describe('ModelArmorBadge', () => {
  it('names the finding in plain words', () => {
    render(<ModelArmorBadge category="prompt_injection" />);
    expect(screen.getByText('Prompt injection')).toBeInTheDocument();
  });
});

describe('ChannelBadge', () => {
  it('says how the instruction arrived', () => {
    const { unmount } = render(<ChannelBadge channel="chat" />);
    expect(screen.getByText('Instruction by chat')).toBeInTheDocument();
    unmount();

    render(<ChannelBadge channel="agent" />);
    expect(screen.getByText('Raised by an AI agent')).toBeInTheDocument();
  });
});

describe('Money', () => {
  it('shows rupees with Indian grouping', () => {
    render(<Money paise="465000000" />);
    expect(screen.getByText('₹46,50,000')).toBeInTheDocument();
  });

  it('shows a dash rather than a number it made up', () => {
    const { container } = render(<Money paise="not-a-number" />);
    expect(container.textContent).toBe('—');
    expect(container.textContent).not.toContain('0');
  });
});

describe('AmountBlock', () => {
  it('shows the figures and the words, because this is where someone decides', () => {
    render(
      <AmountBlock
        paise="465000000"
        payeeName="Global Trade Solutions"
        payeeAccountLast4="9032"
        payeeIfsc="WXYZ0004411"
      />,
    );
    expect(screen.getByText('₹46,50,000')).toBeInTheDocument();
    expect(screen.getByText('forty-six lakh fifty thousand rupees')).toBeInTheDocument();
  });

  it('names the payee and masks the account', () => {
    render(
      <AmountBlock paise="98000000" payeeName="Sri Lakshmi Castings" payeeAccountLast4="7781" />,
    );
    expect(screen.getByText('Sri Lakshmi Castings')).toBeInTheDocument();
    expect(screen.getByText(/7781/)).toBeInTheDocument();
    expect(screen.queryByText(/000123457781/)).not.toBeInTheDocument();
  });

  it('shows a dash rather than invent an amount it cannot parse', () => {
    render(<AmountBlock paise="oops" payeeName="Kaveri Steel Traders" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('CouldNotVerify', () => {
  it('says a check could not be verified, and never that it passed or failed', () => {
    render(<CouldNotVerify what="the signing key" />);
    const text = screen.getByText(/Couldn/).textContent ?? '';
    expect(text).toContain('the signing key');
    expect(text.toLowerCase()).not.toContain('pass');
    expect(text.toLowerCase()).not.toContain('fail');
    expect(text.toLowerCase()).not.toContain('fraud');
  });
});

describe('the three states every screen has', () => {
  it('renders a loading state that a screen reader announces', () => {
    render(<LoadingState label="Loading held payments" />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading held payments');
  });

  it('renders an empty state that reads as calm, not as a failure', () => {
    render(
      <EmptyState
        title="Nothing is waiting"
        detail="Payments that need an approver will show up here."
      />,
    );
    expect(screen.getByText('Nothing is waiting')).toBeInTheDocument();
    expect(screen.getByText(/will show up here/)).toBeInTheDocument();
  });

  it('renders an error state as an alert, without calling anything fraud', () => {
    render(<ErrorState title="We could not load the board" error={new Error('offline')} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('We could not load the board');
    expect(alert).toHaveTextContent('offline');
    expect(alert.textContent?.toLowerCase()).not.toContain('fraud');
  });
});

describe('Banner', () => {
  it('states the fact and whether money moved', () => {
    render(<Banner tone="released">Released. The money has left the account.</Banner>);
    expect(screen.getByText(/The money has left the account/)).toBeInTheDocument();
  });

  it('uses the tone the caller asked for', () => {
    const { container } = render(<Banner tone="held">Waiting.</Banner>);
    expect(container.firstElementChild?.className).toContain('pm-banner--held');
  });
});
