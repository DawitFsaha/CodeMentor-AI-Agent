"""Small pure helpers for the IDE (no Gradio, no file system writes)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Set

from ..project import extract_code_block, javascript_syntax_problem, python_syntax_problem


_FORBIDDEN_NAME_CHARS = set(r'/\:*?"<>|')


def generated_source(value: str) -> str:
    """First fenced code block in an agent answer, or "" when the answer contains no code."""
    return extract_code_block(value)


def syntax_problem(path: str, content: str) -> str:
    """Why proposed .py or .js content does not parse, or "" when it does (nothing is run)."""
    if path.endswith(".js"):
        return javascript_syntax_problem(content)
    if path.endswith(".py"):
        return python_syntax_problem(content)
    return ""


def name_problem(name: str, is_project: bool) -> str:
    """Why ``name`` cannot be used for a file or folder, or "" when it is fine."""
    if not name:
        return "the name is empty"
    if name in (".", "..") or any(char in _FORBIDDEN_NAME_CHARS for char in name):
        return r'names cannot be "." or ".." or contain / \ : * ? " < > |'
    if len(name) > 100:
        return "the name is longer than 100 characters"
    if is_project and not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        return "project names may only use letters, numbers, - and _"
    return ""


def same_text(first: str, second: Optional[str]) -> bool:
    """Equal apart from line endings and trailing newlines (the editor drops the final newline)."""
    if second is None:
        return False
    return first.replace("\r\n", "\n").rstrip("\n") == second.replace("\r\n", "\n").rstrip("\n")


def disk_text(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def path_value(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def without_folder(expanded: Set[str], relative: str) -> Set[str]:
    """Drop a folder and everything below it from the expanded set."""
    return {path for path in expanded if path != relative and not path.startswith(relative + "/")}
