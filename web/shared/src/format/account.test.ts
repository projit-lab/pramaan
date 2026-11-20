import { describe, expect, it } from 'vitest';
import { bankCodeFromIfsc, formatIfsc, isValidIfsc, lastFour, maskAccount } from './account';

describe('maskAccount', () => {
  it('masks all but the last four digits', () => {
    expect(maskAccount('7781')).toBe('•••• 7781');
    expect(maskAccount('0032')).toBe('•••• 0032');
  });

  it('shows a dash rather than a half-masked guess', () => {
    expect(maskAccount(null)).toBe('—');
    expect(maskAccount(undefined)).toBe('—');
    expect(maskAccount('')).toBe('—');
    expect(maskAccount('77')).toBe('—');
    expect(maskAccount('abcd')).toBe('—');
  });
});

describe('lastFour', () => {
  it('takes the last four digits of a full account number', () => {
    expect(lastFour('000123457781')).toBe('7781');
    expect(lastFour('50100004521')).toBe('4521');
  });

  it('ignores separators', () => {
    expect(lastFour('0001 2345 7781')).toBe('7781');
  });

  it('keeps leading zeros that fall in the last four', () => {
    expect(lastFour('123450032')).toBe('0032');
  });

  it('returns null when there is not enough to work with', () => {
    expect(lastFour(null)).toBeNull();
    expect(lastFour('123')).toBeNull();
  });
});

describe('isValidIfsc', () => {
  it('accepts the demo codes', () => {
    expect(isValidIfsc('ABCD0123456')).toBe(true);
    expect(isValidIfsc('WXYZ0004411')).toBe(true);
    expect(isValidIfsc('efgh0005540')).toBe(true);
  });

  it('rejects anything else', () => {
    expect(isValidIfsc('ABC0123456')).toBe(false);
    expect(isValidIfsc('ABCD1123456')).toBe(false);
    expect(isValidIfsc('ABCD012345')).toBe(false);
    expect(isValidIfsc('')).toBe(false);
    expect(isValidIfsc(null)).toBe(false);
  });
});

describe('formatIfsc', () => {
  it('trims and upper-cases', () => {
    expect(formatIfsc('  abcd0123456 ')).toBe('ABCD0123456');
  });

  it('shows a dash when absent', () => {
    expect(formatIfsc(null)).toBe('—');
  });
});

describe('bankCodeFromIfsc', () => {
  it('returns the four-letter bank code', () => {
    expect(bankCodeFromIfsc('ABCD0123456')).toBe('ABCD');
  });

  it('returns null for an invalid code', () => {
    expect(bankCodeFromIfsc('nope')).toBeNull();
  });
});
