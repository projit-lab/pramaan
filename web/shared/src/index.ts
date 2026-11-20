/**
 * @pramaan/shared
 *
 * Everything the Pramaan web apps share: Firebase init, Google sign-in and the
 * role gate, live Firestore hooks, the generated API client, formatting that
 * follows the Indian money and IST conventions, and the components that carry the
 * honesty rules (the AI-written label, and "couldn't verify" for a check that did
 * not run).
 */

// Environment
export {
  type FirebaseWebConfig,
  type PayoutsSource,
  type PramaanEnv,
  missingFirebaseConfig,
  readEnv,
} from './env';

// Firebase
export { env, firebaseApp, firebaseAuth, firestore, resetFirebaseForTests } from './firebase/app';

// Auth and the role gate
export { AuthProvider, type AuthState, type AuthStatus, type Role, useAuth } from './auth/AuthProvider';
export { RoleGate, type RoleGateProps } from './auth/RoleGate';
export { SignIn, type SignInProps } from './auth/SignIn';
export { NoAccess, type NoAccessProps } from './auth/NoAccess';

// Live Firestore
export {
  type LiveResult,
  type LiveStatus,
  useLiveCollection,
  useLiveDocument,
  useLiveSubcollection,
} from './firestore/useLive';

// The typed API client
export {
  type PramaanClient,
  type Problem,
  api,
  fieldErrors,
  problemMessage,
  publicApi,
  resetApiForTests,
  toProblem,
} from './api/client';

// Read-model types
export {
  COLLECTIONS,
  HOLD_STATUSES,
  type AgentLogLine,
  type AgentRequest,
  type AgentRequestStatus,
  type ApprovalEvidence,
  type Decision,
  type Device,
  type Explanation,
  type FirestoreTime,
  type Hold,
  type HoldStatus,
  type Initiator,
  type InstructionChannel,
  type InvoiceExtraction,
  type InvoiceField,
  type EntryRoute,
  type Lane,
  type PayeeChecks,
  type RuleHit,
  type KeySecurityLevel,
  type ModelArmorCategory,
  type ModelArmorFinding,
  type Payout,
  type Reason,
  type ReasonSource,
  type Step,
  type StepName,
  type WithId,
} from './types/firestore';

// Formatting
export {
  InvalidPaiseError,
  InvalidRupeeInputError,
  amountInWords,
  assertPaise,
  comparePaise,
  formatMoney,
  type FormatMoneyOptions,
  groupIndian,
  rupeesToPaise,
  splitPaise,
} from './format/money';

export {
  type TimeLike,
  formatIst,
  formatIstDate,
  formatIstTime,
  formatIstWithRelative,
  hasExpired,
  isOutsideWorkingHoursIst,
  relativeTime,
  toDate,
} from './format/time';

export {
  bankCodeFromIfsc,
  formatIfsc,
  isValidIfsc,
  lastFour,
  maskAccount,
} from './format/account';

// Components
export {
  Banner,
  type BannerTone,
  CouldNotVerify,
  EmptyState,
  type EmptyStateProps,
  ErrorState,
  type ErrorStateProps,
  LoadingState,
} from './components/States';

export {
  AiLabel,
  ChannelBadge,
  ModelArmorBadge,
  ReasonSourceTag,
  RouteBadge,
  StatusBadge,
  TierBadge,
  bandModifier,
  reasonIcon,
} from './components/Badges';

export { AmountBlock, type AmountBlockProps, Money, type MoneyProps } from './components/Money';
export { PramaanLockup, PramaanMark } from './components/PramaanMark';
export { Avatar } from './components/Avatar';
export { Icon, type IconProps } from './components/Icon';
export { StateBand, type StateBandProps } from './components/StateBand';
