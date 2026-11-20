"""Devices router (M1, Prajit).

Handles approver phone enrolment challenge, attestation verification, and device listing.
Contracts: contracts/openapi.yaml, contracts/firestore.md, contracts/events.md.
"""

from __future__ import annotations

import base64
import secrets
from datetime import timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Device, EnrolmentChallenge
from app.domain.attestation import AttestationError, RevocationList, verify_attestation
from app.domain.ids import new_id
from app.domain.models import AuthenticatedUser
from app.errors import ProblemException
from app.roles import require_email, require_roles
from app.runtime import Runtime, get_runtime, utc_now
from app.services.views import aware, ist

router = APIRouter(tags=["devices"])


class EnrolDeviceIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chain_b64: list[str] = Field(min_length=1)
    nonce: str | None = None
    challenge_b64: str | None = None
    phone_model: str | None = None
    fcm_token: str | None = None


@router.post(
    "/devices/enrol/challenge",
    status_code=status.HTTP_201_CREATED,
    operation_id="createEnrolChallenge",
)
def create_enrol_challenge(
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
) -> dict[str, Any]:
    """Issue a single-use 32-byte random challenge for key attestation, expiring in 5 minutes."""
    now = utc_now(rt)
    raw_nonce = secrets.token_bytes(32)
    nonce_b64 = base64.b64encode(raw_nonce).decode("ascii")
    expires_at = now + timedelta(minutes=5)

    with unit_of_work(rt.sessions) as s:
        ch = EnrolmentChallenge(
            challenge_id=new_id("ch"),
            approver_email=user.email,
            nonce=nonce_b64,
            used=False,
            created_at=now,
            expires_at=expires_at,
        )
        s.add(ch)

    return {
        "nonce": nonce_b64,
        "challenge_b64": nonce_b64,
        "expires_at": ist(expires_at),
    }


@router.post(
    "/devices/enrol",
    status_code=status.HTTP_201_CREATED,
    operation_id="enrolDevice",
)
def enrol_device(
    body: EnrolDeviceIn,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
) -> dict[str, Any]:
    """Verify key attestation chain, consume the challenge, and enrol the approver phone."""
    now = utc_now(rt)
    target_nonce = body.nonce or body.challenge_b64

    with unit_of_work(rt.sessions) as s:
        query = select(EnrolmentChallenge).where(
            EnrolmentChallenge.approver_email == user.email,
            EnrolmentChallenge.used.is_(False),
        )
        if target_nonce:
            query = query.where(EnrolmentChallenge.nonce == target_nonce)
        else:
            query = query.order_by(EnrolmentChallenge.created_at.desc())

        challenge = s.scalar(query)
        if challenge is None:
            raise ProblemException(
                422,
                "Enrolment challenge invalid",
                "No valid unconsumed enrolment challenge found for approver.",
                type_="https://pramaan.example/problems/challenge-expired",
            )
        if aware(challenge.expires_at) <= now:
            challenge.used = True
            raise ProblemException(
                422,
                "Enrolment challenge expired",
                "The enrolment challenge has expired.",
                type_="https://pramaan.example/problems/challenge-expired",
            )

        challenge.used = True
        try:
            expected_challenge_bytes = base64.b64decode(challenge.nonce)
        except Exception as exc:
            raise ProblemException(
                422, "Malformed challenge", f"Failed decoding challenge: {exc}"
            ) from exc

        # Decode chain DER
        chain_der: list[bytes] = []
        for i, c in enumerate(body.chain_b64):
            try:
                chain_der.append(base64.b64decode(c))
            except Exception as exc:
                raise ProblemException(
                    422,
                    "Invalid certificate chain",
                    f"Failed decoding certificate at index {i}: {exc}",
                    type_="https://pramaan.example/problems/invalid-certificate",
                ) from exc

        # Verify attestation
        revocation = RevocationList(entries={})
        try:
            result = verify_attestation(
                chain_der=chain_der,
                expected_challenge=expected_challenge_bytes,
                settings=rt.settings,
                revocation=revocation,
                now=now,
            )
        except AttestationError as exc:
            raise ProblemException(
                422,
                "This phone cannot be used",
                exc.detail or str(exc),
                type_=f"https://pramaan.example/problems/{exc.code.replace('_', '-')}",
            ) from exc

        # Extract leaf public key PEM
        pubkey = serialization.load_der_public_key(result.public_key_spki_der)
        pubkey_pem = pubkey.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        sec_level = result.security_level
        if sec_level == "STRONGBOX":
            key_sec_level = "StrongBox"
        elif sec_level == "TEE":
            key_sec_level = "TrustedEnvironment"
        else:
            key_sec_level = "Software"

        patch_year = result.os_patch_level // 100
        patch_month = result.os_patch_level % 100
        patch_level_str = f"{patch_year:04d}-{patch_month:02d}-01"

        # Check existing device or generate new
        device = s.scalar(
            select(Device).where(Device.approver_email == user.email, Device.revoked.is_(False))
        )
        if device is None:
            device_id = new_id("dv")
            device = Device(
                device_id=device_id,
                approver_email=user.email,
                phone_model=body.phone_model or "Android Phone",
                public_key_pem=pubkey_pem,
                key_security_level=key_sec_level,
                patch_level=patch_level_str,
                fcm_token=body.fcm_token,
                revoked=False,
                enrolled_at=now,
            )
            s.add(device)
        else:
            device_id = device.device_id
            device.public_key_pem = pubkey_pem
            device.key_security_level = key_sec_level
            device.patch_level = patch_level_str
            if body.phone_model:
                device.phone_model = body.phone_model
            if body.fcm_token:
                device.fcm_token = body.fcm_token
            device.enrolled_at = now

    # Write to Firestore read model
    try:
        rt.read_model.set_document(
            "devices",
            device_id,
            {
                "deviceId": device_id,
                "approver": user.email,
                "phoneModel": body.phone_model or "Android Phone",
                "keySecurityLevel": key_sec_level,
                "patchLevel": patch_level_str,
                "lastIntegrityVerdict": None,
                "revoked": False,
                "enrolledAt": now,
            },
        )
    except Exception:
        pass

    # Publish device.enrolled event
    rt.event_bus.publish(
        topic="device-enrolled",
        event_type="device.enrolled",
        company_id=rt.settings.COMPANY_ID,
        intent_id=None,
        actor={"type": "human", "id": user.email},
        data={
            "device_id": device_id,
            "approver": user.email,
            "phone_model": body.phone_model or "Android Phone",
            "key_security_level": key_sec_level,
            "patch_level": patch_level_str,
            "attestation_root": "google_hardware",
        },
    )

    return {
        "device_id": device_id,
        "approver": user.email,
        "phone_model": body.phone_model or "Android Phone",
        "key_security_level": key_sec_level,
        "patch_level": patch_level_str,
        "last_integrity_verdict": None,
        "revoked": False,
        "enrolled_at": ist(now),
    }


@router.get("/devices", operation_id="listDevices")
def list_devices(
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("finance", "clerk", "approver")),
) -> dict[str, Any]:
    """List enrolled phones for the console and approver."""
    with unit_of_work(rt.sessions) as s:
        devices = s.scalars(select(Device).order_by(Device.enrolled_at.desc())).all()
        return {
            "devices": [
                {
                    "device_id": d.device_id,
                    "approver": d.approver_email,
                    "phone_model": d.phone_model,
                    "key_security_level": d.key_security_level,
                    "patch_level": d.patch_level,
                    "last_integrity_verdict": None,
                    "revoked": d.revoked,
                    "enrolled_at": ist(d.enrolled_at),
                }
                for d in devices
            ]
        }
