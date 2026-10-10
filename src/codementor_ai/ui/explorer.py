"""Explorer sidebar: the project tree and its actions (open, create, rename, delete)."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Set

import gradio as gr

from ..project import STARTER_FILES, TreeEntry, explorer_entries
from .constants import DOUBLE_CLICK_SECONDS, TRASH_ICON
from .context import IDEContext
from .helpers import name_problem, without_folder


class ExplorerHandlers:
    """Event handlers for the Explorer. Each returns values for the outputs it is wired to."""

    def __init__(self, ctx: IDEContext) -> None:
        self.ctx = ctx

    def click_entry(self, entry: TreeEntry):
        """Opening a file loads it into the editor; clicking a folder toggles and selects it."""
        ctx = self.ctx

        def toggle(expanded: Set[str]) -> Set[str]:
            if entry.relative in expanded:
                return without_folder(expanded, entry.relative)
            return expanded | {entry.relative}

        def handler(
            expanded: Set[str],
            selected: str,
            project_name: str,
            files: Dict[str, str],
            last_click: Dict[str, Any],
        ):
            expanded = set(expanded)
            now = time.monotonic()
            # Gradio buttons have no double-click event: two clicks on the same row in quick
            # succession (timed on the server) switch the row into rename mode.
            last_click = last_click or {}
            if last_click.get("item") == entry.path and now - last_click.get("at", 0.0) <= DOUBLE_CLICK_SECONDS:
                if entry.is_dir:
                    expanded = toggle(expanded)  # undo the open/close from the first click
                return (
                    expanded, entry.path, "", gr.update(), selected, project_name, files,
                    f"Renaming `{entry.relative}`: type the new name and press Enter",
                    {"item": "", "at": 0.0}, entry.path,
                )
            click = {"item": entry.path, "at": now}
            if entry.is_dir:
                return (
                    toggle(expanded), entry.path, "", gr.update(), selected, project_name, files,
                    f"Selected folder {entry.relative}", click, "",
                )
            editor, opened, opened_project, opened_files, message = ctx.open_file(entry.path)
            if not opened:
                return expanded, "", "", gr.update(), selected, project_name, files, message, click, ""
            return expanded, entry.path, "", editor, opened, opened_project, opened_files, message, click, ""

        return handler

    def rename_entry(self, entry: TreeEntry):
        """Rename a file or folder in place, keeping open files, proposals, and chat in step."""
        ctx = self.ctx

        def handler(
            new_name: str,
            selected: str,
            focus: str,
            project_name: str,
            files: Dict[str, str],
            expanded: Set[str],
            version: int,
            proposals: List[Dict[str, Any]],
        ):
            old_path = Path(entry.path)
            name = (new_name or "").strip()
            unchanged = (
                entry.path, selected, focus, project_name, files, expanded, version,
                gr.update(), proposals,
            )
            if name == old_path.name:
                return ("",) + unchanged[1:] + ("Rename cancelled",)
            is_project = "/" not in entry.relative
            problem = name_problem(name, is_project)
            # Only build the path once the name is known to be a single valid component.
            new_path = old_path if problem else old_path.with_name(name)
            if not problem and new_path.exists():
                problem = f"`{name}` already exists here"
            if not problem and not ctx.inside_root(new_path):
                problem = "the new name must stay inside the projects folder"
            if problem:
                return unchanged + (f"Cannot rename: {problem}",)
            try:
                old_path.rename(new_path)
            except OSError as error:
                return unchanged + (f"Cannot rename: {error}",)

            old_text, new_text = str(old_path), str(new_path)

            def moved(path: str) -> str:
                if path == old_text or path.startswith(old_text + os.sep):
                    return new_text + path[len(old_text):]
                return path

            old_relative = entry.relative
            new_relative = ctx.relative(new_path)
            expanded = {
                new_relative + path[len(old_relative):]
                if path == old_relative or path.startswith(old_relative + "/")
                else path
                for path in expanded
            }
            proposals = [
                dict(p, path=moved(p["path"]), relative=ctx.relative(Path(moved(p["path"]))))
                for p in proposals
            ]
            if is_project:
                ctx.workflow.memory.rename_project(old_path.name, name)
                if project_name == old_path.name:
                    project_name = name
            new_selected = moved(selected)
            editor = gr.update()
            if new_selected != selected and new_selected:
                editor = gr.update(label=ctx.relative(Path(new_selected)))
            if project_name:
                try:
                    files = ctx.store.load(project_name)
                except ValueError:
                    pass
            return (
                "", new_selected, moved(focus), project_name, files, expanded, version + 1,
                editor, proposals, f"Renamed `{old_relative}` to `{new_relative}`",
            )

        return handler

    @staticmethod
    def cancel_rename():
        return "", "Rename cancelled"

    def delete_entry(self, entry: TreeEntry):
        """First click asks for confirmation; the second click deletes the file or folder."""
        ctx = self.ctx

        def handler(pending: str, focus: str, selected: str, project_name: str, files: Dict[str, str], expanded: Set[str], version: int):
            if pending != entry.path:
                return entry.path, focus, expanded, version, gr.update(), selected, project_name, files, f"Click **Delete?** to remove `{entry.relative}`"
            target = Path(entry.path)
            try:
                if not ctx.inside_root(target):
                    raise ValueError("Only items inside the projects folder can be deleted.")
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            except (OSError, ValueError) as error:
                return "", focus, expanded, version, gr.update(), selected, project_name, files, f"Delete failed: {error}"

            def removed(path: str) -> bool:
                return bool(path) and (path == entry.path or path.startswith(entry.path + os.sep))

            editor = gr.update()
            if removed(selected):
                selected = ""
                editor = gr.update(value="", label="No file open")
            if project_name not in ctx.store.list_projects():
                project_name, files = "", {}
            elif project_name:
                try:
                    files = ctx.store.load(project_name)
                except ValueError:
                    files = {}
            focus = "" if removed(focus) else focus
            return "", focus, without_folder(set(expanded), entry.relative), version + 1, editor, selected, project_name, files, f"Deleted `{entry.relative}`"

        return handler

    def create_project(self, expanded: Set[str], version: int, language: str):
        """New project with a starter file in the selected language, opened in the editor."""
        store = self.ctx.store
        index = len(store.list_projects()) + 1
        name = f"project-{index}"
        while (store.root / name).exists():
            index += 1
            name = f"project-{index}"
        store.create(name, language)
        main = str(store.root / name / STARTER_FILES.get(language, STARTER_FILES["Python"])[0])
        editor, _, _, files, _ = self.ctx.open_file(main)
        return set(expanded) | {name}, main, "", version + 1, editor, main, name, files, f"Created {name}"

    def create_file(self, focus: str, project_name: str, files: Dict[str, str], selected: str, expanded: Set[str], version: int):
        """New empty file in the selected folder (or the project root), opened in the editor."""
        ctx = self.ctx
        try:
            directory = ctx.target_dir(focus, project_name)
            index = 1
            while (directory / f"untitled_{index}.py").exists():
                index += 1
            new_file = directory / f"untitled_{index}.py"
            new_file.write_text("", encoding="utf-8")
        except (OSError, ValueError) as error:
            return expanded, focus, "", version, gr.update(), selected, project_name, files, f"Cannot create file: {error}"
        expanded = set(expanded) | ctx.ancestors(new_file)
        editor, opened, opened_project, opened_files, _ = ctx.open_file(str(new_file))
        if not opened:
            return expanded, str(new_file), "", version + 1, gr.update(), selected, project_name, files, f"Created {ctx.relative(new_file)}"
        return expanded, str(new_file), "", version + 1, editor, opened, opened_project, opened_files, f"Created {ctx.relative(new_file)}"

    def create_folder(self, focus: str, project_name: str, expanded: Set[str], version: int):
        """New folder in the selected folder (or the project root); it becomes the selection."""
        ctx = self.ctx
        try:
            directory = ctx.target_dir(focus, project_name)
            index = 1
            while (directory / f"folder_{index}").exists():
                index += 1
            new_folder = directory / f"folder_{index}"
            new_folder.mkdir()
        except (OSError, ValueError) as error:
            return expanded, focus, "", version, f"Cannot create folder: {error}"
        # Select the new folder so the next new file goes inside it.
        expanded = set(expanded) | ctx.ancestors(new_folder) | {ctx.relative(new_folder)}
        return expanded, str(new_folder), "", version + 1, f"Created {ctx.relative(new_folder)}"

    def ensure_project(self, project_name: str, expanded: Set[str], selected: str):
        """On page load, fall back to an existing project if the default was renamed or deleted."""
        store = self.ctx.store
        projects = store.list_projects()
        if project_name in projects or not projects:
            return project_name, expanded, selected, gr.update(), gr.update()
        project_name = projects[0]
        expanded = set(expanded) | {project_name}
        main = store.root / project_name / "main.py"
        if not main.is_file():
            return project_name, expanded, "", gr.update(value="", label="No file open"), store.load(project_name)
        editor, opened, _, files, _ = self.ctx.open_file(str(main))
        return project_name, expanded, opened, editor, files


def build_tree(handlers: ExplorerHandlers, ui: SimpleNamespace) -> None:
    """Declare the Explorer tree. Call inside the Explorer column of the layout.

    ``ui`` holds the app's components and states; components created later in the layout
    (the editor, the status line) are looked up when the tree renders, after the layout exists.
    """
    ctx = handlers.ctx

    @gr.render(inputs=[ui.expanded_state, ui.focus_state, ui.pending_delete_state, ui.project_state, ui.tree_version, ui.renaming_state])
    def render_tree(expanded, focus, pending, project_name, _version, renaming):
        try:
            hint = ctx.relative(ctx.target_dir(focus, project_name))
        except ValueError:
            hint = "no project"
        gr.Markdown(f"New items go in `{hint}/`", elem_classes="cm-target")
        entries = explorer_entries(str(ctx.store.root), expanded)
        if not entries:
            gr.Markdown("No projects yet. Click ＋ to create one.")
        for entry in entries:
            row_classes = ["cm-tree-row"] + (["cm-active"] if entry.path == focus else [])
            if entry.path == renaming:
                _rename_row(handlers, ui, entry, row_classes)
            else:
                _entry_row(handlers, ui, entry, row_classes, confirming=pending == entry.path)


def _rename_row(handlers: ExplorerHandlers, ui: SimpleNamespace, entry: TreeEntry, row_classes: List[str]) -> None:
    """A row being renamed: a text box with save and cancel buttons."""
    with gr.Row(elem_classes=row_classes + ["cm-renaming"]):
        name_box = gr.Textbox(
            value=Path(entry.path).name,
            show_label=False,
            container=False,
            autofocus=True,
            max_lines=1,
            scale=1,
            min_width=0,
            elem_classes="cm-rename-box",
        )
        save_button = gr.Button("✓", size="sm", scale=0, min_width=0, elem_classes="cm-rename-save")
        cancel_button = gr.Button("✕", size="sm", scale=0, min_width=0, elem_classes="cm-rename-cancel")
    rename_inputs = [name_box, ui.selected_state, ui.focus_state, ui.project_state, ui.files_state, ui.expanded_state, ui.tree_version, ui.proposals_state]
    rename_outputs = [ui.renaming_state, ui.selected_state, ui.focus_state, ui.project_state, ui.files_state, ui.expanded_state, ui.tree_version, ui.selected_code, ui.proposals_state, ui.status]
    for trigger in (name_box.submit, save_button.click):
        trigger(handlers.rename_entry(entry), inputs=rename_inputs, outputs=rename_outputs, api_name=False)
    cancel_button.click(handlers.cancel_rename, outputs=[ui.renaming_state, ui.status], api_name=False)


def _entry_row(handlers: ExplorerHandlers, ui: SimpleNamespace, entry: TreeEntry, row_classes: List[str], confirming: bool) -> None:
    """A normal row: the name (click to open, double-click to rename) and a delete button."""
    with gr.Row(elem_classes=row_classes):
        name_button = gr.Button(entry.label, size="sm", scale=1, min_width=0, elem_classes="cm-tree-name")
        delete_button = gr.Button(
            "Delete?" if confirming else "",
            icon=None if confirming else TRASH_ICON,
            size="sm",
            scale=0,
            min_width=0,
            elem_classes=["cm-tree-delete"] + (["cm-confirm"] if confirming else []),
        )
    name_button.click(
        handlers.click_entry(entry),
        inputs=[ui.expanded_state, ui.selected_state, ui.project_state, ui.files_state, ui.last_click_state],
        outputs=[ui.expanded_state, ui.focus_state, ui.pending_delete_state, ui.selected_code, ui.selected_state, ui.project_state, ui.files_state, ui.status, ui.last_click_state, ui.renaming_state],
        api_name=False,
        # Queue quick second clicks instead of dropping them, so double-clicks register.
        trigger_mode="multiple",
    )
    delete_button.click(
        handlers.delete_entry(entry),
        inputs=[ui.pending_delete_state, ui.focus_state, ui.selected_state, ui.project_state, ui.files_state, ui.expanded_state, ui.tree_version],
        outputs=[ui.pending_delete_state, ui.focus_state, ui.expanded_state, ui.tree_version, ui.selected_code, ui.selected_state, ui.project_state, ui.files_state, ui.status],
        api_name=False,
    )
