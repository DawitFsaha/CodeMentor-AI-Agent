"""Project file maps: path validation, size limits, and the Explorer listing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping


MAX_PROJECT_FILES = 50
MAX_FILE_SIZE = 50_000
HIDDEN_NAMES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}


def validate_path(raw_path: object) -> str:
    """A safe project-relative POSIX path, or ValueError for absolute or escaping paths."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("File paths must be non-empty strings.")
    path = PurePosixPath(raw_path.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or str(path) != raw_path.replace("\\", "/"):
        raise ValueError(f"Unsafe project path: {raw_path}")
    return str(path)


def parse_project_files(value: str) -> Dict[str, str]:
    """Parse the UI's JSON file map and reject unsafe or oversized projects."""
    try:
        files = json.loads(value or "{}")
    except json.JSONDecodeError as error:
        raise ValueError(f"Project files must be valid JSON: {error.msg}.") from error
    if not isinstance(files, dict):
        raise ValueError("Project files must be a JSON object mapping paths to text.")
    if not files:
        raise ValueError("Add at least one project file.")
    if len(files) > MAX_PROJECT_FILES:
        raise ValueError(f"Projects may contain at most {MAX_PROJECT_FILES} files.")

    validated: Dict[str, str] = {}
    for raw_path, content in files.items():
        path = validate_path(raw_path)
        if not isinstance(content, str):
            raise ValueError(f"File '{path}' must contain text.")
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"File '{path}' exceeds {MAX_FILE_SIZE} characters.")
        validated[path] = content
    return dict(sorted(validated.items()))


def project_json(files: Mapping[str, str]) -> str:
    return json.dumps(dict(sorted(files.items())), indent=2)


def project_tree(files: Mapping[str, str]) -> str:
    """Markdown outline of a project's files, used in agent prompts."""
    lines = ["### PROJECT"]
    for path in sorted(files):
        depth = len(PurePosixPath(path).parts) - 1
        lines.append(f"{'  ' * depth}- `{path}`")
    return "\n".join(lines)


def module_name(path: str) -> str:
    """Import name of a project file: ``src/app.py`` -> ``src.app``."""
    return ".".join(PurePosixPath(path).with_suffix("").parts)


@dataclass(frozen=True)
class TreeEntry:
    """One visible row of the Explorer sidebar."""

    path: str
    relative: str
    label: str
    is_dir: bool
    depth: int


def explorer_entries(root_dir: str, expanded: Iterable[str] = ()) -> List[TreeEntry]:
    """List the visible directory tree, folders first, as Explorer rows.

    ``path`` is absolute and ``relative`` is relative to ``root_dir``. Only folders
    whose relative path is in ``expanded`` show their children.
    """
    root = Path(root_dir)
    open_folders = set(expanded)
    rows: List[TreeEntry] = []

    def walk(directory: Path, depth: int) -> None:
        entries = sorted(
            (entry for entry in directory.iterdir() if entry.name not in HIDDEN_NAMES),
            key=lambda entry: (entry.is_file(), entry.name.lower()),
        )
        indent = "    " * depth
        for entry in entries:
            relative = entry.relative_to(root).as_posix()
            if entry.is_dir():
                is_open = relative in open_folders
                marker = "▾ 📂" if is_open else "▸ 📁"
                rows.append(TreeEntry(str(entry), relative, f"{indent}{marker} {entry.name}", True, depth))
                if is_open:
                    walk(entry, depth + 1)
            else:
                label = f"{indent}   📄 {entry.name}"
                rows.append(TreeEntry(str(entry), relative, label, False, depth))

    if root.is_dir():
        walk(root, 0)
    return rows
