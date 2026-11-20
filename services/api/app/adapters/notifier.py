"""Approver push: Firebase Cloud Messaging data messages (M2, Danish).

The message only says an approval is waiting and which one. It never carries the
payee, the amount or anything to sign: the app fetches the approval over the API,
so a notification can never be the approval itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings

logger = logging.getLogger("pramaan")


@dataclass(frozen=True)
class PushResult:
    device_id: str
    ok: bool
    error: str | None = None


class Notifier(Protocol):
    def send_approval_waiting(
        self, device_id: str, fcm_token: str, approval_id: str, intent_id: str
    ) -> PushResult: ...


def approval_waiting_data(approval_id: str, intent_id: str) -> dict[str, str]:
    return {"type": "approval_waiting", "approval_id": approval_id, "intent_id": intent_id}


class InMemoryNotifier:
    """ENV=local and tests: records what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send_approval_waiting(
        self, device_id: str, fcm_token: str, approval_id: str, intent_id: str
    ) -> PushResult:
        self.sent.append({"device_id": device_id, **approval_waiting_data(approval_id, intent_id)})
        logger.info(f"Push (in-memory) approval_waiting {approval_id} to device {device_id}")
        return PushResult(device_id, True)


class FcmNotifier:
    """Cloud: a high-priority FCM data message, so it wakes the approver's phone."""

    def __init__(self, settings: Settings) -> None:
        import firebase_admin

        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(options={"projectId": settings.GCP_PROJECT})

    def send_approval_waiting(
        self, device_id: str, fcm_token: str, approval_id: str, intent_id: str
    ) -> PushResult:
        from firebase_admin import messaging

        message = messaging.Message(
            token=fcm_token,
            data=approval_waiting_data(approval_id, intent_id),
            android=messaging.AndroidConfig(priority="high", ttl=3600),
        )
        try:
            messaging.send(message)
            return PushResult(device_id, True)
        except Exception as e:  # one bad token must not stop the others
            logger.warning(f"FCM send failed for device {device_id}: {type(e).__name__}")
            return PushResult(device_id, False, type(e).__name__)


def get_notifier(settings: Settings) -> Notifier:
    if settings.ENV == "local":
        return InMemoryNotifier()
    return FcmNotifier(settings)
