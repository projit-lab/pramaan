/**
 * Times in Pramaan are ISO 8601 with the +05:30 offset in the API, and Firestore
 * Timestamps in the live read model. Screens show IST with a relative time beside
 * it, because an approver reading "2 min ago" acts faster than one doing offset
 * arithmetic.
 */

const IST_TIME_ZONE = 'Asia/Kolkata';

/** Anything a Pramaan payload might hand us for a point in time. */
export type TimeLike =
  | string
  | number
  | Date
  | { toDate: () => Date }
  | { seconds: number; nanoseconds?: number }
  | null
  | undefined;

/**
 * Coerces an API string, a Firestore Timestamp or a Date into a Date.
 * Returns null for anything missing or unparseable, so a screen can say
 * "couldn't verify" rather than render "Invalid Date".
 */
export function toDate(value: TimeLike): Date | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === 'number') {
    const fromNumber = new Date(value);
    return Number.isNaN(fromNumber.getTime()) ? null : fromNumber;
  }
  if (typeof value === 'string') {
    const fromString = new Date(value);
    return Number.isNaN(fromString.getTime()) ? null : fromString;
  }
  if (typeof value === 'object') {
    if ('toDate' in value && typeof value.toDate === 'function') {
      try {
        const converted = value.toDate();
        return converted instanceof Date && !Number.isNaN(converted.getTime()) ? converted : null;
      } catch {
        return null;
      }
    }
    if ('seconds' in value && typeof value.seconds === 'number') {
      const millis = value.seconds * 1000 + Math.floor((value.nanoseconds ?? 0) / 1e6);
      const fromTimestamp = new Date(millis);
      return Number.isNaN(fromTimestamp.getTime()) ? null : fromTimestamp;
    }
  }
  return null;
}

const DATE_TIME_IST = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST_TIME_ZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
});

const TIME_IST = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
});

const DATE_IST = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST_TIME_ZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});

/** "20 Nov 2026, 11:14 am IST", or null when there is no usable time. */
export function formatIst(value: TimeLike): string | null {
  const date = toDate(value);
  if (!date) return null;
  return `${DATE_TIME_IST.format(date)} IST`;
}

/** "11:14 am IST" */
export function formatIstTime(value: TimeLike): string | null {
  const date = toDate(value);
  if (!date) return null;
  return `${TIME_IST.format(date)} IST`;
}

/** "20 Nov 2026" */
export function formatIstDate(value: TimeLike): string | null {
  const date = toDate(value);
  if (!date) return null;
  return DATE_IST.format(date);
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/**
 * "just now", "2 min ago", "3 hr ago", "in 5 min", "in 2 days".
 *
 * `now` is a parameter so tests do not depend on the clock.
 */
export function relativeTime(value: TimeLike, now: TimeLike = new Date()): string | null {
  const date = toDate(value);
  const reference = toDate(now);
  if (!date || !reference) return null;

  const deltaMillis = date.getTime() - reference.getTime();
  const future = deltaMillis > 0;
  const magnitude = Math.abs(deltaMillis);

  if (magnitude < 30_000) return 'just now';

  const say = (amount: number, unit: string): string => {
    const plural = amount === 1 ? unit : `${unit}s`;
    const label = unit === 'min' || unit === 'hr' ? unit : plural;
    return future ? `in ${amount} ${label}` : `${amount} ${label} ago`;
  };

  if (magnitude < HOUR) return say(Math.round(magnitude / MINUTE), 'min');
  if (magnitude < DAY) return say(Math.round(magnitude / HOUR), 'hr');
  return say(Math.round(magnitude / DAY), 'day');
}

/**
 * The pair a Pramaan screen shows: the IST time, and the relative time beside it.
 * Returns null when there is no usable time, so the caller renders
 * "couldn't verify" instead of inventing one.
 */
export function formatIstWithRelative(
  value: TimeLike,
  now: TimeLike = new Date(),
): { absolute: string; relative: string } | null {
  const absolute = formatIst(value);
  const relative = relativeTime(value, now);
  if (!absolute || !relative) return null;
  return { absolute, relative };
}

/** True when `expiresAt` is in the past. An expired approval cannot be approved. */
export function hasExpired(expiresAt: TimeLike, now: TimeLike = new Date()): boolean {
  const expiry = toDate(expiresAt);
  const reference = toDate(now);
  if (!expiry || !reference) return false;
  return expiry.getTime() <= reference.getTime();
}

/**
 * True when the time falls outside 9 am to 7 pm IST, which is one of the policy
 * engine's rules. The web lane only ever displays this; the server decides.
 */
export function isOutsideWorkingHoursIst(
  value: TimeLike,
  startHour = 9,
  endHour = 19,
): boolean | null {
  const date = toDate(value);
  if (!date) return null;
  const hourText = new Intl.DateTimeFormat('en-GB', {
    timeZone: IST_TIME_ZONE,
    hour: '2-digit',
    hour12: false,
  }).format(date);
  const hour = Number.parseInt(hourText, 10);
  if (Number.isNaN(hour)) return null;
  return hour < startHour || hour >= endHour;
}
