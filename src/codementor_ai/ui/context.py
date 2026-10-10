"""State and helpers shared by the IDE's event handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Set, Tuple

import gradio as gr

from ..core import CodeMentorWorkflow
from ..project import ProjectStore
from .constants import EDITOR_LANGUAGES
from .helpers import path_value, syntax_problem


class IDEContext:
    """The project store and agent workflow, plus helpers several UI areas need."""

    def __init__(self, workflow: CodeMentorWorkflow, store: ProjectStore) -> None:
        self.workflow = workflow
        self.store = store

    # Paths ----------------------------------------------------------------

    def inside_root(self, path: Path) -> bool:
        resolved = path.resolve()
        return resolved != self.store.root and self.store.root in resolved.parents

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.store.root).as_posix()

    def ancestors(self, path: Path) -> Set[str]:
        """Relative paths of every folder above ``path`` inside the projects root."""
        parts = Path(self.relative(path)).parts[:-1]
        return {"/".join(parts[: index + 1]) for index in range(len(parts))}

    def project_relative(self, selected: str, project_name: str) -> str:
        """Path of the open file inside its project, or "" when there is none."""
        if not selected or not project_name:
            return ""
        try:
            return Path(selected).relative_to(self.store.root / project_name).as_posix()
        except ValueError:
            return ""

    def target_dir(self, focus: str, project_name: str) -> Path:
        """Folder for new items: the selected folder, the selected file's folder, or the project root."""
        if focus:
            path = Path(focus)
            if path.is_dir() and self.inside_root(path):
                return path
            if path.is_file() and self.inside_root(path.parent):
                return path.parent
        projects = self.store.list_projects()
        project = project_name if project_name in projects else (projects[0] if projects else "")
        if not project:
            raise ValueError("Create a project first.")
        return self.store.root / project

    # Files ----------------------------------------------------------------

    def open_file(self, value: Any) -> Tuple[Any, str, str, Dict[str, str], str]:
        """Load a file into the editor: (editor update, path, project, project files, status)."""
        selected = path_value(value)
        path = Path(selected)
        if not path.is_file():
            return gr.update(), "", "", {}, "Select a file to open"
        try:
            project_path = path.relative_to(self.store.root)
            project_name = project_path.parts[0]
            files = self.store.load(project_name)
            relative_path = Path(*project_path.parts[1:]).as_posix()
            editor = gr.update(
                value=path.read_text(encoding="utf-8"),
                label=f"{project_name}/{relative_path}",
                language=EDITOR_LANGUAGES.get(path.suffix.lower()),
            )
            return editor, selected, project_name, files, f"Opened {relative_path}"
        except (OSError, ValueError) as error:
            return gr.update(), "", "", {}, f"Cannot open file: {error}"

    def save_selected(self, selected: str, content: str, project_name: str, files: Dict[str, str]) -> Tuple[Dict[str, str], str]:
        """Autosave the editor contents to the open file."""
        if not selected or not project_name:
            return files, "Open a project file first"
        project_root = self.store.root / project_name
        try:
            relative = Path(selected).relative_to(project_root).as_posix()
            # Write only the edited file so deleted files are never recreated from stale state.
            self.store.save(project_name, {relative: content})
            updated = dict(files or {})
            updated[relative] = content
            return updated, f"Autosaved {relative}"
        except (OSError, ValueError) as error:
            return files, f"Autosave failed: {error}"

    def proposal(self, path: Path, content: str, kind: str) -> Dict[str, Any]:
        """A pending, unsaved change: the agent's content plus the file as it is on disk now."""
        try:
            original = path.read_text(encoding="utf-8") if path.is_file() else ""
        except (OSError, ValueError):
            original = ""
        return {
            "path": str(path),
            "relative": self.relative(path),
            "kind": kind,
            "content": content,
            "original": original,
            "is_new": not path.exists(),
            "problem": syntax_problem(str(path), content),
        }

    # Chat memory ----------------------------------------------------------

    @staticmethod
    def session(project_name: str) -> str:
        """Agent memory is kept per project so each project has its own conversation."""
        return f"project:{project_name}" if project_name else "default"

    def log_chat(self, project_name: str, task: str, answer: str) -> None:
        if project_name:
            self.workflow.memory.add_chat(project_name, "user", task)
            self.workflow.memory.add_chat(project_name, "assistant", answer)
