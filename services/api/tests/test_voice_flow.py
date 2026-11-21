"""Tier 2 in the live flow: signature, then the spoken code, then the mandate."""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.db.engine import unit_of_work
from app.db.models import Device, PaymentIntent
from app.domain.ids import new_id
from tests.test_live_flow import make_test_env

CFO = {"X-Dev-User": "cfo@acme.example"}


def _setup(tmp_path: Path, amount: str):
    client, rt, _ = make_test_env(tmp_path)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    with unit_of_work(rt.sessions) as s:
        s.add(
            Device(
                device_id=new_id("dv"),
                approver_email="cfo@acme.example",
                phone_model="t",
                public_key_pem=pem,
                key_security_level="StrongBox",
                patch_level="2026-10-01",
                fcm_token=None,
                revoked=False,
                enrolled_at=rt.clock(),
            )
        )
    for who in ("ap.manager@acme.example", "controller@acme.example"):
        r = client.post(
            "/v1/_local/delegations",
            json={"delegate_email": "cfo@acme.example"},
            headers={"X-Dev-User": who},
        )
        assert r.status_code in (200, 201), r.text
    r = client.post(
        "/v1/intents",
        headers={"X-Dev-User": "clerk"},
        json={
            "payee_vendor_id": "vd_sri_lakshmi",
            "amount_paise": amount,
            "purpose": "INV-TIER2",
            "instruction_channel": "chat",
            "entry_route": "erp",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
        },
    )
    assert r.status_code == 201, r.text
    intent_id = r.json()["intent_id"]
    aps = client.get("/v1/approvals?status=pending", headers=CFO).json()["approvals"]
    approval_id = next(a for a in aps if a["intent_id"] == intent_id)["approval_id"]
    d = client.get(f"/v1/approvals/{approval_id}", headers=CFO).json()
    sig = key.sign(base64.b64decode(d["canonical_b64"]), ec.ECDSA(hashes.SHA256()))
    r = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers=CFO,
        json={"decision": "approve", "signature": base64.b64encode(sig).decode()},
    )
    assert r.status_code == 200, r.text
    return client, rt, intent_id, approval_id, r.json()


def _mandate(rt, intent_id):
    with unit_of_work(rt.sessions) as s:
        i = s.get(PaymentIntent, intent_id)
        return i.tier, i.status, i.mandate_id


def test_tier2_needs_the_spoken_code_before_a_mandate(tmp_path: Path) -> None:
    client, rt, intent_id, approval_id, decision = _setup(tmp_path, "300000000")  # Rs 30 lakh
    assert decision["next"] == "voice" and decision["mandate_id"] is None
    tier, status, mandate = _mandate(rt, intent_id)
    assert tier >= 2 and status == "held" and mandate is None

    url = f"/v1/approvals/{approval_id}/voice"
    start = client.post(url, headers=CFO, json={"action": "start", "language": "ta"})
    assert start.status_code == 200, start.text
    code, voice_id = start.json()["code"], start.json()["voice_id"]
    done = client.post(
        url, headers=CFO, json={"action": "complete", "voice_id": voice_id, "digits": code}
    )
    assert done.status_code == 200 and done.json()["matched"] is True, done.text

    _, status, mandate = _mandate(rt, intent_id)
    assert status == "approved" and mandate and mandate.startswith("pm_")
    r = client.post("/v1/gate/release", headers=CFO, json={"mandate_id": mandate})
    assert r.status_code == 200, r.text


def test_three_wrong_codes_block_the_payment(tmp_path: Path) -> None:
    client, rt, intent_id, approval_id, _ = _setup(tmp_path, "300000000")
    url = f"/v1/approvals/{approval_id}/voice"
    start = client.post(url, headers=CFO, json={"action": "start", "language": "en"})
    code, voice_id = start.json()["code"], start.json()["voice_id"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(3):
        client.post(
            url, headers=CFO, json={"action": "complete", "voice_id": voice_id, "digits": wrong}
        )
    _, status, mandate = _mandate(rt, intent_id)
    assert status == "blocked" and mandate is None


def test_voice_cannot_start_without_a_verified_signature(tmp_path: Path) -> None:
    client, rt, intent_id, approval_id, _ = _setup(tmp_path, "300000000")
    # someone else's identity cannot use this approval
    r = client.post(
        f"/v1/approvals/{approval_id}/voice",
        headers={"X-Dev-User": "clerk@acme.example"},
        json={"action": "start", "language": "en"},
    )
    assert r.status_code == 404


def test_tier1_is_unchanged(tmp_path: Path) -> None:
    client, rt, intent_id, approval_id, decision = _setup(tmp_path, "20000000")  # Rs 2 lakh
    assert decision.get("next") is None and decision["mandate_id"].startswith("pm_")
