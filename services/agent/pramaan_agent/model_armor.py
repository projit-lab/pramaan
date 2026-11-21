"""Model Armor integration for Pramaan Agent Service.

Model Armor inspects LLM inputs, prompts, and document text for:
- Prompt injection attacks (e.g. hidden instructions in invoices)
- Jailbreaks
- Malicious redirection instructions

If prompt injection is detected, Model Armor returns a structured finding.
A finding raises the payment tier; it NEVER lowers it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+note\s*:", re.IGNORECASE),
    re.compile(r"this\s+supersedes\s+the\s+printed\s+account", re.IGNORECASE),
    re.compile(r"pay\s+account\s+[0-9]{6,20}", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+prior", re.IGNORECASE),
]


@dataclass(frozen=True)
class ModelArmorFinding:
    category: str
    detail: str
    excerpt: str | None
    found_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "detail": self.detail,
            "excerpt": self.excerpt,
            "found_at": self.found_at,
        }

    def to_firestore_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "detail": self.detail,
            "excerpt": self.excerpt,
            "foundAt": self.found_at,
        }


class ModelArmorScanner:
    """Scans text extracted from documents for prompt injection payloads."""

    def __init__(self, template_id: str = "pramaan-invoice-shield") -> None:
        self.template_id = template_id

    def scan(self, text: str, now: datetime | None = None) -> ModelArmorFinding | None:
        if not text:
            return None
        now_dt = now or datetime.now(IST)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=IST)
        found_at = now_dt.astimezone(IST).isoformat(timespec="seconds")

        for pattern in INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                # Capture the surrounding sentence or full line as the excerpt
                start = max(0, text.rfind("\n", 0, match.start()) + 1)
                end = text.find("\n", match.end())
                if end == -1:
                    end = len(text)
                excerpt = text[start:end].strip()
                if not excerpt:
                    excerpt = match.group(0).strip()

                return ModelArmorFinding(
                    category="prompt_injection",
                    detail="Hidden text in the invoice tries to redirect the payment to another account.",
                    excerpt=excerpt,
                    found_at=found_at,
                )

        return None
