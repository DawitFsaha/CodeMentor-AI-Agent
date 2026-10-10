"""Line diffs for the review panel."""

from __future__ import annotations

import difflib
import html
from typing import Tuple


def diff_stats(original: str, proposed: str) -> Tuple[int, int]:
    """Number of added and removed lines between two file versions."""
    added = removed = 0
    for line in difflib.unified_diff(original.splitlines(), proposed.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


def diff_html(original: str, proposed: str) -> str:
    """Render a unified diff as escaped HTML lines, colored by CSS classes (no scripts)."""
    lines = list(difflib.unified_diff(original.splitlines(), proposed.splitlines(), lineterm="", n=3))[2:]
    if not lines:
        return '<div class="cm-diff"><div class="cm-diff-line cm-diff-hunk">No changes</div></div>'
    rows = []
    for line in lines:
        if line.startswith("@@"):
            kind = "hunk"
        elif line.startswith("+"):
            kind = "add"
        elif line.startswith("-"):
            kind = "del"
        else:
            kind = "ctx"
        rows.append(f'<div class="cm-diff-line cm-diff-{kind}">{html.escape(line) or "&nbsp;"}</div>')
    return '<div class="cm-diff">' + "".join(rows) + "</div>"
