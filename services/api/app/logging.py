import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "token",
    "signature",
    "summary_b64",
    "mandate_b64",
    "private_key",
    "secret",
    "secret_key",
    "password",
    "credentials",
}

ACCOUNT_NUMBER_REGEX = re.compile(r"\b\d{9,18}\b")


def mask_account_number(val: str) -> str:
    if len(val) <= 4:
        return val
    return "*" * (len(val) - 4) + val[-4:]


def sanitize_data(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if k.lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            elif "account" in k.lower() and isinstance(v, str) and v.isdigit() and len(v) > 4:
                sanitized[k] = mask_account_number(v)
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str):
        # Mask isolated full bank account numbers
        return ACCOUNT_NUMBER_REGEX.sub(lambda m: mask_account_number(m.group(0)), data)
    return data


class CloudLoggingFormatter(logging.Formatter):
    """Formats log records as JSON lines compatible with Google Cloud Logging."""

    SEVERITY_MAP = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        severity = self.SEVERITY_MAP.get(record.levelname, "DEFAULT")
        raw_msg = record.getMessage()
        masked_msg = ACCOUNT_NUMBER_REGEX.sub(lambda m: mask_account_number(m.group(0)), raw_msg)

        payload: dict[str, Any] = {
            "severity": severity,
            "message": masked_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
        }

        if record.exc_info:
            payload["trace"] = self.formatException(record.exc_info)

        # Include custom extra fields if present
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(sanitize_data(extra))

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("pramaan")
    logger.setLevel(level)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudLoggingFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
