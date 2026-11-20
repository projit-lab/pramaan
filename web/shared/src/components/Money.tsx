/**
 * Money on screen: rupees with Indian grouping, and the amount in words where a
 * person decides on it.
 */

import type { ReactNode } from 'react';
import { amountInWords, formatMoney } from '../format/money';

export interface MoneyProps {
  /** An integer number of paise, as a string. */
  paise: string;
  /** Also show the amount in Indian words underneath. */
  withWords?: boolean;
  className?: string;
}

export function Money({ paise, withWords = false, className }: MoneyProps): ReactNode {
  let formatted: string;
  let words: string | null = null;

  try {
    formatted = formatMoney(paise);
    if (withWords) words = amountInWords(paise);
  } catch {
    // An amount we cannot parse is shown as a dash, never as a guess and never
    // as zero: an approver must not see a number Pramaan made up.
    return <span className={className}>&mdash;</span>;
  }

  return (
    <span className={className}>
      <span className="pr-money">{formatted}</span>
      {words ? <span className="pr-money__words">{words}</span> : null}
    </span>
  );
}
