"""Input and output boundaries for model-facing workflow data."""

from __future__ import annotations

import re


MAX_TASK_LENGTH = 12_000
MAX_CODE_LENGTH = 30_000
MAX_LANGUAGE_LENGTH = 100

_SECRET_PATTERNS = (
    re.compile(r"(?i)sk-[a-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
)


def redact_secrets(value: str) -> str:
    """Replace common credential forms before text reaches memory or a model."""
    return _SECRET_PATTERNS[0].sub("[REDACTED]", _SECRET_PATTERNS[1].sub("\\1[REDACTED]", _SECRET_PATTERNS[2].sub("\\1[REDACTED]", value)))


def validate_request(task: str, language: str, code: str) -> None:
    if not task or not task.strip():
        raise ValueError("Task is required.")
    if len(task) > MAX_TASK_LENGTH:
        raise ValueError(f"Task must be {MAX_TASK_LENGTH} characters or fewer.")
    if len(language) > MAX_LANGUAGE_LENGTH:
        raise ValueError(f"Language must be {MAX_LANGUAGE_LENGTH} characters or fewer.")
    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(f"Code must be {MAX_CODE_LENGTH} characters or fewer.")


def sanitize_output(value: str) -> str:
    return redact_secrets(value)