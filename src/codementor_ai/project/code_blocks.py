"""Reading code out of agent answers (Markdown with fenced code blocks)."""

from __future__ import annotations

import re
from typing import Dict

from .files import validate_path


_FIRST_BLOCK = re.compile(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```", re.DOTALL)
_FENCE = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)
_FILE_LABEL = re.compile(r"File:\**\s*`?([A-Za-z0-9_./ -]+?)`?\s*\**\s*$")


def extract_code_block(text: str) -> str:
    """First fenced code block in an agent answer, or "" when the answer contains no code."""
    matches = _FIRST_BLOCK.findall(text or "")
    return matches[0].strip() + "\n" if matches and matches[0].strip() else ""


def extract_files(text: str, default_path: str) -> Dict[str, str]:
    """Files proposed in an agent answer, keyed by project-relative path.

    A fenced code block belongs to the path on the line just above it, written as
    ``File: utils.py`` (bold or back-ticked forms are accepted). The first block without such
    a line belongs to ``default_path``; later unlabeled blocks (usage examples) are ignored.
    Invalid or unsafe paths are skipped.
    """
    files: Dict[str, str] = {}
    default_taken = False
    for match in _FENCE.finditer(text or ""):
        body = match.group(1).strip()
        if not body:
            continue
        lines_before = text[: match.start()].rstrip().split("\n")
        label = _FILE_LABEL.search(lines_before[-1]) if lines_before else None
        if label:
            path = label.group(1).strip()
        elif not default_taken:
            path, default_taken = default_path, True
        else:
            continue
        try:
            path = validate_path(path)
        except ValueError:
            continue
        files.setdefault(path, body + "\n")
    return files
