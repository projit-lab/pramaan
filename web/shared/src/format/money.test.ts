import { describe, expect, it } from 'vitest';
import {
  InvalidPaiseError,
  amountInWords,
  comparePaise,
  formatMoney,
  groupIndian,
  rupeesToPaise,
  splitPaise,
} from './money';

describe('groupIndian', () => {
  it('leaves three digits or fewer alone', () => {
    expect(groupIndian('0')).toBe('0');
    expect(groupIndian('7')).toBe('7');
    expect(groupIndian('999')).toBe('999');
  });

  it('groups the last three digits, then twos', () => {
    expect(groupIndian('1000')).toBe('1,000');
    expect(groupIndian('98000')).toBe('98,000');
    expect(groupIndian('980000')).toBe('9,80,000');
    expect(groupIndian('4650000')).toBe('46,50,000');
    expect(groupIndian('10400000')).toBe('1,04,00,000');
    expect(groupIndian('1000000000')).toBe('1,00,00,00,000');
  });

  it('drops leading zeros but keeps a lone zero', () => {
    expect(groupIndian('0004650000')).toBe('46,50,000');
    expect(groupIndian('000')).toBe('0');
  });
});

describe('splitPaise', () => {
  it('splits rupees from paise', () => {
    expect(splitPaise('465000000')).toEqual({ rupees: 4650000n, paise: 0 });
    expect(splitPaise('98000050')).toEqual({ rupees: 980000n, paise: 50 });
    expect(splitPaise('7')).toEqual({ rupees: 0n, paise: 7 });
  });

  it('rejects anything that is not an integer number of paise', () => {
    expect(() => splitPaise('4650.00')).toThrow(InvalidPaiseError);
    expect(() => splitPaise('-100')).toThrow(InvalidPaiseError);
    expect(() => splitPaise('')).toThrow(InvalidPaiseError);
    expect(() => splitPaise('1e5')).toThrow(InvalidPaiseError);
  });
});

describe('formatMoney', () => {
  it('formats the build plan and demo amounts', () => {
    // The boss-scam amount, and INOX's real first transfer.
    expect(formatMoney('465000000')).toBe('₹46,50,000');
    // The genuine invoice INV-2219.
    expect(formatMoney('98000000')).toBe('₹9,80,000');
    // The poisoned Kaveri Steel invoice.
    expect(formatMoney('184000000')).toBe('₹18,40,000');
    // The Tier 2 voice scenario.
    expect(formatMoney('300000000')).toBe('₹30,00,000');
  });

  it('formats a crore-sized amount', () => {
    // INOX's total loss: Rupees 10.40 crore.
    expect(formatMoney('10400000000')).toBe('₹10,40,00,000');
  });

  it('can drop the rupee sign', () => {
    expect(formatMoney('465000000', { symbol: false })).toBe('46,50,000');
  });

  it('shows paise only when there are some', () => {
    expect(formatMoney('98000050')).toBe('₹9,80,000.50');
    expect(formatMoney('98000000', { paise: 'always' })).toBe('₹9,80,000.00');
    expect(formatMoney('98000050', { paise: 'never' })).toBe('₹9,80,000');
  });

  it('keeps full precision far beyond a double', () => {
    expect(formatMoney('123456789012345678')).toBe('₹1,23,45,67,89,01,23,456.78');
  });
});

describe('amountInWords', () => {
  it('matches the wording the build plan asks for', () => {
    expect(amountInWords('465000000')).toBe('forty-six lakh fifty thousand rupees');
  });

  it('spells the demo amounts', () => {
    expect(amountInWords('98000000')).toBe('nine lakh eighty thousand rupees');
    expect(amountInWords('184000000')).toBe('eighteen lakh forty thousand rupees');
    expect(amountInWords('300000000')).toBe('thirty lakh rupees');
  });

  it('spells crore amounts', () => {
    // INOX's total loss: Rupees 10.40 crore, which is 10,40,00,000 rupees.
    expect(amountInWords('10400000000')).toBe('ten crore forty lakh rupees');
    // Ten crore rupees in paise is 10^10, one crore rupees is 10^9.
    expect(amountInWords('10000000000')).toBe('ten crore rupees');
    expect(amountInWords('1000000000')).toBe('one crore rupees');
    // The Tier 3 threshold: above Rupees 1 crore.
    expect(amountInWords('1000100000')).toBe('one crore one thousand rupees');
  });

  it('spells hundreds and tens', () => {
    expect(amountInWords('50000')).toBe('five hundred rupees');
    expect(amountInWords('123400')).toBe('one thousand two hundred thirty-four rupees');
    expect(amountInWords('1900')).toBe('nineteen rupees');
    expect(amountInWords('0')).toBe('zero rupees');
  });

  it('spells the paise when there are some', () => {
    expect(amountInWords('98000050')).toBe('nine lakh eighty thousand rupees and fifty paise');
    expect(amountInWords('1')).toBe('zero rupees and one paise');
  });

  it('spells a crore count above a thousand', () => {
    // Rupees 1,200 crore.
    expect(amountInWords('1200000000000')).toBe('one thousand two hundred crore rupees');
  });
});

describe('rupeesToPaise', () => {
  it('converts what a clerk actually types', () => {
    expect(rupeesToPaise('980000')).toBe('98000000');
    expect(rupeesToPaise('9,80,000')).toBe('98000000');
    expect(rupeesToPaise('₹ 46,50,000')).toBe('465000000');
    expect(rupeesToPaise(' 4650000 ')).toBe('465000000');
  });

  it('keeps paise exact, without going through a float', () => {
    // 1234.35 * 100 is 123434.99999999999 in floating point.
    expect(rupeesToPaise('1234.35')).toBe('123435');
    expect(rupeesToPaise('0.01')).toBe('1');
    expect(rupeesToPaise('9800.5')).toBe('980050');
    expect(rupeesToPaise('.5')).toBe('50');
  });

  it('handles amounts far beyond a safe integer', () => {
    expect(rupeesToPaise('1234567890123456.78')).toBe('123456789012345678');
  });

  it('strips leading zeros', () => {
    expect(rupeesToPaise('000980000')).toBe('98000000');
  });

  it('rejects what a person should be told about', () => {
    expect(() => rupeesToPaise('')).toThrow(/Enter an amount/);
    expect(() => rupeesToPaise('   ')).toThrow(/Enter an amount/);
    expect(() => rupeesToPaise('-500')).toThrow(/cannot be negative/);
    expect(() => rupeesToPaise('abc')).toThrow(/digits only/);
    expect(() => rupeesToPaise('12.3.4')).toThrow(/digits only/);
    expect(() => rupeesToPaise('100.123')).toThrow(/two decimal places/);
    expect(() => rupeesToPaise('0')).toThrow(/more than zero/);
    expect(() => rupeesToPaise('0.00')).toThrow(/more than zero/);
  });

  it('round-trips with formatMoney', () => {
    expect(formatMoney(rupeesToPaise('46,50,000'))).toBe('₹46,50,000');
    expect(formatMoney(rupeesToPaise('9800.50'))).toBe('₹9,800.50');
  });
});

describe('comparePaise', () => {
  it('sorts by value, not by string length', () => {
    const sorted = ['98000000', '465000000', '184000000'].sort(comparePaise);
    expect(sorted).toEqual(['98000000', '184000000', '465000000']);
  });

  it('treats equal values as equal', () => {
    expect(comparePaise('100', '100')).toBe(0);
  });
});
