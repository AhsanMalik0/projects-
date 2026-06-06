import re

_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b\+?\d[\d\-\s]{7,15}\d\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
}

_REDACTED = "[REDACTED]"


def redact_pii(text: str) -> str:
    for _label, pattern in _PATTERNS.items():
        text = pattern.sub(_REDACTED, text)
    return text
