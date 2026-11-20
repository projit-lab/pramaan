import { describe, expect, it } from 'vitest';
import {
  formatIst,
  formatIstDate,
  formatIstWithRelative,
  hasExpired,
  isOutsideWorkingHoursIst,
  relativeTime,
  toDate,
} from './time';

const BOSS_SCAM_CREATED = '2026-11-20T11:14:07+05:30';

describe('toDate', () => {
  it('parses an API timestamp with the +05:30 offset', () => {
    const date = toDate(BOSS_SCAM_CREATED);
    expect(date?.toISOString()).toBe('2026-11-20T05:44:07.000Z');
  });

  it('converts a Firestore Timestamp through toDate', () => {
    const stub = { toDate: () => new Date('2026-11-20T05:44:07.000Z') };
    expect(toDate(stub)?.toISOString()).toBe('2026-11-20T05:44:07.000Z');
  });

  it('converts a plain seconds and nanoseconds shape', () => {
    expect(toDate({ seconds: 1795153447, nanoseconds: 0 })?.toISOString()).toBe(
      '2026-11-20T05:44:07.000Z',
    );
  });

  it('returns null rather than an Invalid Date', () => {
    expect(toDate(null)).toBeNull();
    expect(toDate(undefined)).toBeNull();
    expect(toDate('not a time')).toBeNull();
    expect(toDate(new Date('nonsense'))).toBeNull();
    expect(toDate({ toDate: () => { throw new Error('boom'); } })).toBeNull();
  });
});

describe('formatIst', () => {
  it('shows the time in IST regardless of the offset it arrived in', () => {
    // The same instant, written three ways.
    const fromIst = formatIst('2026-11-20T11:14:07+05:30');
    const fromUtc = formatIst('2026-11-20T05:44:07Z');
    expect(fromIst).toBe(fromUtc);
    expect(fromIst).toContain('20 Nov 2026');
    expect(fromIst).toContain('IST');
    expect(fromIst).toMatch(/11:14/);
  });

  it('returns null for a missing time', () => {
    expect(formatIst(null)).toBeNull();
  });
});

describe('formatIstDate', () => {
  it('formats the date alone', () => {
    expect(formatIstDate(BOSS_SCAM_CREATED)).toBe('20 Nov 2026');
  });
});

describe('relativeTime', () => {
  const now = '2026-11-20T12:00:00+05:30';

  it('says just now inside half a minute', () => {
    expect(relativeTime('2026-11-20T11:59:45+05:30', now)).toBe('just now');
  });

  it('counts minutes and hours in the past', () => {
    expect(relativeTime('2026-11-20T11:58:00+05:30', now)).toBe('2 min ago');
    expect(relativeTime('2026-11-20T11:00:00+05:30', now)).toBe('1 hr ago');
    expect(relativeTime('2026-11-20T09:00:00+05:30', now)).toBe('3 hr ago');
  });

  it('counts days in the past', () => {
    expect(relativeTime('2026-11-18T12:00:00+05:30', now)).toBe('2 days ago');
    expect(relativeTime('2026-11-19T12:00:00+05:30', now)).toBe('1 day ago');
  });

  it('counts forward for an expiry still to come', () => {
    expect(relativeTime('2026-11-20T12:05:00+05:30', now)).toBe('in 5 min');
    expect(relativeTime('2026-11-21T12:00:00+05:30', now)).toBe('in 1 day');
  });

  it('returns null for a missing time', () => {
    expect(relativeTime(undefined, now)).toBeNull();
  });
});

describe('formatIstWithRelative', () => {
  it('returns both halves of what a screen shows', () => {
    const pair = formatIstWithRelative(BOSS_SCAM_CREATED, '2026-11-20T11:16:07+05:30');
    expect(pair?.relative).toBe('2 min ago');
    expect(pair?.absolute).toContain('20 Nov 2026');
  });

  it('returns null when there is nothing to show', () => {
    expect(formatIstWithRelative(null)).toBeNull();
  });
});

describe('hasExpired', () => {
  const now = '2026-11-20T12:00:00+05:30';

  it('is true once the expiry has passed', () => {
    expect(hasExpired('2026-11-20T11:59:59+05:30', now)).toBe(true);
    expect(hasExpired('2026-11-20T12:00:00+05:30', now)).toBe(true);
  });

  it('is false while the approval is still live', () => {
    expect(hasExpired('2026-11-20T12:00:01+05:30', now)).toBe(false);
  });

  it('is false when there is no expiry, so nothing is wrongly disabled', () => {
    expect(hasExpired(null, now)).toBe(false);
  });
});

describe('isOutsideWorkingHoursIst', () => {
  it('is false inside 9 am to 7 pm IST', () => {
    expect(isOutsideWorkingHoursIst('2026-11-20T09:00:00+05:30')).toBe(false);
    expect(isOutsideWorkingHoursIst('2026-11-20T18:59:00+05:30')).toBe(false);
  });

  it('is true outside them', () => {
    expect(isOutsideWorkingHoursIst('2026-11-20T08:59:00+05:30')).toBe(true);
    expect(isOutsideWorkingHoursIst('2026-11-20T19:00:00+05:30')).toBe(true);
    expect(isOutsideWorkingHoursIst('2026-11-20T02:30:00+05:30')).toBe(true);
  });

  it('judges by IST, not by the offset the time arrived in', () => {
    // 22:00 UTC is 03:30 IST the next day, which is outside working hours.
    expect(isOutsideWorkingHoursIst('2026-11-20T22:00:00Z')).toBe(true);
  });

  it('returns null when there is no time to judge', () => {
    expect(isOutsideWorkingHoursIst(null)).toBeNull();
  });
});
