/**
 * Money on screen.
 *
 * Two shapes: `Money` for a figure inside a row or a table, and `AmountBlock`
 * for the heart of a decision screen, laid out like a payments app with the
 * payee avatar, the masked account, the big figure and the amount in words.
 *
 * An amount we cannot parse renders as a dash, never as a guess and never as
 * zero. An approver must not be shown a number Pramaan made up.
 */

import type { ReactNode } from 'react';
import { amountInWords, formatMoney } from '../format/money';
import { formatIfsc, maskAccount } from '../format/account';
import { Avatar } from './Avatar';

export interface MoneyProps {
  /** An integer number of paise, as a string. */
  paise: string;
  className?: string;
}

export function Money({ paise, className }: MoneyProps): ReactNode {
  try {
    return <span className={`pm-money ${className ?? ''}`}>{formatMoney(paise)}</span>;
  } catch {
    return <span className={className}>&mdash;</span>;
  }
}

export interface AmountBlockProps {
  paise: string;
  payeeName: string;
  payeeAccountLast4?: string | null;
  payeeIfsc?: string | null;
  /** A line under the account: the invoice, or who raised it. */
  note?: ReactNode;
  /** Drop the avatar when the block sits inside a card that already has one. */
  withAvatar?: boolean;
  onBand?: boolean;
}

export function AmountBlock({
  paise,
  payeeName,
  payeeAccountLast4,
  payeeIfsc,
  note,
  withAvatar = true,
  onBand = false,
}: AmountBlockProps): ReactNode {
  let figure: string;
  let words: string | null = null;
  try {
    figure = formatMoney(paise);
    words = amountInWords(paise);
  } catch {
    figure = '—';
  }

  return (
    <div className="pm-amount">
      {withAvatar ? <Avatar name={payeeName} onBand={onBand} /> : null}
      <span className="pm-amount__to">Paying</span>
      <span className="pm-amount__payee">{payeeName}</span>
      {payeeAccountLast4 || payeeIfsc ? (
        <span className="pm-amount__acct">
          {payeeAccountLast4 ? `A/c ${maskAccount(payeeAccountLast4)}` : ''}
          {payeeAccountLast4 && payeeIfsc ? ' · ' : ''}
          {payeeIfsc ? formatIfsc(payeeIfsc) : ''}
        </span>
      ) : null}
      {note ? <span className="pm-amount__acct">{note}</span> : null}
      <span className="pm-amount__fig">{figure}</span>
      {words ? <span className="pm-amount__words">{words}</span> : null}
    </div>
  );
}
