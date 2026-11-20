/**
 * Status, tier and reason badges.
 *
 * Colour carries meaning only, and never alone: amber held, red blocked or
 * declined, green released, each always with its own text. The same mapping is
 * used in the console, the mock ERP and the sandbox bank, so a judge watching two
 * screens side by side sees one language.
 */

import type { ReactNode } from 'react';
import type { HoldStatus, ModelArmorCategory, ReasonSource } from '../types/firestore';

const STATUS_LABELS: Record<HoldStatus, string> = {
  held: 'Held',
  approved: 'Approved',
  declined: 'Declined',
  released: 'Released',
  blocked: 'Blocked',
  expired: 'Expired',
};

/** amber held, green released, red blocked and declined, grey the rest. */
const STATUS_TONES: Record<HoldStatus, string> = {
  held: 'amber',
  approved: 'blue',
  declined: 'red',
  released: 'green',
  blocked: 'red',
  expired: 'grey',
};

export function StatusBadge({ status }: { status: HoldStatus }): ReactNode {
  const tone = STATUS_TONES[status] ?? 'grey';
  const label = STATUS_LABELS[status] ?? status;
  return (
    <span className={`pr-badge pr-badge--${tone}`} data-status={status}>
      {label}
    </span>
  );
}

const TIER_NAMES: Record<number, string> = {
  0: 'Pass',
  1: 'Signed approval',
  2: 'Spoken confirmation',
  3: 'Two people and a call-back',
};

export function TierBadge({ tier }: { tier: number }): ReactNode {
  const name = TIER_NAMES[tier];
  return (
    <span className={`pr-badge pr-badge--tier${tier}`} title={name ?? undefined}>
      Tier {tier}
      {name ? <span className="pr-badge__sub">{name}</span> : null}
    </span>
  );
}

/**
 * The label that must sit on anything Gemini wrote.
 *
 * The build plan's wording, kept word for word so it reads the same on every
 * screen: "Explanation written by Gemini; rules made the decision".
 */
export function AiLabel({
  variant = 'explanation',
}: {
  variant?: 'explanation' | 'extraction' | 'answer';
}): ReactNode {
  const text =
    variant === 'explanation'
      ? 'Explanation written by Gemini; rules made the decision'
      : variant === 'extraction'
        ? 'Fields read by Gemini; compared against the vendor master by rules'
        : 'Answer written by Gemini from the ledger';
  return (
    <span className="pr-ailabel">
      <span className="pr-ailabel__dot" aria-hidden="true" />
      {text}
    </span>
  );
}

/** A small marker beside a single reason, saying where that reason came from. */
export function ReasonSourceTag({ source }: { source: ReasonSource }): ReactNode {
  if (source === 'rule') {
    return <span className="pr-tag pr-tag--rule">Rule</span>;
  }
  if (source === 'gemini') {
    return <span className="pr-tag pr-tag--ai">AI-written</span>;
  }
  return <span className="pr-tag pr-tag--armor">Model Armor</span>;
}

const ARMOR_LABELS: Record<ModelArmorCategory, string> = {
  prompt_injection: 'Prompt injection',
  jailbreak: 'Jailbreak attempt',
  malicious_url: 'Malicious link',
  sensitive_data: 'Sensitive data',
};

export function ModelArmorBadge({ category }: { category: ModelArmorCategory }): ReactNode {
  return (
    <span className="pr-badge pr-badge--red" data-armor={category}>
      {ARMOR_LABELS[category] ?? 'Finding'}
    </span>
  );
}

const CHANNEL_LABELS: Record<string, string> = {
  portal: 'Keyed in the ERP',
  email: 'Instruction by email',
  chat: 'Instruction by chat',
  phone: 'Instruction by phone',
  agent: 'Raised by an AI agent',
};

export function ChannelBadge({ channel }: { channel: string }): ReactNode {
  const tone = channel === 'chat' || channel === 'agent' ? 'amber' : 'grey';
  return (
    <span className={`pr-badge pr-badge--${tone}`}>
      {CHANNEL_LABELS[channel] ?? channel}
    </span>
  );
}
