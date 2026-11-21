"""Reading an invoice: Gemini on Vertex AI, or an offline stand-in.

The reader only *reads*. It returns the fields printed on the invoice; it never
decides anything. A rule compares those fields with the vendor master
(app/services/agent.py), and only a person's signed mandate can release money.

`GeminiInvoiceReader` sends the PDF bytes to Gemini on Vertex AI (Application
Default Credentials, no key files) and asks for structured JSON.

`StubInvoiceReader` is for tests and for runs without Vertex AI. It is not
Gemini and never claims to be: it pulls the fields out of the PDF's text layer
with regular expressions, and it deliberately behaves like a naive payables
agent that obeys a hidden "pay account ..." line, so the demo can show what
Pramaan does when the agent upstream has been fooled.
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger("pramaan")

FIELDS = (
    "vendor_name",
    "gstin",
    "account",
    "ifsc",
    "amount_paise",
    "invoice_number",
    "invoice_date",
)


@dataclass
class InvoiceReading:
    fields: dict[str, str | None]
    text: str  # the PDF's full text layer, hidden text included; screened separately
    source: str  # "gemini" or "stub"
    model_version: str
    notes: list[str] = field(default_factory=list)


class InvoiceReader(Protocol):
    def read(self, pdf: bytes) -> InvoiceReading: ...


def pdf_text(pdf: bytes) -> str:
    """Every character in the text layer, including white-on-white or 1pt text."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _rupees_to_paise(raw: str) -> str | None:
    digits = raw.replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "").strip()
    m = re.match(r"^(\d+)(?:\.(\d{1,2}))?$", digits)
    if not m:
        return None
    paise = int(m.group(1)) * 100 + int((m.group(2) or "0").ljust(2, "0"))
    return str(paise)


def _clean(fields: dict[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for k in FIELDS:
        v = fields.get(k)
        out[k] = None if v in (None, "", "null") else str(v).strip()
    if out["account"]:
        out["account"] = re.sub(r"\D", "", out["account"]) or None
    if out["ifsc"]:
        out["ifsc"] = out["ifsc"].upper().replace(" ", "")
    if out["gstin"]:
        out["gstin"] = out["gstin"].upper().replace(" ", "")
    if out["amount_paise"] and not out["amount_paise"].isdigit():
        out["amount_paise"] = _rupees_to_paise(out["amount_paise"])
    return out


class StubInvoiceReader:
    """Regex over the text layer. Offline, deterministic, and gullible on purpose."""

    def read(self, pdf: bytes) -> InvoiceReading:
        text = pdf_text(pdf)
        flat = " ".join(text.split())

        def find(pattern: str) -> str | None:
            m = re.search(pattern, flat, re.IGNORECASE)
            return m.group(1).strip() if m else None

        fields: dict[str, Any] = {
            "vendor_name": (text.strip().splitlines() or [None])[0],
            "gstin": find(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b"),
            "account": find(
                r"(?:A/?c(?:count)?\.?\s*(?:No\.?|number)?|Account)\s*[:#]?\s*(\d{9,18})"
            ),
            "ifsc": find(r"\b([A-Z]{4}0[A-Z0-9]{6})\b"),
            "invoice_number": find(r"Invoice\s*(?:No\.?|Number|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9/-]+)"),
            "invoice_date": find(
                r"(?:Invoice\s*)?Date\s*[:#]?\s*([0-9]{1,2}[ /.-][A-Za-z0-9]{1,9}[ /.-][0-9]{2,4})"
            ),
        }
        amount = find(
            r"(?:Total|Amount\s*(?:Due|Payable)|Grand\s*Total)[^0-9₹]{0,20}(?:₹|Rs\.?|INR)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)"
        )
        fields["amount_paise"] = _rupees_to_paise(amount) if amount else None

        notes: list[str] = []
        # The gullible part: a naive agent treats an embedded instruction as data.
        hijack = find(r"pay\s+(?:to\s+)?account\s*(?:no\.?|number)?\s*[:#]?\s*(\d{9,18})")
        if hijack and hijack != fields["account"]:
            notes.append(f"followed an instruction inside the document to pay {hijack}")
            fields["account"] = hijack
        return InvoiceReading(_clean(fields), text, "stub", "regex-stub", notes)


PROMPT = """You are reading a supplier invoice for an accounts-payable team in India.
Return only JSON with these keys, each a string or null:
vendor_name, gstin, account (the supplier's bank account number, digits only), ifsc,
amount_paise (the total payable, in paise, digits only), invoice_number, invoice_date (YYYY-MM-DD).
Copy what the invoice prints. If a field is not printed, use null. Do not guess."""


class GeminiInvoiceReader:
    def __init__(self, project: str, location: str, model: str):
        from google import genai

        self.model = model
        self.client = genai.Client(vertexai=True, project=project, location=location)

    def read(self, pdf: bytes) -> InvoiceReading:
        from google.genai import types

        text = pdf_text(pdf)
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[types.Part.from_bytes(data=pdf, mime_type="application/pdf"), PROMPT],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {k: {"type": "STRING", "nullable": True} for k in FIELDS},
                },
            ),
        )
        try:
            data = json.loads(resp.text or "{}")
        except json.JSONDecodeError:
            data = {}
        version = getattr(resp, "model_version", None) or self.model
        return InvoiceReading(_clean(data), text, "gemini", version)


def get_invoice_reader(settings: Any) -> InvoiceReader:
    if settings.USE_REAL_AI:
        return GeminiInvoiceReader(
            settings.GCP_PROJECT, settings.GEMINI_LOCATION, settings.GEMINI_MODEL
        )
    return StubInvoiceReader()


EXPLAIN_PROMPT = """You write one or two plain sentences for a finance approver in India explaining
why a payment was held. Use only the facts given. Do not recommend approving or declining.
Facts (JSON): {facts}"""


def explain_hold(settings: Any, facts: dict[str, Any]) -> dict[str, str] | None:
    """Gemini's plain-language note on a hold. Real AI only; the rule reasons stand without it."""
    if not settings.USE_REAL_AI:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=True, project=settings.GCP_PROJECT, location=settings.GEMINI_LOCATION
        )
        resp = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=EXPLAIN_PROMPT.format(facts=json.dumps(facts, ensure_ascii=False)),
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=160),
        )
        text = (resp.text or "").strip()
        if not text:
            return None
        return {
            "text": text,
            "source": "gemini",
            "modelVersion": getattr(resp, "model_version", None) or settings.GEMINI_MODEL,
        }
    except Exception as e:  # an explanation is a nicety; never fail the payment over it
        logger.warning(f"Gemini explanation failed: {type(e).__name__}: {e}")
        return None
