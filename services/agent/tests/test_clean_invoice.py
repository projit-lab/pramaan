"""Tests processing a genuine, clean invoice (INV-2219.pdf)."""

from pathlib import Path
from pramaan_agent.payables_agent import PayablesAgent

INVOICE_PATH = Path(__file__).resolve().parents[3] / "data" / "invoices" / "INV-2219.pdf"


def test_clean_invoice_processing():
    assert INVOICE_PATH.exists(), f"Invoice file not found: {INVOICE_PATH}"

    captured_payloads = []

    def mock_create_intent(**kwargs):
        captured_payloads.append(kwargs)
        return {
            "intent_id": "pi_01JD2XCLEAN001",
            "status": "held",
            "tier": 2,  # Held because raised by an AI agent and amount > 5 lakh
            "decision": "hold",
        }

    agent = PayablesAgent(create_intent_fn=mock_create_intent)
    result = agent.process_invoice(INVOICE_PATH)

    assert result.invoice_ref == "INV-2219"
    assert result.model_armor_finding is None
    assert result.status == "mandate_requested"
    assert result.held is True
    assert result.intent_id == "pi_01JD2XCLEAN001"

    # Verify no mismatch
    mismatches = [r for r in result.reasons if r.get("code") == "invoice_account_mismatch"]
    assert len(mismatches) == 0

    # Verify create_intent payload
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["payee_vendor_id"] == "vd_sri_lakshmi"
    assert payload["amount_paise"] == "98000000"
    assert payload["purpose"] == "INV-2219"
    assert payload["instruction_channel"] == "agent"
    assert payload["entry_route"] == "agent"
    assert payload["initiator"]["type"] == "agent"

    # Verify audit log
    sources = [entry["source"] for entry in result.log]
    assert "rule" in sources
    assert "gemini" in sources
    assert "model_armor" not in sources  # No Model Armor finding on clean invoice
