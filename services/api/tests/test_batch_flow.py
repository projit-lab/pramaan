"""Signed batches: one fingerprint approves a window's Tier 1 lines; the gate
releases each line once, and refuses a line changed after signing."""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.db.engine import unit_of_work
from app.db.models import Batch, Device, PaymentIntent
from app.domain.ids import new_id
from tests.test_live_flow import make_test_env

CLERK = {"X-Dev-User": "clerk"}
GATE = {"X-Dev-User": "service_payout"}


def _enrol(rt, email: str) -> ec.EllipticCurvePrivateKey:
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
                approver_email=email,
                phone_model="Test Phone",
                public_key_pem=pem,
                key_security_level="StrongBox",
                patch_level="2026-10-01",
                fcm_token=None,
                revoked=False,
                enrolled_at=rt.clock(),
            )
        )
    return key


def _batch(client, rt, amounts: list[str]) -> tuple[str, str, list[str]]:
    ids = []
    for n, amount in enumerate(amounts):
        r = client.post(
            "/v1/intents",
            headers=CLERK,
            json={
                "payee_vendor_id": "vd_sri_lakshmi",
                "amount_paise": amount,
                "purpose": f"INV-30{n}",
                "instruction_channel": "portal",
                "entry_route": "erp",
                "initiator": {"type": "human", "id": "clerk@acme.example"},
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "held", body
        ids.append(body["intent_id"])
    with unit_of_work(rt.sessions) as s:
        rows = [s.get(PaymentIntent, i) for i in ids]
        assert all(r.lane == "batch" for r in rows), [(r.lane, r.tier) for r in rows]
        window = max(r.batch_window_at for r in rows)
    r = client.post("/v1/_local/jobs/close-batches", headers=CLERK, json={"at": window.isoformat()})
    assert r.status_code == 200, r.text
    made = r.json()["batches"]
    assert len(made) == 1, made
    return made[0]["batch_id"], made[0]["approver"], ids


def _sign(client, key, batch_id: str, approver: str) -> dict:
    h = {"X-Dev-User": approver}
    r = client.get(f"/v1/batches/{batch_id}", headers=h)
    assert r.status_code == 200, r.text
    sig = key.sign(base64.b64decode(r.json()["canonical_b64"]), ec.ECDSA(hashes.SHA256()))
    return {"headers": h, "signature": base64.b64encode(sig).decode(), "view": r.json()}


def test_one_fingerprint_signs_the_batch_and_each_line_releases_once(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)
    batch_id, approver, ids = _batch(client, rt, ["60000000", "70000000", "80000000"])
    key = _enrol(rt, approver)
    signed = _sign(client, key, batch_id, approver)
    assert signed["view"]["line_count"] == 3
    assert signed["view"]["summary_fields"]["kind"] == "batch"

    r = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "approve", "signature": signed["signature"]},
    )
    assert r.status_code == 200, r.text
    mandates = r.json()["mandates"]
    assert sorted(m["intent_id"] for m in mandates) == sorted(ids)

    for m in mandates:
        r = client.post("/v1/gate/release", headers=GATE, json={"mandate_id": m["mandate_id"]})
        assert r.status_code == 200, r.text
    again = client.post(
        "/v1/gate/release", headers=GATE, json={"mandate_id": mandates[0]["mandate_id"]}
    )
    assert again.status_code == 409

    # The batch is single use.
    replay = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "approve", "signature": signed["signature"]},
    )
    assert replay.status_code == 409


def test_a_line_changed_after_signing_is_refused_at_the_gate(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)
    batch_id, approver, ids = _batch(client, rt, ["60000000", "70000000"])
    key = _enrol(rt, approver)
    signed = _sign(client, key, batch_id, approver)
    r = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "approve", "signature": signed["signature"]},
    )
    assert r.status_code == 200, r.text
    target = r.json()["mandates"][0]

    t = client.post(f"/v1/_local/intents/{target['intent_id']}/tamper", headers=CLERK)
    assert t.status_code == 200, t.text
    r = client.post("/v1/gate/release", headers=GATE, json={"mandate_id": target["mandate_id"]})
    assert r.status_code == 409, r.text
    assert "differs" in r.text


def test_editing_the_stored_line_hashes_does_not_get_a_tampered_line_through(
    tmp_path: Path,
) -> None:
    client, rt, _ = make_test_env(tmp_path)
    batch_id, approver, _ = _batch(client, rt, ["60000000", "70000000"])
    key = _enrol(rt, approver)
    signed = _sign(client, key, batch_id, approver)
    r = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "approve", "signature": signed["signature"]},
    )
    target = r.json()["mandates"][0]
    client.post(f"/v1/_local/intents/{target['intent_id']}/tamper", headers=CLERK)
    # An attacker with database access also rewrites the stored line hashes.
    from app.domain.batch import line_hash

    with unit_of_work(rt.sessions) as s:
        b = s.get(Batch, batch_id)
        i = s.get(PaymentIntent, target["intent_id"])
        fields = signed["view"]["summary_fields"]
        b.line_hashes = [line_hash(i, fields["nonce"], fields["expires_at"])] + list(
            b.line_hashes[1:]
        )
    r = client.post("/v1/gate/release", headers=GATE, json={"mandate_id": target["mandate_id"]})
    assert r.status_code == 409, r.text


def test_wrong_key_and_tier_two_lines_are_refused(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)
    batch_id, approver, ids = _batch(client, rt, ["60000000", "70000000"])
    _enrol(rt, approver)
    other = ec.generate_private_key(ec.SECP256R1())
    signed = _sign(client, other, batch_id, approver)
    r = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "approve", "signature": signed["signature"]},
    )
    assert r.status_code == 422, r.text

    with unit_of_work(rt.sessions) as s:
        s.get(PaymentIntent, ids[0]).tier = 2
    r = client.get(f"/v1/batches/{batch_id}", headers={"X-Dev-User": approver})
    assert r.status_code == 422
    assert "never batched" in r.text


def test_declining_the_batch_blocks_every_line(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)
    batch_id, approver, ids = _batch(client, rt, ["60000000", "70000000"])
    key = _enrol(rt, approver)
    signed = _sign(client, key, batch_id, approver)
    r = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "decline", "signature": signed["signature"]},
    )
    assert r.status_code == 200, r.text
    with unit_of_work(rt.sessions) as s:
        assert {s.get(PaymentIntent, i).status for i in ids} == {"declined"}


def test_demo_assign_hands_the_batch_to_the_phone_on_stage(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)
    batch_id, _, ids = _batch(client, rt, ["60000000", "70000000"])
    r = client.post(
        f"/v1/_local/batches/{batch_id}/assign",
        headers=CLERK,
        json={"approver_email": "cfo@acme.example"},
    )
    assert r.status_code == 200, r.text
    key = _enrol(rt, "cfo@acme.example")
    signed = _sign(client, key, batch_id, "cfo@acme.example")
    r = client.post(
        f"/v1/batches/{batch_id}/decision",
        headers=signed["headers"],
        json={"decision": "approve", "signature": signed["signature"]},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["mandates"]) == 2
