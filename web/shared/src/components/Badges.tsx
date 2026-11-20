/**
 * Status chips, tier badges, reason chips and the AI label.
 *
 * Two rules from the brand kit are enforced here rather than left to each
 * screen:
 *
 *   - **Colour never carries meaning alone.** Every chip has an icon and a
 *     word. Nothing is distinguished by colour only.
 *   - **Approved is blue, not green.** Green is kept for money that actually
 *     moved. A signed approval is not a released payment, and showing both in
 *     green would blur the one distinction the product exists to make.
 */

import type { ReactNode } from 'react';
import type { EntryRoute, HoldStatus, ModelArmorCategory, ReasonSource } from '../types/firestore';
import { Icon } from './Icon';

interface ChipLook {
  className: string;
  icon: string;
  label: string;
}

const STATUS_LOOK: Record<HoldStatus, ChipLook> = {
  held: { className: 'pm-chip--held', icon: 'schedule', label: 'Held' },
  approved: { className: 'pm-chip--approved', icon: 'draw', label: 'Approved' },
  released: { className: 'pm-chip--released', icon: 'check_circle', label: 'Released' },
  declined: { className: 'pm-chip--declined', icon: 'block', label: 'Declined' },
  blocked: { className: 'pm-chip--blocked', icon: 'gpp_bad', label: 'Blocked' },
  expired: { className: 'pm-chip--expired', icon: 'timer_off', label: 'Expired' },
};

export function StatusBadge({
  status,
  onBand = false,
}: {
  status: HoldStatus;
  /** On a coloured band the chip sits on white, so it stays readable. */
  onBand?: boolean;
}): ReactNode {
  const look = STATUS_LOOK[status];
  if (!look) {
    return <span className="pm-chip pm-chip--expired">{status}</span>;
  }
  return (
    <span
      className={`pm-chip ${look.className}`}
      style={onBand ? { background: 'var(--background)' } : undefined}
      data-status={status}
    >
      <Icon name={look.icon} />
      {look.label}
    </span>
  );
}

/** Which band colour a status gets. Blue at rest, amber held, green released, red stopped. */
export function bandModifier(status: HoldStatus | null | undefined): string {
  if (status === 'held') return 'pm-band--held';
  if (status === 'released') return 'pm-band--released';
  if (status === 'blocked' || status === 'declined') return 'pm-band--blocked';
  return '';
}

/**
 * The risk tier the rules gave a payment. A small radius, not a pill, so it
 * never reads as a status. Always beside the status chip, never instead of it.
 */
export function TierBadge({ tier }: { tier: number }): ReactNode {
  const names: Record<number, string> = {
    0: 'Pass',
    1: 'Signed approval',
    2: 'Spoken confirmation',
    3: 'Two people and a call-back',
  };
  return (
    <span className={`pm-tier pm-tier--${tier}`} title={names[tier]}>
      Tier {tier}
    </span>
  );
}

/** Icons for the rule codes we know. Anything else gets a neutral marker. */
const REASON_ICONS: Record<string, string> = {
  new_payee: 'person_add',
  bank_details_changed: 'account_balance',
  lookalike_vendor: 'content_copy',
  amount_above_5_lakh: 'trending_up',
  amount_above_25_lakh: 'trending_up',
  unusual_amount: 'trending_up',
  outside_working_hours: 'bedtime',
  raised_by_agent: 'smart_toy',
  instruction_by_chat: 'chat',
  instruction_by_email: 'mail',
  pressure_language: 'priority_high',
  invoice_account_mismatch: 'rule',
  model_armor_finding: 'gpp_bad',
};

export function reasonIcon(code: string): string {
  return REASON_ICONS[code] ?? 'label';
}

/**
 * The label that must sit on anything Gemini wrote.
 *
 * The kit's wording, kept exactly: "AI summary · Gemini", with the note that
 * rules made the decision.
 */
export function AiLabel({
  variant = 'explanation',
}: {
  variant?: 'explanation' | 'extraction' | 'answer';
}): ReactNode {
  const text =
    variant === 'extraction'
      ? 'AI extraction · Gemini'
      : variant === 'answer'
        ? 'AI answer · Gemini'
        : 'AI summary · Gemini';
  return (
    <div className="pm-ai__label">
      <Icon name="auto_awesome" fill size="sm" />
      {text}
    </div>
  );
}

/** A small marker beside one reason, saying where that reason came from. */
export function ReasonSourceTag({ source }: { source: ReasonSource }): ReactNode {
  if (source === 'rule') return <b>rule</b>;
  if (source === 'gemini') return <b>AI-written</b>;
  return <b>Model Armor</b>;
}

const ARMOR_LABELS: Record<ModelArmorCategory, string> = {
  prompt_injection: 'Prompt injection',
  jailbreak: 'Jailbreak attempt',
  malicious_url: 'Malicious link',
  sensitive_data: 'Sensitive data',
};

export function ModelArmorBadge({ category }: { category: ModelArmorCategory }): ReactNode {
  return (
    <span className="pm-chip pm-chip--blocked" data-armor={category}>
      <Icon name="gpp_bad" />
      {ARMOR_LABELS[category] ?? 'Finding'}
    </span>
  );
}

const CHANNEL_LOOK: Record<string, { icon: string; label: string; loud: boolean }> = {
  portal: { icon: 'keyboard', label: 'Keyed in the ERP', loud: false },
  email: { icon: 'mail', label: 'Instruction by email', loud: false },
  chat: { icon: 'chat', label: 'Instruction by chat', loud: true },
  phone: { icon: 'call', label: 'Instruction by phone', loud: false },
  agent: { icon: 'smart_toy', label: 'Raised by an AI agent', loud: true },
};

export function ChannelBadge({ channel }: { channel: string }): ReactNode {
  const look = CHANNEL_LOOK[channel] ?? { icon: 'label', label: channel, loud: false };
  return (
    <span className={`pm-chip ${look.loud ? 'pm-chip--held' : 'pm-chip--expired'}`}>
      <Icon name={look.icon} />
      {look.label}
    </span>
  );
}

/**
 * Which door a payment came through.
 *
 * Four systems can start a payment and the demo fires all four at once. The
 * badge exists so an approver and the console can see that the gate treated
 * them identically: a bank file gets no more trust than a human typing, and an
 * agent gets no less scrutiny than either. The route is a fact about where the
 * instruction arrived from, never a judgement about it, so none of these is
 * coloured as a warning.
 */
const ROUTE_LOOK: Record<EntryRoute, { icon: string; label: string }> = {
  erp: { icon: 'desktop_windows', label: 'From the ERP' },
  bank_file: { icon: 'description', label: 'From a bank file' },
  payout_api: { icon: 'api', label: 'From the payout API' },
  agent: { icon: 'smart_toy', label: 'From an AI agent' },
};

export function RouteBadge({ route }: { route: EntryRoute | null | undefined }): ReactNode {
  // A row written before the doors existed says nothing rather than guessing
  // "ERP", which would be a claim about provenance we cannot support.
  if (!route) return null;
  const look = ROUTE_LOOK[route];
  if (!look) return null;
  return (
    <span className="pm-chip pm-chip--route" data-route={route}>
      <Icon name={look.icon} size="sm" />
      {look.label}
    </span>
  );
}
