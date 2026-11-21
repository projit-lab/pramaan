"""End-to-end tests for live flow: enrolment, approval signing, mandate, and gate release."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.adapters.event_bus import InMemoryEventBus
from app.adapters.notifier import InMemoryNotifier
from app.adapters.read_model import InMemoryReadModel
from app.config import Settings
from app.db.engine import make_engine, make_session_factory, unit_of_work
from app.db.models import Device, EnrolmentChallenge, PaymentIntent
from app.db.seed import seed_if_empty
from app.domain.ids import new_id
from app.domain.policy import IST
from app.main import create_app
from app.runtime import Runtime, migrate

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CAPTURE_NOW = datetime(2026, 11, 21, 0, 10, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.t = start or datetime(2026, 11, 20, 12, 0, tzinfo=IST)

    def __call__(self) -> datetime:
        return self.t


def make_test_env(tmp_path: Path, now: datetime | None = None) -> tuple[TestClient, Runtime, Clock]:
    url = f"sqlite:///{(tmp_path / 'live.db').as_posix()}"
    migrate(url)
    sessions = make_session_factory(make_engine(url))
    seed_if_empty(sessions)
    clock = Clock(now)
    rt = Runtime(
        settings=Settings(
            ENV="local",
            ANDROID_SIGNING_SHA256="3313d44bb45e66849411470eeffa85a49a66bc9d1a9718a2463b98898d93d968",
        ),
        sessions=sessions,
        event_bus=InMemoryEventBus(),
        read_model=InMemoryReadModel(),
        notifier=InMemoryNotifier(),
        clock=clock,
    )
    app = create_app()
    app.state.runtime = rt
    return TestClient(app), rt, clock


def test_enrol_happy_path_and_replay_rejected(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path, CAPTURE_NOW)

    fixture_path = FIXTURES_DIR / "attestation_real_phone.json"
    with open(fixture_path, encoding="utf-8") as f:
        phone_fixture = json.load(f)

    challenge_b64 = phone_fixture["challenge_b64"]
    chain_b64 = phone_fixture["chain_b64"]

    # Inject challenge as issued nonce for cfo@acme.example
    with unit_of_work(rt.sessions) as s:
        ch = EnrolmentChallenge(
            challenge_id=new_id("ch"),
            approver_email="cfo@acme.example",
            nonce=challenge_b64,
            used=False,
            created_at=CAPTURE_NOW,
            expires_at=CAPTURE_NOW + timedelta(minutes=5),
        )
        s.add(ch)

    # Call POST /v1/devices/enrol as CFO
    headers = {"X-Dev-User": "cfo@acme.example"}
    resp = client.post(
        "/v1/devices/enrol",
        headers=headers,
        json={
            "chain_b64": chain_b64,
            "nonce": challenge_b64,
            "phone_model": "Pixel 9 Pro",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["approver"] == "cfo@acme.example"
    assert data["key_security_level"] == "StrongBox"
    assert data["patch_level"] == "2026-10-01"
    device_id = data["device_id"]

    # Check device was written to read model
    doc = rt.read_model.get_document("devices", device_id)
    assert doc is not None
    assert doc["keySecurityLevel"] == "StrongBox"

    # Check device.enrolled event
    events = [e for e in rt.event_bus.events if e["event_type"] == "device.enrolled"]
    assert len(events) == 1
    assert events[0]["data"]["device_id"] == device_id

    # Replayed nonce must be rejected with 422
    resp_replay = client.post(
        "/v1/devices/enrol",
        headers=headers,
        json={
            "chain_b64": chain_b64,
            "nonce": challenge_b64,
            "phone_model": "Pixel 9 Pro",
        },
    )
    assert resp_replay.status_code == 422


def test_approve_end_to_end_mandate_and_single_release(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)

    # 1. Enrol a software key representing CFO phone
    device_key = ec.generate_private_key(ec.SECP256R1())
    device_pem = (
        device_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    device_id = new_id("dv")
    now = rt.clock()
    with unit_of_work(rt.sessions) as s:
        s.add(
            Device(
                device_id=device_id,
                approver_email="cfo@acme.example",
                phone_model="Test Phone",
                public_key_pem=device_pem,
                key_security_level="StrongBox",
                patch_level="2026-10-01",
                fcm_token=None,
                revoked=False,
                enrolled_at=now,
            )
        )

    # AP Manager delegates to CFO so CFO gets the individual Tier 1 approval
    client.post(
        "/v1/_local/delegations",
        json={"delegate_email": "cfo@acme.example"},
        headers={"X-Dev-User": "ap.manager@acme.example"},
    )

    # 2. Create held Tier 1 intent (instruction_channel='chat' sends it to individual lane)
    resp = client.post(
        "/v1/intents",
        headers={"X-Dev-User": "clerk"},
        json={
            "payee_vendor_id": "vd_sri_lakshmi",
            "amount_paise": "98000000",
            "currency": "INR",
            "purpose": "INV-2219",
            "instruction_channel": "chat",
            "entry_route": "erp",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
        },
    )
    assert resp.status_code == 201, resp.text
    intent_id = resp.json()["intent_id"]
    assert resp.json()["status"] == "held"
    assert resp.json()["tier"] == 1

    # 3. List approvals for CFO and get the approval ID
    resp = client.get("/v1/approvals?status=pending", headers={"X-Dev-User": "cfo@acme.example"})
    assert resp.status_code == 200
    approvals = resp.json()["approvals"]
    target = next(a for a in approvals if a["intent_id"] == intent_id)
    approval_id = target["approval_id"]

    # 4. GET /v1/approvals/{approval_id} to get canonical summary and nonce
    resp = client.get(f"/v1/approvals/{approval_id}", headers={"X-Dev-User": "cfo@acme.example"})
    assert resp.status_code == 200, resp.text
    appr_detail = resp.json()
    canonical_b64 = appr_detail["canonical_b64"]
    canonical_bytes_to_sign = base64.b64decode(canonical_b64)

    # 5. Sign with CFO phone key
    sig_der = device_key.sign(canonical_bytes_to_sign, ec.ECDSA(hashes.SHA256()))
    sig_b64 = base64.b64encode(sig_der).decode("ascii")

    # 6. POST /v1/approvals/{approval_id}/decision
    resp = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers={"X-Dev-User": "cfo@acme.example"},
        json={"decision": "approve", "signature": sig_b64},
    )
    assert resp.status_code == 200, resp.text
    decision_data = resp.json()
    assert decision_data["verified"] is True
    mandate_id = decision_data["mandate_id"]
    assert mandate_id.startswith("pm_")

    # Check mandate issued event
    mandate_events = [e for e in rt.event_bus.events if e["event_type"] == "mandate.issued"]
    assert len(mandate_events) == 1
    assert mandate_events[0]["data"]["mandate_id"] == mandate_id

    # 7. Release via gate: POST /v1/gate/release
    resp = client.post(
        "/v1/gate/release",
        headers={"X-Dev-User": "service_payout"},
        json={"mandate_id": mandate_id},
    )
    assert resp.status_code == 200, resp.text
    release_data = resp.json()
    payout_id = release_data["payout_id"]
    assert payout_id.startswith("po_")

    # Check payout in Firestore read model
    payout_doc = rt.read_model.get_document("payouts", payout_id)
    assert payout_doc is not None
    assert payout_doc["mandateId"] == mandate_id
    assert payout_doc["status"] == "paid"

    # Check payment.released event
    released_events = [e for e in rt.event_bus.events if e["event_type"] == "payment.released"]
    assert len(released_events) == 1
    assert released_events[0]["data"]["payout_id"] == payout_id

    # 8. Second release MUST be refused with 409
    resp_second = client.post(
        "/v1/gate/release",
        headers={"X-Dev-User": "service_payout"},
        json={"mandate_id": mandate_id},
    )
    assert resp_second.status_code == 409
    assert "already used" in resp_second.text


def test_tamper_then_release_refused(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)

    device_key = ec.generate_private_key(ec.SECP256R1())
    device_pem = (
        device_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    now = rt.clock()
    with unit_of_work(rt.sessions) as s:
        s.add(
            Device(
                device_id=new_id("dv"),
                approver_email="cfo@acme.example",
                phone_model="Test Phone",
                public_key_pem=device_pem,
                key_security_level="StrongBox",
                patch_level="2026-10-01",
                fcm_token=None,
                revoked=False,
                enrolled_at=now,
            )
        )

    # Delegate AP Manager to CFO
    client.post(
        "/v1/_local/delegations",
        json={"delegate_email": "cfo@acme.example"},
        headers={"X-Dev-User": "ap.manager@acme.example"},
    )

    # Create intent
    resp = client.post(
        "/v1/intents",
        headers={"X-Dev-User": "clerk"},
        json={
            "payee_vendor_id": "vd_sri_lakshmi",
            "amount_paise": "98000000",
            "currency": "INR",
            "purpose": "INV-2219",
            "instruction_channel": "chat",
            "entry_route": "erp",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
        },
    )
    intent_id = resp.json()["intent_id"]

    # Get approval
    resp = client.get("/v1/approvals?status=pending", headers={"X-Dev-User": "cfo@acme.example"})
    approval_id = next(a for a in resp.json()["approvals"] if a["intent_id"] == intent_id)[
        "approval_id"
    ]

    resp = client.get(f"/v1/approvals/{approval_id}", headers={"X-Dev-User": "cfo@acme.example"})
    appr_detail = resp.json()
    canonical_bytes_to_sign = base64.b64decode(appr_detail["canonical_b64"])

    # Sign and approve
    sig_der = device_key.sign(canonical_bytes_to_sign, ec.ECDSA(hashes.SHA256()))
    sig_b64 = base64.b64encode(sig_der).decode("ascii")

    resp = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers={"X-Dev-User": "cfo@acme.example"},
        json={"decision": "approve", "signature": sig_b64},
    )
    mandate_id = resp.json()["mandate_id"]

    # Tamper with stored payee account using local admin route
    resp_tamper = client.post(f"/v1/_local/intents/{intent_id}/tamper")
    assert resp_tamper.status_code == 200

    # Release attempt must fail with 409 mandate-mismatch
    resp_gate = client.post(
        "/v1/gate/release",
        headers={"X-Dev-User": "service_payout"},
        json={"mandate_id": mandate_id},
    )
    assert resp_gate.status_code == 409
    assert "does not match" in resp_gate.text

    # Payment intent in DB must be marked blocked
    with unit_of_work(rt.sessions) as s:
        i = s.get(PaymentIntent, intent_id)
        assert i.status == "blocked"

    # payment.blocked event was emitted
    blocked = [e for e in rt.event_bus.events if e["event_type"] == "payment.blocked"]
    assert any(b["data"]["reason"] == "mandate_mismatch" for b in blocked)


def test_wrong_device_key_refused(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)

    enrolled_key = ec.generate_private_key(ec.SECP256R1())
    enrolled_pem = (
        enrolled_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    wrong_key = ec.generate_private_key(ec.SECP256R1())

    now = rt.clock()
    with unit_of_work(rt.sessions) as s:
        s.add(
            Device(
                device_id=new_id("dv"),
                approver_email="cfo@acme.example",
                phone_model="Test Phone",
                public_key_pem=enrolled_pem,
                key_security_level="StrongBox",
                patch_level="2026-10-01",
                fcm_token=None,
                revoked=False,
                enrolled_at=now,
            )
        )

    client.post(
        "/v1/_local/delegations",
        json={"delegate_email": "cfo@acme.example"},
        headers={"X-Dev-User": "ap.manager@acme.example"},
    )

    resp = client.post(
        "/v1/intents",
        headers={"X-Dev-User": "clerk"},
        json={
            "payee_vendor_id": "vd_sri_lakshmi",
            "amount_paise": "98000000",
            "currency": "INR",
            "purpose": "INV-2219",
            "instruction_channel": "chat",
            "entry_route": "erp",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
        },
    )
    intent_id = resp.json()["intent_id"]

    resp = client.get("/v1/approvals?status=pending", headers={"X-Dev-User": "cfo@acme.example"})
    approval_id = next(a for a in resp.json()["approvals"] if a["intent_id"] == intent_id)[
        "approval_id"
    ]

    resp = client.get(f"/v1/approvals/{approval_id}", headers={"X-Dev-User": "cfo@acme.example"})
    canonical_bytes_to_sign = base64.b64decode(resp.json()["canonical_b64"])

    # Sign with WRONG key
    sig_der = wrong_key.sign(canonical_bytes_to_sign, ec.ECDSA(hashes.SHA256()))
    sig_b64 = base64.b64encode(sig_der).decode("ascii")

    resp = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers={"X-Dev-User": "cfo@acme.example"},
        json={"decision": "approve", "signature": sig_b64},
    )
    assert resp.status_code == 422
    assert "signature invalid" in resp.text.lower()


def test_decline_blocks(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)

    device_key = ec.generate_private_key(ec.SECP256R1())
    device_pem = (
        device_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    now = rt.clock()
    with unit_of_work(rt.sessions) as s:
        s.add(
            Device(
                device_id=new_id("dv"),
                approver_email="cfo@acme.example",
                phone_model="Test Phone",
                public_key_pem=device_pem,
                key_security_level="StrongBox",
                patch_level="2026-10-01",
                fcm_token=None,
                revoked=False,
                enrolled_at=now,
            )
        )

    client.post(
        "/v1/_local/delegations",
        json={"delegate_email": "cfo@acme.example"},
        headers={"X-Dev-User": "ap.manager@acme.example"},
    )

    resp = client.post(
        "/v1/intents",
        headers={"X-Dev-User": "clerk"},
        json={
            "payee_vendor_id": "vd_sri_lakshmi",
            "amount_paise": "98000000",
            "currency": "INR",
            "purpose": "INV-2219",
            "instruction_channel": "chat",
            "entry_route": "erp",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
        },
    )
    intent_id = resp.json()["intent_id"]

    resp = client.get("/v1/approvals?status=pending", headers={"X-Dev-User": "cfo@acme.example"})
    approval_id = next(a for a in resp.json()["approvals"] if a["intent_id"] == intent_id)[
        "approval_id"
    ]

    resp = client.get(f"/v1/approvals/{approval_id}", headers={"X-Dev-User": "cfo@acme.example"})
    canonical_bytes_to_sign = base64.b64decode(resp.json()["canonical_b64"])

    sig_der = device_key.sign(canonical_bytes_to_sign, ec.ECDSA(hashes.SHA256()))
    sig_b64 = base64.b64encode(sig_der).decode("ascii")

    resp = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers={"X-Dev-User": "cfo@acme.example"},
        json={"decision": "decline", "signature": sig_b64},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"
    assert resp.json()["mandate_id"] is None

    # Intent in DB must be declined
    with unit_of_work(rt.sessions) as s:
        i = s.get(PaymentIntent, intent_id)
        assert i.status == "declined"

    blocked = [e for e in rt.event_bus.events if e["event_type"] == "payment.blocked"]
    assert any(b["data"]["reason"] == "declined_by_approver" for b in blocked)


def test_new_intent_writes_the_console_hold_document(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path)
    resp = client.post(
        "/v1/intents",
        headers={"X-Dev-User": "clerk"},
        json={
            "payee_vendor_id": "vd_sri_lakshmi",
            "amount_paise": "20000000",
            "purpose": "INV-2219",
            "instruction_channel": "chat",
            "entry_route": "erp",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
        },
    )
    assert resp.status_code == 201, resp.text
    hold = rt.read_model.get_document("holds", resp.json()["intent_id"])
    assert hold is not None
    assert hold["status"] == "held"
    assert hold["payeeNameAtBank"]
    assert hold["entryRoute"] == "erp"
    assert hold["lane"] == "individual_review"
