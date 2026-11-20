/**
 * Account numbers and IFSC codes on screen.
 *
 * Lists show only the last four digits. The full number appears on a detail page
 * behind a "Show" click, which is logged. The web lane never receives a full
 * account number in the first place for the buildathon cut: the API masks it, and
 * the only place the full number exists is inside the canonical summary the
 * approver signs on their phone.
 */

const FOUR_DIGITS = /^[0-9]{4}$/;

/** The standard IFSC shape: four letters, a zero, then six alphanumerics. */
const IFSC = /^[A-Z]{4}0[A-Z0-9]{6}$/;

/** "•••• 7781". Returns a plain dash when there is nothing to mask. */
export function maskAccount(last4: string | null | undefined): string {
  if (!last4 || !FOUR_DIGITS.test(last4)) return '—';
  return `•••• ${last4}`;
}

/**
 * Takes the last four digits of whatever account-like string arrives, so a screen
 * degrades safely if an upstream ever hands over more than it should.
 */
export function lastFour(account: string | null | undefined): string | null {
  if (!account) return null;
  const digits = account.replace(/\D/g, '');
  if (digits.length < 4) return null;
  return digits.slice(-4);
}

/** True when the string looks like a valid IFSC code. Display validation only. */
export function isValidIfsc(ifsc: string | null | undefined): boolean {
  if (!ifsc) return false;
  return IFSC.test(ifsc.trim().toUpperCase());
}

/** Normalises an IFSC for display: trimmed and upper-case. */
export function formatIfsc(ifsc: string | null | undefined): string {
  if (!ifsc) return '—';
  return ifsc.trim().toUpperCase();
}

/**
 * The bank's four-letter code, which is the part a person recognises.
 * formatIfsc("abcd0123456") -> "ABCD0123456", bankCodeFromIfsc -> "ABCD"
 */
export function bankCodeFromIfsc(ifsc: string | null | undefined): string | null {
  if (!isValidIfsc(ifsc)) return null;
  return (ifsc as string).trim().toUpperCase().slice(0, 4);
}
