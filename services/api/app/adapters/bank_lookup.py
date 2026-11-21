"""Account name look-up for the automatic payee checks (M2+).

The plan uses a mock bank for the buildathon: the name the bank holds for an
account is the name recorded against it in the vendor master's account history.
A real deployment swaps in a bank's name-enquiry ("penny drop") API behind the
same method. An account the bank does not know returns None, which the checks
report as not_found.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import VendorBankAccount


class BankLookup(Protocol):
    def name_for(self, s: Session, account_number: str | None, ifsc: str) -> str | None: ...


class MockBankLookup:
    def name_for(self, s: Session, account_number: str | None, ifsc: str) -> str | None:
        if not account_number:
            return None  # a one-off payee arrives with the last four digits only
        return s.scalar(
            select(VendorBankAccount.name_at_bank).where(
                VendorBankAccount.account_number == account_number,
                VendorBankAccount.ifsc == ifsc,
            )
        )
