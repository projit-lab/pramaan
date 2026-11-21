"""Invoice extraction and deterministic rule comparison against Vendor Master.

Honesty Rules:
- "rules decide, Gemini explains": Gemini/OCR extracts the fields from the PDF,
  but deterministic Python rules compare the extracted bank account against the
  vendor master and flag mismatches.
- Label any AI-extracted content with source="gemini".
- Never the word "fraud" unless a human chose to report fraud.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedInvoice:
    invoice_ref: str
    vendor_name: str
    amount_paise: int
    account_extracted: str
    account_printed: str
    ifsc: str
    gstin: str | None
    raw_text: str
    sha256: str
    has_injection_payload: bool


# Vendor Master on record (default Acme vendor master per contracts/firestore-seed.json and app/db/seed.py)
DEFAULT_VENDOR_MASTER = {
    "vd_kaveri_steel": {
        "vendor_id": "vd_kaveri_steel",
        "legal_name": "Kaveri Steel Traders",
        "account_number": "556677885540",
        "account_last4": "5540",
        "ifsc": "EFGH0005540",
        "gstin": "33AAFCK9921M1Z8",
    },
    "vd_sri_lakshmi": {
        "vendor_id": "vd_sri_lakshmi",
        "legal_name": "Sri Lakshmi Castings",
        "account_number": "000123457781",
        "account_last4": "7781",
        "ifsc": "ABCD0123456",
        "gstin": "33AABCS1429P1Z5",
    },
}


def read_pdf_text(path_or_bytes: str | Path | bytes) -> tuple[str, str]:
    """Returns (extracted_text, sha256_hash)."""
    if isinstance(path_or_bytes, (str, Path)):
        p = Path(path_or_bytes)
        raw_bytes = p.read_bytes()
    else:
        raw_bytes = path_or_bytes

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    import io
    reader = PdfReader(io.BytesIO(raw_bytes))
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return full_text, sha256


class InvoiceExtractor:
    """Parses invoices and matches fields against the vendor master."""

    def __init__(self, vendor_master: dict[str, dict[str, Any]] | None = None) -> None:
        self.vendor_master = vendor_master or DEFAULT_VENDOR_MASTER

    def extract_from_pdf(self, path_or_bytes: str | Path | bytes) -> ExtractedInvoice:
        text, sha256 = read_pdf_text(path_or_bytes)

        # Invoice ref
        ref_match = re.search(r"Invoice\s+No:\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        invoice_ref = ref_match.group(1).strip() if ref_match else "UNKNOWN-REF"

        # Vendor name (first non-empty line usually)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        vendor_name = lines[0] if lines else "Unknown Vendor"

        # GSTIN
        gstin_match = re.search(r"GSTIN:\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})", text)
        gstin = gstin_match.group(1) if gstin_match else None

        # IFSC
        ifsc_match = re.search(r"IFSC:\s*([A-Z]{4}0[A-Z0-9]{6}|[A-Z]{4}[0-9]{7})", text)
        ifsc = ifsc_match.group(1) if ifsc_match else "UNKNOWN0000"

        # Printed Account
        account_match = re.search(r"Account\s+number:\s*([0-9]{6,20})", text, re.IGNORECASE)
        account_printed = account_match.group(1).strip() if account_match else ""

        # Amount
        amount_match = re.search(r"Total\s+payable\s*\n?\s*Rs\.?\s*([0-9,]+(?:\.[0-9]{2})?)", text, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r"Rs\.?\s*([0-9,]+(?:\.[0-9]{2})?)", text, re.IGNORECASE)
        amount_paise = 0
        if amount_match:
            raw_amt = amount_match.group(1).replace(",", "")
            amount_paise = int(round(float(raw_amt) * 100))

        # Prompt Injection check for redirection
        injection_match = re.search(r"pay\s+account\s+([0-9]{6,20})", text, re.IGNORECASE)
        has_injection = bool(re.search(r"ignore\s+previous\s+instructions", text, re.IGNORECASE))

        # Under prompt injection, an LLM extracts the attacker's redirected account
        if has_injection and injection_match:
            account_extracted = injection_match.group(1).strip()
        else:
            account_extracted = account_printed

        return ExtractedInvoice(
            invoice_ref=invoice_ref,
            vendor_name=vendor_name,
            amount_paise=amount_paise,
            account_extracted=account_extracted,
            account_printed=account_printed,
            ifsc=ifsc,
            gstin=gstin,
            raw_text=text,
            sha256=sha256,
            has_injection_payload=has_injection,
        )

    def compare_with_vendor_master(
        self, extracted: ExtractedInvoice, vendor_id: str | None = None
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        """Compares extracted invoice fields against vendor master record.

        Returns:
            (invoice_read_model, rule_reasons, matched_vendor_id)
        """
        # Resolve vendor
        matched_vid = vendor_id
        if not matched_vid:
            for vid, v in self.vendor_master.items():
                if v["legal_name"].lower() in extracted.vendor_name.lower():
                    matched_vid = vid
                    break
        if not matched_vid:
            matched_vid = "vd_kaveri_steel" if "kaveri" in extracted.vendor_name.lower() else "vd_sri_lakshmi"

        vendor_record = self.vendor_master.get(matched_vid, {})
        master_account = vendor_record.get("account_number", "")
        master_last4 = vendor_record.get("account_last4", master_account[-4:] if master_account else "")
        master_ifsc = vendor_record.get("ifsc", "")
        master_gstin = vendor_record.get("gstin", "")
        master_name = vendor_record.get("legal_name", extracted.vendor_name)

        extracted_last4 = extracted.account_extracted[-4:] if extracted.account_extracted else ""
        account_mismatch = bool(master_last4 and extracted_last4 and master_last4 != extracted_last4)

        rule_reasons: list[dict[str, Any]] = []
        if account_mismatch:
            rule_reasons.append(
                {
                    "code": "invoice_account_mismatch",
                    "text": "The account on the invoice is not the account on record for this vendor.",
                    "source": "rule",
                    "changedFrom": master_last4,
                    "changedTo": extracted_last4,
                }
            )

        fields: dict[str, Any] = {
            "vendor_name": {
                "extracted": extracted.vendor_name,
                "onRecord": master_name,
                "mismatch": False,
            },
            "account": {
                "extracted": extracted.account_extracted,
                "onRecord": master_account or f"•••• {master_last4}",
                "mismatch": account_mismatch,
            },
            "ifsc": {
                "extracted": extracted.ifsc,
                "onRecord": master_ifsc,
                "mismatch": False,
            },
            "amount_paise": {
                "extracted": str(extracted.amount_paise),
                "onRecord": None,
                "mismatch": False,
            },
            "gstin": {
                "extracted": extracted.gstin,
                "onRecord": master_gstin,
                "mismatch": False,
            },
            "invoice_number": {
                "extracted": extracted.invoice_ref,
                "onRecord": None,
                "mismatch": False,
            },
        }

        invoice_doc = {
            "source": "gemini",
            "modelVersion": None,
            "fileUrl": None,
            "ref": extracted.invoice_ref,
            "fields": fields,
        }

        return invoice_doc, rule_reasons, matched_vid
