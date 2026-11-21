"""Screening an invoice's text for prompt injection before anything acts on it.

`ModelArmorScreen` calls Google Cloud Model Armor's sanitizeUserPrompt against
a template (prompt injection and jailbreak, malicious URLs, sensitive data). It
fails closed: if Model Armor cannot be reached, the screen reports a finding so
the payment is held for a person rather than waved through.

`RegexScreen` is the offline stand-in for tests and runs without Model Armor.
It is a handful of regular expressions, it is labelled as such everywhere it
shows up, and it is never called Model Armor.

A finding can only make a payment stricter (raise the tier, force individual
review). Nothing here can approve or release a payment.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("pramaan")


@dataclass
class Finding:
    category: str  # prompt_injection | jailbreak | malicious_url | sensitive_data
    detail: str
    excerpt: str | None
    screened_by: str


class Screen(Protocol):
    name: str

    def screen(self, text: str) -> Finding | None: ...


INJECTION = re.compile(
    r"(ignore (?:all |any )?(?:previous|prior|above) instructions"
    r"|disregard (?:the )?(?:previous|above)"
    r"|system (?:note|prompt|message)\s*:"
    r"|this supersedes"
    r"|you are now"
    r"|pay (?:to )?account\s*(?:no\.?|number)?\s*[:#]?\s*\d{6,})",
    re.IGNORECASE,
)
URL = re.compile(r"https?://[^\s]+", re.IGNORECASE)
PRESSURE = re.compile(
    r"\b(urgent(?:ly)?|immediately|within the hour|today itself|before (?:eod|end of day)"
    r"|do not (?:call|verify)|keep this confidential|don't tell)\b",
    re.IGNORECASE,
)


def excerpt_around(text: str, start: int, end: int, pad: int = 60) -> str:
    flat = text
    a, b = max(0, start - pad), min(len(flat), end + pad)
    return " ".join(flat[a:b].split())


def pressure_language(text: str) -> bool:
    """A rule, not a model: urgency or secrecy wording in the document."""
    return bool(PRESSURE.search(text))


class RegexScreen:
    name = "regex screen (offline stand-in, not Model Armor)"

    def screen(self, text: str) -> Finding | None:
        m = INJECTION.search(text)
        if m:
            return Finding(
                "prompt_injection",
                "Text in the document tries to give instructions to an AI agent.",
                excerpt_around(text, m.start(), m.end()),
                self.name,
            )
        return None


CATEGORY_BY_FILTER = {
    "pi_and_jailbreak": "prompt_injection",
    "malicious_uris": "malicious_url",
    "sdp": "sensitive_data",
    "rai": "jailbreak",
    "csam": "jailbreak",
}


class ModelArmorScreen:
    name = "Google Cloud Model Armor"

    def __init__(self, project: str, location: str, template: str):
        self.url = (
            f"https://modelarmor.{location}.rep.googleapis.com/v1/projects/{project}"
            f"/locations/{location}/templates/{template}:sanitizeUserPrompt"
        )

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        r = AuthorizedSession(creds).post(self.url, json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def screen(self, text: str) -> Finding | None:
        try:
            data = self._post({"userPromptData": {"text": text[:50000]}})
        except Exception as e:
            logger.warning(f"Model Armor unreachable, failing closed: {type(e).__name__}: {e}")
            return Finding(
                "prompt_injection",
                "Model Armor could not screen this document, so it is held for a person.",
                None,
                self.name,
            )
        result = data.get("sanitizationResult", {})
        if result.get("filterMatchState") != "MATCH_FOUND":
            return None
        hits = [
            name for name, res in (result.get("filterResults") or {}).items() if _matched(res)
        ] or ["pi_and_jailbreak"]
        category = CATEGORY_BY_FILTER.get(hits[0], "prompt_injection")
        m = INJECTION.search(text) or URL.search(text)
        return Finding(
            category,
            f"Model Armor flagged this document ({', '.join(hits)}).",
            excerpt_around(text, m.start(), m.end()) if m else None,
            self.name,
        )


def _matched(res: Any) -> bool:
    """True if any nested matchState in a filter result is MATCH_FOUND."""
    if isinstance(res, dict):
        if res.get("matchState") == "MATCH_FOUND":
            return True
        return any(_matched(v) for v in res.values())
    if isinstance(res, list):
        return any(_matched(v) for v in res)
    return False


def get_screen(settings: Any) -> Screen:
    if settings.USE_REAL_AI:
        return ModelArmorScreen(
            settings.GCP_PROJECT, settings.MODEL_ARMOR_LOCATION, settings.MODEL_ARMOR_TEMPLATE
        )
    return RegexScreen()
