"""Live attestation revocation list and key-device correlation at enrolment."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.db.engine import unit_of_work
from app.db.models import Device, EnrolmentChallenge
from app.domain import attestation
from app.domain.attestation import AttestationError, RevocationList
from app.domain.ids import new_id
from app.routers import devices
from tests.test_live_flow import CAPTURE_NOW, FIXTURES_DIR, make_test_env

# --- RevocationList fetch behaviour -------------------------------------------------


class _Resp:
    def __init__(self, data: object) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._data


def test_live_list_is_fetched_once_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_get(url: str, timeout: float) -> _Resp:
        calls.append(url)
        return _Resp({"entries": {"abc": {"status": "REVOKED", "reason": "KEY_COMPROMISE"}}})

    monkeypatch.setattr(attestation.httpx, "get", fake_get)
    rl = RevocationList()
    assert rl.is_revoked("00ABC") is True
    assert rl.is_revoked(0xABD) is False
    assert calls == [attestation.STATUS_URL]


def test_fail_closed_refuses_when_list_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(url: str, timeout: float) -> _Resp:
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(attestation.httpx, "get", boom)
    with pytest.raises(AttestationError) as exc:
        RevocationList(fail_closed=True).is_revoked(1)
    assert exc.value.code == "revocation_list_unavailable"


def test_fail_open_backs_off_instead_of_refetching(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def boom(url: str, timeout: float) -> _Resp:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(attestation.httpx, "get", boom)
    rl = RevocationList()
    for serial in (1, 2, 3, 4):  # one chain: leaf, two intermediates, root
        assert rl.is_revoked(serial) is False
    assert calls == 1


def test_get_revocation_list_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # drop conftest's stub (same monkeypatch instance) to test the real one
    monkeypatch.setattr(devices, "_revocation_lists", {})
    off = devices.get_revocation_list(Settings(ENV="dev", ATTEST_REVOCATION_LIVE=False))
    assert off.is_revoked(1) is False  # empty list, no fetch
    local = devices.get_revocation_list(Settings(ENV="local"))
    cloud = devices.get_revocation_list(Settings(ENV="dev"))
    assert local.fail_closed is False
    assert cloud.fail_closed is True
    assert devices.get_revocation_list(Settings(ENV="prod")) is cloud  # shared 24 h cache


# --- Key-device correlation ----------------------------------------------------------


def _enrol(client, rt, email: str) -> httpx.Response:
    phone = json.loads((FIXTURES_DIR / "attestation_real_phone.json").read_text("utf-8"))
    with unit_of_work(rt.sessions) as s:
        # The captured chain embeds one fixed challenge; drop the used row so the
        # same chain can be offered again (nonces are unique).
        s.query(EnrolmentChallenge).filter_by(nonce=phone["challenge_b64"]).delete()
        s.add(
            EnrolmentChallenge(
                challenge_id=new_id("ch"),
                approver_email=email,
                nonce=phone["challenge_b64"],
                used=False,
                created_at=CAPTURE_NOW,
                expires_at=CAPTURE_NOW + timedelta(minutes=5),
            )
        )
    return client.post(
        "/v1/devices/enrol",
        headers={"X-Dev-User": email},
        json={"chain_b64": phone["chain_b64"], "nonce": phone["challenge_b64"]},
    )


def test_same_key_cannot_enrol_for_a_second_approver(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path, CAPTURE_NOW)
    assert _enrol(client, rt, "cfo@acme.example").status_code == 201

    resp = _enrol(client, rt, "ap.manager@acme.example")
    assert resp.status_code == 409, resp.text
    assert resp.json()["type"].endswith("/key-already-enrolled")
    with unit_of_work(rt.sessions) as s:
        assert s.query(Device).filter_by(approver_email="ap.manager@acme.example").count() == 0


def test_same_approver_can_re_enrol_the_same_key(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path, CAPTURE_NOW)
    first = _enrol(client, rt, "cfo@acme.example")
    second = _enrol(client, rt, "cfo@acme.example")
    assert second.status_code == 201, second.text
    assert second.json()["device_id"] == first.json()["device_id"]


def test_revoked_device_frees_the_key(tmp_path: Path) -> None:
    client, rt, _ = make_test_env(tmp_path, CAPTURE_NOW)
    assert _enrol(client, rt, "cfo@acme.example").status_code == 201
    with unit_of_work(rt.sessions) as s:
        for d in s.query(Device).filter_by(approver_email="cfo@acme.example"):
            d.revoked = True
    assert _enrol(client, rt, "ap.manager@acme.example").status_code == 201
