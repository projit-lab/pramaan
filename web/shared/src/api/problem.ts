/**
 * Problem details, RFC 9457, as every Pramaan error arrives.
 *
 * Kept apart from client.ts so the public pages can read errors without pulling
 * in Firebase Auth. Nothing here imports anything.
 */

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  errors?: Array<{ field: string; detail: string }>;
}

/**
 * Turns whatever an error branch produced into a Problem a screen can show.
 *
 * Never invents a title: if the server did not send problem details, the message
 * says only that the request failed.
 */
export function toProblem(error: unknown, status?: number): Problem {
  if (error && typeof error === 'object') {
    const candidate = error as Partial<Problem>;
    if (typeof candidate.title === 'string' && typeof candidate.status === 'number') {
      return candidate as Problem;
    }
  }
  return {
    type: 'about:blank',
    title: 'The request failed',
    status: status ?? 0,
    detail:
      status === undefined
        ? 'Pramaan could not reach the API. Check that it is running and that VITE_API_BASE is correct.'
        : undefined,
  };
}

/** The one-line message a screen shows for a problem. */
export function problemMessage(problem: Problem): string {
  return problem.detail ? `${problem.title}. ${problem.detail}` : problem.title;
}

/** Field errors keyed by field name, so a form can show them inline. */
export function fieldErrors(problem: Problem): Record<string, string> {
  const result: Record<string, string> = {};
  for (const entry of problem.errors ?? []) {
    result[entry.field] = entry.detail;
  }
  return result;
}
