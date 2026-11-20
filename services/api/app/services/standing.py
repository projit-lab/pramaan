"""M2+ standing mandates: finding a valid one for a payment, and the monthly
usage counters (Danish). Prajit owns the signed standing-mandate format and the
gate's check that every released payment fits it; this module decides the
auto-release lane and keeps the counters honest.

The counter changes in one conditional UPDATE ("add this payment only if the new
total and count still fit"), so two payments racing for the last of the cap can
never both get it. That holds on PostgreSQL (AlloyDB) and on SQLite alike.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import StandingMandate, StandingMandateUsage, VendorBankAccount
from app.domain.lanes import IST


def account_hash(account_number: str) -> str:
    return hashlib.sha256(account_number.encode()).hexdigest()


def month_key(now: datetime) -> str:
    return now.astimezone(IST).strftime("%Y-%m")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def usage(s: Session, sm: StandingMandate, now: datetime) -> tuple[int, int]:
    row = s.get(StandingMandateUsage, (sm.standing_mandate_id, month_key(now)))
    return (row.total_paise, row.used_count) if row else (0, 0)


def find_valid(
    s: Session, vendor_id: str, account: VendorBankAccount, amount_paise: int, now: datetime
) -> StandingMandate | None:
    """A standing mandate this payment fits right now, or None. Any change to the
    vendor's bank details after the mandate was signed voids it."""
    candidates = s.scalars(
        select(StandingMandate).where(
            StandingMandate.vendor_id == vendor_id,
            StandingMandate.revoked.is_(False),
        )
    )
    for sm in candidates:
        if _aware(sm.expires_at) <= now:
            continue
        if sm.payee_account_sha256 != account_hash(account.account_number):
            continue
        if sm.payee_ifsc != account.ifsc:
            continue
        if _aware(account.valid_from) > _aware(sm.created_at):
            continue  # bank details changed after signing: void
        if amount_paise > sm.cap_per_payment_paise:
            continue
        total, count = usage(s, sm, now)
        if total + amount_paise > sm.cap_per_month_paise or count >= sm.max_count:
            continue
        return sm
    return None


def reserve(s: Session, sm: StandingMandate, amount_paise: int, now: datetime) -> bool:
    """Count this payment against the mandate's month. False when it no longer
    fits (someone else used the room first)."""
    key = (sm.standing_mandate_id, month_key(now))
    if s.get(StandingMandateUsage, key) is None:
        try:
            with s.begin_nested():
                s.add(
                    StandingMandateUsage(
                        standing_mandate_id=key[0], month=key[1], total_paise=0, used_count=0
                    )
                )
        except IntegrityError:
            pass  # another payment created the row first
    result = s.execute(
        update(StandingMandateUsage)
        .where(
            StandingMandateUsage.standing_mandate_id == key[0],
            StandingMandateUsage.month == key[1],
            StandingMandateUsage.total_paise + amount_paise <= sm.cap_per_month_paise,
            StandingMandateUsage.used_count < sm.max_count,
        )
        .values(
            total_paise=StandingMandateUsage.total_paise + amount_paise,
            used_count=StandingMandateUsage.used_count + 1,
        )
        .execution_options(synchronize_session=False)
    )
    s.expire_all()
    return result.rowcount == 1
