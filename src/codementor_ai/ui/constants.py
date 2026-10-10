"""Fixed values used across the IDE."""

from __future__ import annotations

from pathlib import Path


# PNG rather than SVG: Gradio serves SVG files as downloads, so they cannot be used as icons.
TRASH_ICON = str(Path(__file__).resolve().parent.parent / "assets" / "trash.png")

LANGUAGES = ["Python", "JavaScript", "Java"]

# Editor syntax highlighting by file extension.
EDITOR_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    # Gradio 4 has no Java mode; C++ highlighting covers Java's keywords and syntax closely.
    ".java": "cpp",
    ".ts": "typescript",
    ".md": "markdown",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
}

# Two clicks on the same Explorer row within this many seconds count as a double-click.
DOUBLE_CLICK_SECONDS = 0.8
