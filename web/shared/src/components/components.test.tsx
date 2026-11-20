/**
 * Component tests for the pieces that carry Pramaan's honesty rules.
 *
 * These are not styling tests. Each one pins a claim the product makes:
 * colour never carries meaning alone, anything Gemini wrote is labelled, a check
 * that did not run says so rather than passing, and an amount a person approves
 * is shown in words as well as figures.
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
} from './Badges';
import { Money } from './Money';
import { CouldNotVerify, EmptyState, ErrorState, LoadingState } from './States';

describe('StatusBadge', () => {
  it('always carries text, so colour never carries meaning alone', () => {
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

  it('uses amber for held, green for released and red for blocked and declined', () => {
    const tone = (status: 'held' | 'released' | 'blocked' | 'declined') => {
      const { container, unmount } = render(<StatusBadge status={status} />);
      const className = container.firstElementChild?.className ?? '';
      unmount();
      return className;
    };
    expect(tone('held')).toContain('pr-badge--amber');
    expect(tone('released')).toContain('pr-badge--green');
    expect(tone('blocked')).toContain('pr-badge--red');
    expect(tone('declined')).toContain('pr-badge--red');
  });
});

describe('TierBadge', () => {
  it('names the tier and what it means', () => {
    render(<TierBadge tier={2} />);
    expect(screen.getByText(/Tier 2/)).toBeInTheDocument();
    expect(screen.getByText('Spoken confirmation')).toBeInTheDocument();
  });

  it('renders a tier it does not have a name for without inventing one', () => {
    render(<TierBadge tier={9} />);
    expect(screen.getByText(/Tier 9/)).toBeInTheDocument();
  });
});

describe('AiLabel', () => {
  it('uses the exact wording the build plan asks for', () => {
    render(<AiLabel />);
    expect(
      screen.getByText('Explanation written by Gemini; rules made the decision'),
    ).toBeInTheDocument();
  });

  it('says rules did the comparing when Gemini only read fields', () => {
    render(<AiLabel variant="extraction" />);
    expect(screen.getByText(/read by Gemini/)).toBeInTheDocument();
    expect(screen.getByText(/compared against the vendor master by rules/)).toBeInTheDocument();
  });
});

describe('ReasonSourceTag', () => {
  it('distinguishes a rule from something Gemini wrote', () => {
    const { unmount } = render(<ReasonSourceTag source="rule" />);
    expect(screen.getByText('Rule')).toBeInTheDocument();
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

  it('shows the amount in words where a person decides on it', () => {
    render(<Money paise="465000000" withWords />);
    expect(screen.getByText('forty-six lakh fifty thousand rupees')).toBeInTheDocument();
  });

  it('shows a dash rather than a number it made up', () => {
    const { container } = render(<Money paise="not-a-number" />);
    expect(container.textContent).toBe('—');
    expect(container.textContent).not.toContain('0');
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
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Loading held payments');
  });

  it('renders an empty state with its own wording', () => {
    render(
      <EmptyState
        title="No payments held yet"
        detail="A payment appears here the moment a rule holds it."
      />,
    );
    expect(screen.getByText('No payments held yet')).toBeInTheDocument();
    expect(screen.getByText(/the moment a rule holds it/)).toBeInTheDocument();
  });

  it('renders an error state as an alert, without calling anything fraud', () => {
    render(<ErrorState title="Could not load the holds board" error={new Error('offline')} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Could not load the holds board');
    expect(alert).toHaveTextContent('offline');
    expect(alert.textContent?.toLowerCase()).not.toContain('fraud');
  });
});
