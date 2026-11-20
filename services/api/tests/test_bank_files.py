"""The file door.

Two rules carry the weight here, and each gets a test that would fail loudly if
someone optimised it away:

- a file is imported whole or not at all, so a bad line late in the file leaves
  nothing behind;
- a file is not finished while any of its lines is still waiting for a person.

The rest pin that a bank file is treated exactly like a payment somebody typed:
same policy, same tiers, same board.
"""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app.db.models import BankFile, BankFileLine, PaymentIntent
from app.services.bank_files import BankFileError, parse_bank_file

HEADER = "payee_name,account_last4,ifsc,amount_paise,purpose\n"

GOOD = HEADER + (
    "Sri Lakshmi Castings,7781,ABCD0123456,98000000,INV-2219\n"
    "Global Trade Solutions,9032,WXYZ0004411,465000000,INV-7741\n"
    "Kaveri Steel Traders,5540,EFGH0005540,184000000,KAVERI-4471\n"
)

CLERK = {"X-Dev-User": "clerk"}


def upload(client, body: str, name: str = "payments.csv", headers=CLERK):
    return client.post(
        "/v1/files/bank",
        files={"file": (name, io.BytesIO(body.encode("utf-8")), "text/csv")},
        headers=headers,
    )


# --------------------------------------------------------------------------
# Parsing, without touching the database
# --------------------------------------------------------------------------


def test_reads_every_line_of_a_good_file():
    lines = parse_bank_file(GOOD.encode())
    assert [line.line_no for line in lines] == [1, 2, 3]
    assert lines[0].payee_name == "Sri Lakshmi Castings"
    assert lines[2].amount_paise == "184000000"


def test_accepts_the_columns_in_any_order_and_ignores_a_trailing_blank_line():
    body = (
        "amount_paise,ifsc,payee_name,account_last4\n"
        "98000000,ABCD0123456,Sri Lakshmi Castings,7781\n"
        "\n"
    )
    lines = parse_bank_file(body.encode())
    assert len(lines) == 1
    assert lines[0].ifsc == "ABCD0123456"


def test_names_the_line_that_is_wrong_rather_than_saying_invalid_file():
    body = HEADER + (
        "Sri Lakshmi Castings,7781,ABCD0123456,98000000,INV-2219\n"
        "Bad Vendor,7781,NOTANIFSC,98000000,INV-1\n"
    )
    with pytest.raises(BankFileError) as caught:
        parse_bank_file(body.encode())
    assert caught.value.line_no == 2
    assert "ifsc" in caught.value.detail.lower()


@pytest.mark.parametrize(
    "row,fragment",
    [
        (",7781,ABCD0123456,98000000,x", "payee_name"),
        ("A Vendor,78,ABCD0123456,98000000,x", "account_last4"),
        ("A Vendor,7781,ABCD0123456,12.50,x", "amount_paise"),
        ("A Vendor,7781,ABCD0123456,0,x", "positive"),
        ("A Vendor,7781,ABCD0123456,-100,x", "positive"),
        ("A Vendor,7781,ABCD0123456,0098,x", "positive"),
    ],
)
def test_refuses_a_line_it_cannot_trust(row, fragment):
    with pytest.raises(BankFileError) as caught:
        parse_bank_file((HEADER + row + "\n").encode())
    assert fragment in caught.value.detail


def test_refuses_a_file_with_no_header():
    with pytest.raises(BankFileError) as caught:
        parse_bank_file(b"")
    assert "empty" in caught.value.detail.lower()


def test_refuses_a_header_that_is_missing_a_column():
    with pytest.raises(BankFileError) as caught:
        parse_bank_file(b"payee_name,amount_paise\nA,1\n")
    assert "account_last4" in caught.value.detail


def test_refuses_a_header_row_with_no_payments():
    with pytest.raises(BankFileError) as caught:
        parse_bank_file(HEADER.encode())
    assert "no payments" in caught.value.detail


def test_refuses_a_file_that_is_not_text():
    with pytest.raises(BankFileError) as caught:
        parse_bank_file(b"\xff\xfe\x00binary")
    assert "UTF-8" in caught.value.detail


# --------------------------------------------------------------------------
# Through the API, against a real migrated database
# --------------------------------------------------------------------------


def test_every_line_becomes_a_payment_that_came_through_the_file_door(env):
    client, rt, _clock = env
    res = upload(client, GOOD)
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["line_count"] == 3
    assert len(body["lines"]) == 3
    assert [line["line_no"] for line in body["lines"]] == [1, 2, 3]

    with rt.sessions() as s:
        routes = s.execute(
            select(PaymentIntent.entry_route)
            .join(BankFileLine, BankFileLine.intent_id == PaymentIntent.intent_id)
            .where(BankFileLine.file_id == body["file_id"])
        ).scalars().all()
    assert routes == ["bank_file", "bank_file", "bank_file"]


def test_a_bad_line_leaves_nothing_behind(env):
    """Whole or not at all. The bad line is last, so a naive implementation
    would already have created the two before it."""
    client, rt, _clock = env
    with rt.sessions() as s:
        before = len(s.execute(select(PaymentIntent.intent_id)).scalars().all())

    body = HEADER + (
        "Sri Lakshmi Castings,7781,ABCD0123456,98000000,INV-2219\n"
        "Global Trade Solutions,9032,WXYZ0004411,465000000,INV-7741\n"
        "Broken Vendor,9999,ABCD0123456,not-a-number,INV-3\n"
    )
    res = upload(client, body)
    assert res.status_code == 422

    with rt.sessions() as s:
        after = len(s.execute(select(PaymentIntent.intent_id)).scalars().all())
        files = s.execute(select(BankFile.file_id)).scalars().all()
    assert after == before, "a rejected file must not create any payment"
    assert files == [], "a rejected file must not be recorded"


def test_the_file_is_not_finished_while_a_line_is_still_waiting(env):
    client, rt, _clock = env
    res = upload(client, GOOD)
    body = res.json()

    assert body["waiting_on_approval"] >= 1
    assert body["complete"] is False

    read_back = client.get(f"/v1/files/bank/{body['file_id']}", headers=CLERK).json()
    assert read_back["complete"] is False
    assert read_back["waiting_on_approval"] == body["waiting_on_approval"]
    assert read_back["settled"] + read_back["waiting_on_approval"] == 3


def test_the_file_is_finished_once_every_line_is_decided(env):
    client, rt, _clock = env
    body = upload(client, GOOD).json()

    # Stand in for the approvers: settle every line the file produced.
    with rt.sessions() as s:
        ids = s.execute(
            select(BankFileLine.intent_id).where(BankFileLine.file_id == body["file_id"])
        ).scalars().all()
        for intent_id in ids:
            s.get(PaymentIntent, intent_id).status = "released"
        s.commit()

    read_back = client.get(f"/v1/files/bank/{body['file_id']}", headers=CLERK).json()
    assert read_back["waiting_on_approval"] == 0
    assert read_back["settled"] == 3
    assert read_back["complete"] is True


def test_records_the_hash_of_what_was_uploaded(env):
    import hashlib

    client, _rt, _clock = env
    body = upload(client, GOOD).json()
    assert body["sha256"] == hashlib.sha256(GOOD.encode()).hexdigest()


def test_a_file_keeps_its_filename_for_the_clerk(env):
    client, _rt, _clock = env
    body = upload(client, GOOD, name="november-run.csv").json()
    assert body["filename"] == "november-run.csv"


def test_an_unknown_file_is_a_404_not_an_empty_file(env):
    client, _rt, _clock = env
    res = client.get("/v1/files/bank/bf_01JD2XNOTHING0001", headers=CLERK)
    assert res.status_code == 404


def test_signing_in_is_required_to_upload(env):
    client, _rt, _clock = env
    res = client.post(
        "/v1/files/bank",
        files={"file": ("payments.csv", io.BytesIO(GOOD.encode()), "text/csv")},
    )
    assert res.status_code in (401, 403)
