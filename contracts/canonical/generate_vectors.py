#!/usr/bin/env python3
"""
Generates contracts/canonical/vectors.json.

DRAFT, proposed by Shoaib, needs Prajit's approval. He owns the canonical summary
spec; this script only turns that spec into cases both sides can test against.

The canonical payment summary, from the build plan (page 21):

  - A JSON object, keys sorted by Unicode code point.
  - No whitespace anywhere: separators are "," and ":".
  - Every value is a string. Numbers are strings; there are no nulls, no
    booleans, no nested objects and no arrays.
  - UTF-8, with non-ASCII characters emitted raw rather than as \\uXXXX escapes.
  - Only ", \\ and the C0 control characters are escaped, the standard JSON way.
  - Every name is normalised to Unicode NFC before encoding, or a Tamil name
    hashes differently on each side.
  - The signature always covers the FULL payee account number. The screen shows
    the last four; the bytes carry all of it.

  Fields, in sorted order:
    amount_paise, currency, expires_at, initiator, intent_id, invoice_sha256,
    nonce, payee_account, payee_ifsc, payee_name, payer_account, purpose, v

Run:  python contracts/canonical/generate_vectors.py
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

FIELDS = [
    "amount_paise",
    "currency",
    "expires_at",
    "initiator",
    "intent_id",
    "invoice_sha256",
    "nonce",
    "payee_account",
    "payee_ifsc",
    "payee_name",
    "payer_account",
    "purpose",
    "v",
]

# Fields holding human-written text, which must be NFC-normalised. Identifiers,
# account numbers and hashes are left exactly as given: normalising an account
# number would be a silent data change, not a fix.
TEXT_FIELDS = {"payee_name", "purpose"}


def canonical_string(payment: dict[str, str]) -> str:
    """The exact string both Kotlin and Python must produce."""
    missing = [field for field in FIELDS if field not in payment]
    if missing:
        raise ValueError(f"missing fields: {missing}")
    extra = [key for key in payment if key not in FIELDS]
    if extra:
        raise ValueError(f"unknown fields: {extra}")
    for key, value in payment.items():
        if not isinstance(value, str):
            raise TypeError(f"{key} must be a string, got {type(value).__name__}")

    normalised = {
        key: (unicodedata.normalize("NFC", value) if key in TEXT_FIELDS else value)
        for key, value in payment.items()
    }

    # sort_keys sorts by code point, which is what the spec asks for.
    return json.dumps(
        normalised,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def vector(name: str, description: str, payment: dict[str, str]) -> dict[str, object]:
    canonical = canonical_string(payment)
    encoded = canonical.encode("utf-8")
    return {
        "name": name,
        "description": description,
        "payment": payment,
        "canonical": canonical,
        "canonical_utf8_bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def base(**overrides: str) -> dict[str, str]:
    payment = {
        "amount_paise": "98000000",
        "currency": "INR",
        "expires_at": "2026-11-21T11:42:07+05:30",
        "initiator": "human:clerk@acme.example",
        "intent_id": "pi_01JD2XGENUINE0001",
        "invoice_sha256": "9f1c2b7a4d6e8f0a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f607182",
        "nonce": "q7ZpL2nR8sT4vW6yX0zA1bC3dE5fG7hJ",
        "payee_account": "000123457781",
        "payee_ifsc": "ABCD0123456",
        "payee_name": "Sri Lakshmi Castings",
        "payer_account": "50100004521",
        "purpose": "INV-2219",
        "v": "1",
    }
    payment.update(overrides)
    return payment


VECTORS = [
    vector(
        "genuine_payment",
        "The ordinary case: INV-2219 to a known vendor. Demo moment 2.",
        base(),
    ),
    vector(
        "boss_scam_new_payee",
        "Demo moment 1: Rupees 46,50,000 to a brand-new payee, raised by a clerk.",
        base(
            amount_paise="465000000",
            intent_id="pi_01JD2XBOSSSCAM0001",
            payee_account="774120098032",
            payee_ifsc="WXYZ0004411",
            payee_name="Global Trade Solutions",
            purpose="Urgent vendor advance",
            invoice_sha256="",
        ),
    ),
    vector(
        "tamil_payee_name",
        "A Tamil payee name. Required by the build plan: the single most likely "
        "place for Kotlin and Python to disagree.",
        base(payee_name="ஸ்ரீ லட்சுமி காஸ்டிங்கஸ்"),
    ),
    vector(
        "crore_sized_amount",
        "Required by the build plan. Rupees 10.40 crore, the INOX total, in paise. "
        "Larger than a 32-bit integer and larger than a float can hold exactly, "
        "which is why amounts are strings.",
        base(amount_paise="10400000000", intent_id="pi_01JD2XCRORE000001"),
    ),
    vector(
        "account_with_leading_zeros",
        "Required by the build plan. An account number that must keep its leading "
        "zeros: parse it as a number anywhere and the signature breaks.",
        base(payee_account="000000045210", payer_account="00050100004521"),
    ),
    vector(
        "nfc_already_composed",
        "A Latin name with an accent, already in NFC. Pairs with "
        "nfc_decomposed_input: both must produce identical canonical bytes.",
        base(payee_name="Café Steel Works"),
    ),
    vector(
        "nfc_decomposed_input",
        "The same name supplied in NFD, as e followed by a combining acute accent. "
        "Normalisation must make this byte-identical to nfc_already_composed. If "
        "these two hashes differ, the implementation is not normalising.",
        base(payee_name="Café Steel Works"),
    ),
    vector(
        "tamil_decomposed_input",
        "A Tamil name whose vowel sign is supplied decomposed. NFC must compose it, "
        "so this matches the composed spelling of the same name.",
        base(payee_name="கொள்ளிடம் Metals"),
    ),
    vector(
        "hindi_payee_name",
        "A Devanagari payee name, for the Hindi-speaking approvers in Tier 2.",
        base(payee_name="कावेरी स्टील ट्रेडर्स"),
    ),
    vector(
        "name_needing_json_escapes",
        "A payee name containing a double quote and a backslash. These are the only "
        "characters besides control codes that get escaped, and they must be "
        "escaped the same way on both sides.",
        base(payee_name='Sri "Lakshmi" Castings \\ Foundry'),
    ),
    vector(
        "ampersand_and_slash_in_purpose",
        "Characters that some JSON writers escape unnecessarily. They must be "
        "emitted raw: & and / are ordinary characters.",
        base(purpose="INV-2219/A & B"),
    ),
    vector(
        "agent_initiator",
        "Demo moment 4: raised by the payables agent rather than a person. The "
        "initiator string is what tells the policy engine to raise the tier.",
        base(
            amount_paise="184000000",
            initiator="agent:payables-agent-01",
            intent_id="pi_01JD2XPOISONED001",
            payee_account="556677885540",
            payee_ifsc="EFGH0005540",
            payee_name="Kaveri Steel Traders",
            purpose="KAVERI-4471",
        ),
    ),
    vector(
        "tier2_voice_amount",
        "Demo moment 5: Rupees 30,00,000, which crosses the Tier 2 threshold.",
        base(amount_paise="300000000", intent_id="pi_01JD2XVOICE0000001"),
    ),
    vector(
        "smallest_amount",
        "One paise. The lower boundary, and a reminder that the amount is paise "
        "rather than rupees.",
        base(amount_paise="1"),
    ),
]


def main() -> None:
    out = Path(__file__).with_name("vectors.json")
    out.write_text(json.dumps(VECTORS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # The NFC pair is the whole point of having these vectors, so assert it here
    # rather than hope someone notices.
    by_name = {v["name"]: v for v in VECTORS}
    composed = by_name["nfc_already_composed"]["sha256"]
    decomposed = by_name["nfc_decomposed_input"]["sha256"]
    assert composed == decomposed, "NFC normalisation is not being applied"

    print(f"wrote {len(VECTORS)} vectors to {out}")
    for v in VECTORS:
        print(f"  {v['name']:<32} {v['canonical_utf8_bytes']:>4} bytes  {v['sha256'][:16]}...")


if __name__ == "__main__":
    main()
