/**
 * Money in Pramaan is an integer number of paise, carried as a string.
 * Rupees 46.5 lakh is "465000000". Only the screen formats it.
 *
 * Everything here works on BigInt and on digit strings, never on a JavaScript
 * number, because a crore-sized amount in paise has no business going through
 * floating point on its way to an approver's eyes.
 */

const DIGITS_ONLY = /^[0-9]+$/;

export class InvalidPaiseError extends Error {
  constructor(value: string) {
    super(`Not an integer number of paise: ${JSON.stringify(value)}`);
    this.name = 'InvalidPaiseError';
  }
}

/** Throws unless `paise` is a string of one or more digits. */
export function assertPaise(paise: string): void {
  if (typeof paise !== 'string' || !DIGITS_ONLY.test(paise)) {
    throw new InvalidPaiseError(String(paise));
  }
}

/** Splits paise into whole rupees and the 0-99 paise remainder. */
export function splitPaise(paise: string): { rupees: bigint; paise: number } {
  assertPaise(paise);
  const total = BigInt(paise);
  return { rupees: total / 100n, paise: Number(total % 100n) };
}

/**
 * Indian digit grouping: the last three digits, then groups of two.
 * 4650000 becomes "46,50,000".
 */
export function groupIndian(digits: string): string {
  if (!DIGITS_ONLY.test(digits)) throw new InvalidPaiseError(digits);
  const trimmed = digits.replace(/^0+(?=\d)/, '');
  if (trimmed.length <= 3) return trimmed;
  const last3 = trimmed.slice(-3);
  const rest = trimmed.slice(0, -3);
  const groups: string[] = [];
  for (let end = rest.length; end > 0; end -= 2) {
    groups.unshift(rest.slice(Math.max(0, end - 2), end));
  }
  return `${groups.join(',')},${last3}`;
}

export interface FormatMoneyOptions {
  /** Prefix with the rupee sign. Default true. */
  symbol?: boolean;
  /**
   * Show the paise. Default "auto": shown only when they are not zero, because
   * every amount in the demo seed is whole rupees and "Rupees 46,50,000.00" reads
   * worse on a holds board than "Rupees 46,50,000".
   */
  paise?: 'auto' | 'always' | 'never';
}

/**
 * Formats paise as rupees with Indian grouping.
 * formatMoney("465000000") === "₹46,50,000"
 */
export function formatMoney(paiseValue: string, options: FormatMoneyOptions = {}): string {
  const { symbol = true, paise: paiseMode = 'auto' } = options;
  const { rupees, paise } = splitPaise(paiseValue);
  const whole = groupIndian(rupees.toString());
  const showPaise = paiseMode === 'always' || (paiseMode === 'auto' && paise !== 0);
  const body = showPaise ? `${whole}.${String(paise).padStart(2, '0')}` : whole;
  return symbol ? `₹${body}` : body;
}

const ONES = [
  'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
  'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
  'seventeen', 'eighteen', 'nineteen',
] as const;

const TENS = [
  '', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety',
] as const;

/** Words for 0-99. */
function underHundred(n: number): string {
  if (n < 20) return ONES[n] ?? '';
  const tens = TENS[Math.floor(n / 10)] ?? '';
  const ones = n % 10;
  return ones === 0 ? tens : `${tens}-${ONES[ones] ?? ''}`;
}

/** Words for 0-999. */
function underThousand(n: number): string {
  if (n < 100) return underHundred(n);
  const hundreds = Math.floor(n / 100);
  const rest = n % 100;
  const head = `${ONES[hundreds] ?? ''} hundred`;
  return rest === 0 ? head : `${head} ${underHundred(rest)}`;
}

/**
 * The amount in Indian words, for the one screen where a person decides on it.
 * amountInWords("465000000") === "forty-six lakh fifty thousand rupees"
 *
 * Scales up through crore the Indian way: above 100 crore it reads
 * "one thousand two hundred crore", which is how a CFO says it.
 */
export function amountInWords(paiseValue: string): string {
  const { rupees, paise } = splitPaise(paiseValue);

  const parts: string[] = [];
  let remaining = rupees;

  const crore = remaining / 10000000n;
  remaining %= 10000000n;
  const lakh = remaining / 100000n;
  remaining %= 100000n;
  const thousand = remaining / 1000n;
  remaining %= 1000n;
  const rest = Number(remaining);

  if (crore > 0n) {
    // A crore count can itself exceed 999, so it is spelled with the same scale.
    parts.push(`${croreCountInWords(crore)} crore`);
  }
  if (lakh > 0n) parts.push(`${underHundred(Number(lakh))} lakh`);
  if (thousand > 0n) parts.push(`${underHundred(Number(thousand))} thousand`);
  if (rest > 0) parts.push(underThousand(rest));

  const rupeeWords = parts.length === 0 ? 'zero rupees' : `${parts.join(' ')} rupees`;
  if (paise === 0) return rupeeWords;
  return `${rupeeWords} and ${underHundred(paise)} paise`;
}

/** Spells a crore count, which may itself run into lakh and thousand. */
function croreCountInWords(crore: bigint): string {
  if (crore < 1000n) return underThousand(Number(crore));
  const parts: string[] = [];
  let remaining = crore;
  const lakh = remaining / 100000n;
  remaining %= 100000n;
  const thousand = remaining / 1000n;
  remaining %= 1000n;
  if (lakh > 0n) parts.push(`${underHundred(Number(lakh))} lakh`);
  if (thousand > 0n) parts.push(`${underHundred(Number(thousand))} thousand`);
  const rest = Number(remaining);
  if (rest > 0) parts.push(underThousand(rest));
  return parts.join(' ');
}

export class InvalidRupeeInputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'InvalidRupeeInputError';
  }
}

/**
 * Turns what a clerk typed into an integer number of paise.
 *
 * A person keying a payment types rupees: "980000", "9,80,000" or "9800.50".
 * The wire format is paise as a string, and the conversion has to be exact, so
 * it is done on the digits rather than by multiplying a float by 100 (which
 * turns 1234.35 rupees into 123434.99999999999 paise).
 *
 * Throws InvalidRupeeInputError with a message written for the person who typed
 * it, so a form can show it inline.
 */
export function rupeesToPaise(input: string): string {
  const cleaned = (input ?? '').replace(/[\s,₹]/g, '');

  if (cleaned === '') {
    throw new InvalidRupeeInputError('Enter an amount.');
  }
  if (cleaned.startsWith('-')) {
    throw new InvalidRupeeInputError('An amount cannot be negative.');
  }
  if (!/^\d*(\.\d*)?$/.test(cleaned)) {
    throw new InvalidRupeeInputError('Use digits only, for example 9,80,000 or 9800.50.');
  }

  const [whole = '', fraction = ''] = cleaned.split('.');
  if (whole === '' && fraction === '') {
    throw new InvalidRupeeInputError('Enter an amount.');
  }
  if (fraction.length > 2) {
    throw new InvalidRupeeInputError('Paise go to two decimal places at most.');
  }

  const paise = `${whole || '0'}${fraction.padEnd(2, '0')}`.replace(/^0+(?=\d)/, '');
  if (!/^\d+$/.test(paise)) {
    throw new InvalidRupeeInputError('Enter a valid amount.');
  }
  if (BigInt(paise) === 0n) {
    throw new InvalidRupeeInputError('An amount must be more than zero.');
  }
  return paise;
}

/**
 * Compares two paise strings, for sorting a holds board by amount.
 * Returns a negative number, zero, or a positive number.
 */
export function comparePaise(a: string, b: string): number {
  const left = BigInt(a);
  const right = BigInt(b);
  return left < right ? -1 : left > right ? 1 : 0;
}
