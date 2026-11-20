/**
 * The live read model, typed to match contracts/firestore.md.
 *
 * These are hand-written rather than generated, because Firestore has no schema
 * to generate from. If Prajit changes a field name in firestore.md, it changes
 * here and TypeScript points at every screen that has to change with it.
 *
 * Only the API writes these documents. Nothing in the web lane ever writes.
 */

import type { Timestamp } from 'firebase/firestore';

/** What Firestore hands back for a timestamp field, or null when unset. */
export type FirestoreTime = Timestamp | null;

export type HoldStatus =
  | 'held'
  | 'approved'
  | 'declined'
  | 'released'
  | 'blocked'
  | 'expired';

export type StepName =
  | 'created'
  | 'scored'
  | 'held'
  | 'pushed'
  | 'signed'
  | 'verified'
  // Tier 2 spoken check (M4); only on tier 2 and higher payments.
  | 'voice_started'
  | 'voice_verified'
  | 'voice_failed'
  | 'countersigned'
  | 'released'
  | 'blocked';

export type InstructionChannel = 'portal' | 'email' | 'chat' | 'phone' | 'agent';

export type KeySecurityLevel = 'StrongBox' | 'TrustedEnvironment' | 'Software';

/**
 * Where a piece of text came from. Rules decide; Gemini only explains. Anything
 * marked 'gemini' must be rendered with the AI-written label.
 */
export type ReasonSource = 'rule' | 'gemini' | 'model_armor';

export type ModelArmorCategory =
  | 'prompt_injection'
  | 'jailbreak'
  | 'malicious_url'
  | 'sensitive_data';

export interface Initiator {
  type: 'human' | 'agent';
  /** A work email for a human, or the Agent Identity for an agent. */
  id: string;
}

export interface Reason {
  code: string;
  text: string;
  source: ReasonSource;
  /** For a changed value, what it was before. The screen shows this in red. */
  changedFrom?: string | null;
  changedTo?: string | null;
}

export interface Explanation {
  text: string;
  source: 'gemini';
  modelVersion?: string | null;
}

export interface ModelArmorFinding {
  category: ModelArmorCategory;
  detail: string;
  excerpt?: string | null;
  foundAt?: FirestoreTime;
}

/** holds/{intentId} */
export interface Hold {
  intentId: string;
  status: HoldStatus;
  tier: number;
  amountPaise: string;
  currency: 'INR';
  payeeNameAtBank: string;
  payeeAccountLast4: string;
  payeeIfsc: string;
  payerAccountLast4?: string;
  purpose?: string | null;
  instructionChannel: InstructionChannel;
  instructionNote?: string | null;
  initiator: Initiator;
  reasons: Reason[];
  explanation?: Explanation | null;
  modelArmorFinding?: ModelArmorFinding | null;
  policyVersion?: string | null;
  approvers?: string[];
  approver?: string | null;
  mandateId?: string | null;
  agentRequestId?: string | null;
  payoutId?: string | null;
  createdAt: FirestoreTime;
  updatedAt?: FirestoreTime;
  expiresAt?: FirestoreTime;
}

/** holds/{intentId}/steps/{n} */
export interface Step {
  n: number;
  step: StepName;
  at: FirestoreTime;
  detail?: string | null;
}

/** devices/{deviceId} */
export interface Device {
  deviceId: string;
  approver: string;
  phoneModel?: string | null;
  keySecurityLevel: KeySecurityLevel;
  patchLevel?: string | null;
  /**
   * Null means no verdict was recorded. The screen says "couldn't verify"; it
   * never renders null as a passed check.
   */
  lastIntegrityVerdict?: string | null;
  revoked: boolean;
  enrolledAt: FirestoreTime;
}

export type AgentRequestStatus =
  | 'reading'
  | 'mandate_requested'
  | 'flagged'
  | 'held'
  | 'declined'
  | 'failed';

export interface AgentLogLine {
  at: FirestoreTime;
  text: string;
  source?: ReasonSource;
}

/** agentRequests/{agentRequestId} */
export interface AgentRequest {
  agentRequestId: string;
  agentId: string;
  invoiceRef?: string | null;
  intentId?: string | null;
  status: AgentRequestStatus;
  modelArmorFinding?: ModelArmorFinding | null;
  log?: AgentLogLine[];
  createdAt: FirestoreTime;
}

/** payouts/{payoutId} */
export interface Payout {
  payoutId: string;
  mandateId: string;
  intentId?: string | null;
  amountPaise: string;
  currency: 'INR';
  payeeNameAtBank: string;
  payeeAccountLast4: string;
  payeeIfsc: string;
  status: 'queued' | 'paid' | 'failed';
  createdAt: FirestoreTime;
}

/** A document plus its id, which is what every live hook returns. */
export type WithId<T> = T & { id: string };

/** The collection names, so no screen types a string literal by hand. */
export const COLLECTIONS = {
  holds: 'holds',
  devices: 'devices',
  agentRequests: 'agentRequests',
  payouts: 'payouts',
} as const;

export const HOLD_STATUSES: readonly HoldStatus[] = [
  'held',
  'approved',
  'released',
  'blocked',
  'declined',
  'expired',
] as const;
