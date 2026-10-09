"""Validated project files and bounded local execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping


MAX_PROJECT_FILES = 50
MAX_FILE_SIZE = 50_000
EXECUTION_TIMEOUT_SECONDS = 10


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
        path = _validate_path(raw_path)
        if not isinstance(content, str):
            raise ValueError(f"File '{path}' must contain text.")
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"File '{path}' exceeds {MAX_FILE_SIZE} characters.")
        validated[path] = content
    return dict(sorted(validated.items()))


def project_json(files: Mapping[str, str]) -> str:
    return json.dumps(dict(sorted(files.items())), indent=2)


def project_tree(files: Mapping[str, str]) -> str:
    lines = ["### PROJECT"]
    for path in sorted(files):
        depth = len(PurePosixPath(path).parts) - 1
        lines.append(f"{'  ' * depth}- `{path}`")
    return "\n".join(lines)


HIDDEN_NAMES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}


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


def run_project(files: Mapping[str, str], entrypoint: str = "", language: str = "") -> str:
    """Run the program, then its pytest suite if it has one, in a temporary copy of the project.

    Both outputs are returned so the user sees what the program prints as well as the
    test results. Each command runs without a shell and has its own timeout.
    """
    validated = parse_project_files(project_json(files))
    entrypoint = _entrypoint(validated, entrypoint, language)
    if entrypoint not in validated:
        raise ValueError(f"Entrypoint '{entrypoint}' is not in the project.")
    commands = [("Program", _command_for(language, entrypoint))]
    if _is_python(language, entrypoint) and any(_is_test_file(path) for path in validated):
        commands.append(("Tests", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]))
    with tempfile.TemporaryDirectory(prefix="codementor-") as directory:
        root = Path(directory)
        for path, content in validated.items():
            target = root.joinpath(*PurePosixPath(path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        sections = [f"=== {title}: {_display(command)} ===\n{_execute(command, root)}" for title, command in commands]
    return "\n\n".join(sections)


def _execute(command: list[str], root: Path) -> str:
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            # No keyboard is attached: input() raises EOFError instead of hanging.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"Timed out after {EXECUTION_TIMEOUT_SECONDS} seconds."
    except FileNotFoundError:
        return f"Could not start '{command[0]}'. Is it installed and on PATH?"
    output = (completed.stdout + completed.stderr).strip()
    return f"Exit code: {completed.returncode}\n{output or '(no output)'}"


def _display(command: list[str]) -> str:
    """Readable command line, e.g. 'python main.py' instead of the interpreter's full path."""
    program = "python" if command[0] == sys.executable else command[0]
    return " ".join([program, *command[1:]])


def _is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _is_python(language: str, entrypoint: str) -> bool:
    return Path(entrypoint).suffix.lower() == ".py" or (
        not Path(entrypoint).suffix and language.lower().strip() in ("python", "py")
    )


def _validate_path(raw_path: object) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("File paths must be non-empty strings.")
    path = PurePosixPath(raw_path.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or str(path) != raw_path.replace("\\", "/"):
        raise ValueError(f"Unsafe project path: {raw_path}")
    return str(path)


def _entrypoint(files: Mapping[str, str], entrypoint: str, language: str) -> str:
    if entrypoint:
        return _validate_path(entrypoint)
    normalized = language.lower().strip()
    suffixes = (".js",) if normalized in ("javascript", "js") else (".py",)
    # Test files are run by pytest, never as the program itself.
    candidates = [
        path for path in files if Path(path).suffix.lower() in suffixes and not _is_test_file(path)
    ]
    for preferred in ("main.py", "index.py", "main.js", "index.js"):
        if preferred in candidates:
            return preferred
    if candidates:
        return min(candidates)
    raise ValueError("No runnable source file exists in the project.")


def _command_for(language: str, entrypoint: str) -> list[str]:
    normalized = language.lower().strip()
    suffix = Path(entrypoint).suffix.lower()
    if suffix == ".py" or (not suffix and normalized in ("python", "py")):
        return [sys.executable, *PurePosixPath(entrypoint).parts]
    if suffix == ".js" or (not suffix and normalized in ("javascript", "js")):
        return ["node", *PurePosixPath(entrypoint).parts]
    raise ValueError("Run currently supports Python (.py) and JavaScript (.js) files.")