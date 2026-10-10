"""Run panel: run the open program (or the project's entry file) and its tests."""

from __future__ import annotations

from typing import Dict, Tuple

from ..project import is_runnable_source, run_project
from .context import IDEContext


class RunHandlers:
    def __init__(self, ctx: IDEContext) -> None:
        self.ctx = ctx

    def run_code(self, language: str, selected: str, project_name: str, files: Dict[str, str]) -> Tuple[str, str]:
        # Run the open file when it is a program in this project; otherwise the default entrypoint.
        relative = self.ctx.project_relative(selected, project_name)
        entrypoint = relative if relative and is_runnable_source(relative) else ""
        try:
            output = run_project(files or self.ctx.store.load(project_name), entrypoint=entrypoint, language=language)
        except ValueError as error:
            output = f"Run blocked: {error}"
        return output, f"Ran {project_name}"
