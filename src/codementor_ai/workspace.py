"""Persistent local project workspaces used by the IDE."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Dict, List

from .project import parse_project_files, project_json


class ProjectStore:
    """Store project files under a local directory without allowing path escape."""

    def __init__(self, root: str = "projects") -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> List[str]:
        return sorted(path.name for path in self.root.iterdir() if path.is_dir())

    def create(self, name: str) -> str:
        project_name = _safe_project_name(name)
        directory = self.root / project_name
        directory.mkdir(parents=True, exist_ok=True)
        main = directory / "main.py"
        if not main.exists():
            main.write_text("print('Hello from CodeMentor')\n", encoding="utf-8")
        return project_name

    def load(self, name: str) -> Dict[str, str]:
        project_name = _safe_project_name(name)
        directory = self.root / project_name
        if not directory.is_dir():
            raise ValueError(f"Project '{project_name}' does not exist.")
        files = {
            path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
            for path in directory.rglob("*")
            if path.is_file()
        }
        return parse_project_files(project_json(files or {"main.py": ""}))

    def save(self, name: str, files: Dict[str, str]) -> None:
        project_name = _safe_project_name(name)
        directory = self.root / project_name
        directory.mkdir(parents=True, exist_ok=True)
        validated = parse_project_files(project_json(files))
        for path, content in validated.items():
            target = directory.joinpath(*PurePosixPath(path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")


def _safe_project_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    if not name:
        raise ValueError("Project name is required.")
    return name[:64]