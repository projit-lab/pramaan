import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class AuthenticatedUser:
    uid: str
    email: str | None = None
    roles: list[str] = field(default_factory=list)


IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_time() -> str:
    """Returns current ISO 8601 timestamp with +05:30 offset."""
    return datetime.now(IST).isoformat()


def generate_event_id() -> str:
    """Generates an event ID (UUIDv4 formatted)."""
    return f"ev_{uuid.uuid4().hex}"
