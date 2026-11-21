"""The AI payables agent: an invoice PDF in, a held payment out.

1. Read: Gemini (or the offline stub) reads the invoice's fields.
2. Screen: Model Armor (or the offline regex screen) checks the document's full
   text, hidden text included, for instructions aimed at an AI.
3. Compare: a rule, not the model, compares what was read with the vendor master.
4. Submit: the agent asks to pay what it read, through the same create_intent
   every other route uses. Findings can only make the payment stricter.

The agent never approves anything. A person's signed mandate is still the only
thing that releases money.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.adapters.gemini import InvoiceReading, explain_hold, get_invoice_reader
from app.adapters.model_armor import Finding, get_screen, pressure_language
from app.db.engine import unit_of_work
from app.db.models import Vendor
from app.domain.ids import new_id
from app.errors import ProblemException
from app.runtime import Runtime
from app.services.intents import create_intent
from app.services.views import current_account

logger = logging.getLogger("pramaan")

AGENT_ID = "payables-agent-01"
MAX_PDF_BYTES = 5 * 1024 * 1024

# Built per process; tests replace these to run without Vertex AI.
_reader = None
_screen = None


def reader(rt: Runtime):
    global _reader
    if _reader is None:
        _reader = get_invoice_reader(rt.settings)
    return _reader


def screen(rt: Runtime):
    global _screen
    if _screen is None:
        _screen = get_screen(rt.settings)
    return _screen


def _norm(v: str | None) -> str:
    return " ".join((v or "").upper().split())


def _on_record(rt: Runtime, fields: dict[str, str | None]) -> dict[str, Any] | None:
    company_id = rt.settings.COMPANY_ID
    with unit_of_work(rt.sessions) as s:
        vendor = None
        if fields.get("gstin"):
            vendor = s.scalar(
                select(Vendor).where(
                    Vendor.company_id == company_id, Vendor.gstin == fields["gstin"]
                )
            )
        if vendor is None and fields.get("vendor_name"):
            vendor = s.scalar(
                select(Vendor).where(
                    Vendor.company_id == company_id,
                    func.upper(Vendor.legal_name) == _norm(fields["vendor_name"]),
                )
            )
        if vendor is None:
            return None
        acct = current_account(s, vendor.vendor_id)
        return {
            "vendor_id": vendor.vendor_id,
            "vendor_name": vendor.legal_name,
            "gstin": vendor.gstin,
            "account": acct.account_number if acct else None,
            "ifsc": acct.ifsc if acct else None,
        }


def compare(fields: dict[str, str | None], record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The rule. A field the model could not find is not a mismatch: absence is not disagreement."""
    out: dict[str, dict[str, Any]] = {}
    for name in (
        "vendor_name",
        "account",
        "ifsc",
        "gstin",
        "amount_paise",
        "invoice_number",
        "invoice_date",
    ):
        got = fields.get(name)
        expected = record.get(name)
        mismatch = bool(got and expected and _norm(got) != _norm(expected))
        out[name] = {"extracted": got, "onRecord": expected, "mismatch": mismatch}
    return out


def finding_doc(f: Finding, now: datetime) -> dict[str, Any]:
    return {
        "category": f.category,
        "detail": f"{f.detail} Screened by {f.screened_by}.",
        "excerpt": f.excerpt,
        "foundAt": now,
        "screenedBy": f.screened_by,
    }


def agent_log(
    reading: InvoiceReading,
    finding: Finding | None,
    compared: dict[str, dict[str, Any]],
    mismatches: list[str],
    result: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    ai = "gemini" if reading.source == "gemini" else "rule"
    who = (
        f"Gemini ({reading.model_version})"
        if reading.source == "gemini"
        else "the offline stub reader (regex, not Gemini)"
    )
    log = [
        {
            "at": now,
            "source": ai,
            "text": f"Read invoice {compared['invoice_number']['extracted'] or ''} with {who}.",
        },
    ]
    for note in reading.notes:
        log.append({"at": now, "source": ai, "text": f"The reader {note}."})
    if finding:
        src = "model_armor" if finding.screened_by.startswith("Google") else "rule"
        log.append({"at": now, "source": src, "text": f"{finding.screened_by}: {finding.detail}"})
    else:
        log.append(
            {
                "at": now,
                "source": "rule",
                "text": "Screened the document text: nothing aimed at an AI.",
            }
        )
    if mismatches:
        parts = []
        for k in mismatches:
            got, rec = compared[k]["extracted"] or "", compared[k]["onRecord"] or ""
            parts.append(f"{k} {got} on the invoice, {rec} on record")
        log.append(
            {
                "at": now,
                "source": "rule",
                "text": "Rule check against the vendor master: " + "; ".join(parts) + ".",
            }
        )
    else:
        log.append(
            {
                "at": now,
                "source": "rule",
                "text": "Rule check against the vendor master: bank details match.",
            }
        )
    log.append(
        {
            "at": now,
            "source": "rule",
            "text": f"Asked Pramaan for a mandate: payment {result['intent_id']}, "
            f"Tier {result['tier']}, {result['status']}. "
            "The agent cannot release money; an approver's phone has to sign.",
        }
    )
    return log


def process_invoice(rt: Runtime, pdf: bytes, filename: str | None = None) -> dict[str, Any]:
    if len(pdf) > MAX_PDF_BYTES:
        raise ProblemException(413, "Invoice too large", "Invoices up to 5 MB.")
    if not pdf.startswith(b"%PDF"):
        raise ProblemException(422, "Not a PDF", "Upload the invoice as a PDF.")
    now = datetime.now(timezone.utc)

    try:
        reading: InvoiceReading = reader(rt).read(pdf)
    except Exception as e:
        logger.warning(f"Invoice reader failed: {type(e).__name__}: {e}")
        raise ProblemException(
            503, "Could not read the invoice", "The invoice reader failed; nothing was paid."
        ) from e
    fields = reading.fields
    finding = screen(rt).screen(reading.text)
    pressure = pressure_language(reading.text)

    record = _on_record(rt, fields)
    if record is None:
        raise ProblemException(
            422, "Unknown vendor", "No vendor on record matches this invoice's GSTIN or name."
        )
    if not fields.get("amount_paise"):
        raise ProblemException(422, "No amount", "The reader found no total on this invoice.")
    compared = compare(fields, record)
    mismatches = [k for k in ("account", "ifsc", "gstin") if compared[k]["mismatch"]]

    from app.routers.intents import IntentCreate  # local: routers import services

    pays_record = not compared["account"]["mismatch"] and not compared["ifsc"]["mismatch"]
    common = {
        "amount_paise": fields["amount_paise"],
        "purpose": fields.get("invoice_number") or filename,
        "invoice_sha256": hashlib.sha256(pdf).hexdigest(),
        "instruction_channel": "agent",
        "instruction_note": f"Raised by {AGENT_ID} from {filename or 'an uploaded invoice'}.",
        "initiator": {"type": "agent", "id": AGENT_ID},
        "entry_route": "agent",
    }
    if pays_record:
        body = IntentCreate(payee_vendor_id=record["vendor_id"], **common)
    else:
        # The agent asks to pay what it read. Pramaan holds it, it never silently fixes it.
        body = IntentCreate(
            payee={
                "name_at_bank": record["vendor_name"],
                "account_last4": (fields.get("account") or "0000")[-4:],
                "ifsc": fields.get("ifsc") or record["ifsc"],
            },
            **common,
        )

    ai = {
        "invoice_mismatches": mismatches,
        "model_armor_finding": finding is not None,
        "pressure_language": pressure,
        "finding_source": "model_armor"
        if finding and finding.screened_by.startswith("Google")
        else "rule",
    }
    result = create_intent(rt, body, ai=ai)

    request_id = new_id("ag")
    invoice_doc = {
        "source": reading.source,
        "modelVersion": reading.model_version,
        "fileUrl": None,
        "ref": fields.get("invoice_number"),
        "fields": compared,
        "notes": reading.notes,
    }
    extra: dict[str, Any] = {
        "invoice": invoice_doc,
        "modelArmorFinding": finding_doc(finding, now) if finding else None,
        "agentRequestId": request_id,
    }
    explanation = explain_hold(
        rt.settings,
        {
            "tier": result["tier"],
            "status": result["status"],
            "reasons": [r["text"] for r in result["reasons"]],
            "account_on_invoice_ends": (fields.get("account") or "")[-4:],
            "account_on_record_ends": (record.get("account") or "")[-4:],
        },
    )
    if explanation:
        extra["explanation"] = explanation
    run_doc = {
        "agentRequestId": request_id,
        "agentId": AGENT_ID,
        "invoiceRef": fields.get("invoice_number"),
        "intentId": result["intent_id"],
        "status": "flagged"
        if (finding or mismatches)
        else "held"
        if result["status"] == "held"
        else "mandate_requested",
        "modelArmorFinding": extra["modelArmorFinding"],
        "log": agent_log(reading, finding, compared, mismatches, result, now),
        "createdAt": now,
    }
    try:
        rt.read_model.set_document("agentRequests", request_id, run_doc)
        rt.read_model.update_document("holds", result["intent_id"], extra)
    except Exception as e:  # the console is a view; the hold itself is already stored
        logger.warning(f"Could not add the invoice to hold {result['intent_id']}: {e}")

    return {
        **result,
        "agent_request_id": request_id,
        "invoice": invoice_doc,
        "model_armor_finding": extra["modelArmorFinding"],
        "explanation": extra.get("explanation"),
        "pays_vendor_master_account": pays_record,
    }
