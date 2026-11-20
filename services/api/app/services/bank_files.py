"""The file door: a bank payment file in, one payment intent per line.

Finance uploads the same kind of CSV they would hand to their bank. Every line
becomes an ordinary payment intent with `entry_route='bank_file'` and meets
exactly the same policy, the same approvers and the same gate as a payment
somebody typed. That identity of treatment is the argument: the demo fires four
doors at once and they all arrive on one board.

Two rules this module exists to enforce:

1. **A file is imported whole or not at all.** If any line is malformed, nothing
   is created. A half-imported payment file is worse than a rejected one,
   because nobody can tell by looking which half went in.

2. **A file is not finished while any line is still waiting.** The clerk is told
   how many lines are held and by whom, rather than being shown a tick the
   moment the upload succeeds.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import BankFile, BankFileLine, PaymentIntent
from app.domain.ids import new_id
from app.domain.money import parse_paise
from app.errors import ProblemException
from app.runtime import Runtime, utc_now
from app.services.intents import create_intent

#: The columns a bank file must carry, in any order.
REQUIRED_COLUMNS = ("payee_name", "account_last4", "ifsc", "amount_paise")
OPTIONAL_COLUMNS = ("purpose", "vendor_id")

IFSC_LENGTH = 11
MAX_LINES = 500


class BankFileError(ProblemException):
    """A file that cannot be read. Carries the line number, because "row 14 has
    no IFSC" is actionable and "invalid file" is not."""

    def __init__(self, detail: str, line_no: int | None = None) -> None:
        where = f" (line {line_no})" if line_no is not None else ""
        super().__init__(422, "Bank file could not be read", f"{detail}{where}")
        self.line_no = line_no


@dataclass(frozen=True)
class ParsedLine:
    line_no: int
    payee_name: str
    account_last4: str
    ifsc: str
    amount_paise: str
    purpose: str | None
    vendor_id: str | None


def parse_bank_file(content: bytes) -> list[ParsedLine]:
    """Reads the whole file before anything is created, so a bad line later in
    the file cannot leave earlier lines already imported."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise BankFileError("The file is not UTF-8 text.") from e

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise BankFileError("The file is empty.")

    headers = {(h or "").strip().lower() for h in reader.fieldnames}
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise BankFileError(
            "The header row must name " + ", ".join(REQUIRED_COLUMNS) + "; missing "
            + ", ".join(missing) + "."
        )

    lines: list[ParsedLine] = []
    for index, row in enumerate(reader, start=1):
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}

        if not any(clean.get(c) for c in REQUIRED_COLUMNS):
            continue  # a blank line at the end of a file is not an error

        if len(lines) >= MAX_LINES:
            raise BankFileError(f"A file may carry at most {MAX_LINES} payments.", index)

        name = clean.get("payee_name", "")
        if not name:
            raise BankFileError("payee_name is empty.", index)

        account = clean.get("account_last4", "")
        if not (account.isdigit() and len(account) == 4):
            raise BankFileError(
                "account_last4 must be the last four digits of the account.", index
            )

        ifsc = clean.get("ifsc", "").upper()
        if len(ifsc) != IFSC_LENGTH or not ifsc.isalnum() or ifsc[4] != "0":
            raise BankFileError("ifsc is not an IFSC code.", index)

        # parse_paise is the single authority on what an amount may look like:
        # a positive whole number of paise, no decimals, signs or leading zeros,
        # so one amount can never be written two ways. Zero is refused there.
        amount = clean.get("amount_paise", "")
        try:
            parse_paise(amount)
        except Exception as e:  # noqa: BLE001 - parse_paise raises ValueError
            raise BankFileError(
                "amount_paise must be a positive whole number of paise.", index
            ) from e

        lines.append(
            ParsedLine(
                line_no=index,
                payee_name=name,
                account_last4=account,
                ifsc=ifsc,
                amount_paise=amount,
                purpose=clean.get("purpose") or None,
                vendor_id=clean.get("vendor_id") or None,
            )
        )

    if not lines:
        raise BankFileError("The file has a header row but no payments.")
    return lines


class _LineIntent:
    """The shape create_intent expects, built from one line of the file.

    A small stand-in rather than the pydantic IntentCreate: the file has already
    been validated line by line, and reaching back into the router's request
    model from a service would point the dependency the wrong way.
    """

    def __init__(self, line: ParsedLine, uploader: str, department_id: str | None) -> None:
        self.payee_vendor_id = line.vendor_id
        self.payee = None if line.vendor_id else _Payee(line)
        self.amount_paise = line.amount_paise
        self.currency = "INR"
        self.purpose = line.purpose
        self.invoice_sha256 = None
        self.instruction_channel = "portal"
        self.instruction_note = None
        self.initiator = _Initiator(uploader)
        self.department_id = department_id
        self.entry_route = "bank_file"

    @property
    def route(self) -> str:
        return "bank_file"

    @property
    def amount(self) -> int:
        return parse_paise(self.amount_paise)


class _Payee:
    def __init__(self, line: ParsedLine) -> None:
        self.name_at_bank = line.payee_name
        self.account_last4 = line.account_last4
        self.ifsc = line.ifsc
        self.vendor_id = None


class _Initiator:
    def __init__(self, uploader: str) -> None:
        self.type = "human"
        self.id = uploader


def upload_bank_file(
    rt: Runtime,
    *,
    filename: str,
    content: bytes,
    uploaded_by: str,
    department_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Parse the whole file, then create one intent per line."""
    lines = parse_bank_file(content)
    moment = (now or utc_now(rt)).astimezone(timezone.utc)
    digest = hashlib.sha256(content).hexdigest()
    file_id = new_id("bf")

    results: list[dict[str, Any]] = []
    for line in lines:
        created = create_intent(rt, _LineIntent(line, uploaded_by, department_id), now=moment)
        results.append({"line_no": line.line_no, **created})

    with unit_of_work(rt.sessions) as s:
        s.add(
            BankFile(
                file_id=file_id,
                company_id=rt.settings.COMPANY_ID,
                filename=filename[:260],
                sha256=digest,
                uploaded_by=uploaded_by,
                line_count=len(lines),
                created_at=moment,
            )
        )
        for line, created in zip(lines, results, strict=True):
            s.add(
                BankFileLine(
                    file_id=file_id,
                    line_no=line.line_no,
                    intent_id=created["intent_id"],
                )
            )

    return {
        "file_id": file_id,
        "filename": filename,
        "sha256": digest,
        "line_count": len(lines),
        "lines": results,
        **_settlement(rt, file_id),
    }


#: Intent statuses that mean nobody has to do anything more about this line.
_SETTLED = frozenset({"released", "blocked", "declined", "expired"})


def _settlement(rt: Runtime, file_id: str) -> dict[str, Any]:
    """How much of the file is finished. Derived from the intents every time,
    never cached: a cached count is a count that can be wrong."""
    with unit_of_work(rt.sessions) as s:
        rows = s.execute(
            select(PaymentIntent.status)
            .join(BankFileLine, BankFileLine.intent_id == PaymentIntent.intent_id)
            .where(BankFileLine.file_id == file_id)
        ).scalars().all()

    waiting = [r for r in rows if r not in _SETTLED]
    return {
        "waiting_on_approval": len(waiting),
        "settled": len(rows) - len(waiting),
        # The honest headline: the file is not done while anything is waiting.
        "complete": len(waiting) == 0 and len(rows) > 0,
    }


def bank_file_view(rt: Runtime, file_id: str) -> dict[str, Any]:
    with unit_of_work(rt.sessions) as s:
        record = s.get(BankFile, file_id)
        if record is None or record.company_id != rt.settings.COMPANY_ID:
            raise ProblemException(404, "Not found", "No such bank file.")
        lines = s.execute(
            select(BankFileLine.line_no, PaymentIntent.intent_id, PaymentIntent.status)
            .join(PaymentIntent, BankFileLine.intent_id == PaymentIntent.intent_id)
            .where(BankFileLine.file_id == file_id)
            .order_by(BankFileLine.line_no)
        ).all()
        payload = {
            "file_id": record.file_id,
            "filename": record.filename,
            "sha256": record.sha256,
            "uploaded_by": record.uploaded_by,
            "line_count": record.line_count,
            "created_at": record.created_at,
            "lines": [
                {"line_no": n, "intent_id": i, "status": st} for n, i, st in lines
            ],
        }
    return {**payload, **_settlement(rt, file_id)}
