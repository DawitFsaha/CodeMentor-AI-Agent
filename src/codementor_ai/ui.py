"""Gradio mini-IDE with a native filesystem Explorer."""

from __future__ import annotations

import difflib
import html
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .memory import SQLiteMemory
from .project import TreeEntry, explorer_entries, run_project
from .workflow import CodeMentorRequest, CodeMentorWorkflow
from .workspace import ProjectStore


# PNG rather than SVG: Gradio serves SVG files as downloads, so they cannot be used as icons.
TRASH_ICON = str(Path(__file__).parent / "assets" / "trash.png")
DEFAULT_FILES = {"main.py": "print('Hello from CodeMentor')\n"}
LANGUAGES = ["Python", "JavaScript"]
EDITOR_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".md": "markdown",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
}


def _generated_source(value: str) -> str:
    """First fenced code block in an agent answer, or "" when the answer contains no code."""
    matches = re.findall(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```", value, re.DOTALL)
    return matches[0].strip() + "\n" if matches and matches[0].strip() else ""


def _same_text(first: str, second: Optional[str]) -> bool:
    """Equal apart from line endings and trailing newlines (the editor drops the final newline)."""
    if second is None:
        return False
    return first.replace("\r\n", "\n").rstrip("\n") == second.replace("\r\n", "\n").rstrip("\n")


def _disk_text(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


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


def _path_value(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _without(expanded: Set[str], relative: str) -> Set[str]:
    """Drop a folder and everything below it from the expanded set."""
    return {path for path in expanded if path != relative and not path.startswith(relative + "/")}


def create_app(workflow: Optional[CodeMentorWorkflow] = None) -> Any:
    """Build the IDE around the projects directory and native file tree."""
    import gradio as gr

    active_workflow = workflow or CodeMentorWorkflow()
    store = ProjectStore()
    if not store.list_projects():
        store.create("starter")
    initial_project = store.list_projects()[0]
    initial_files = store.load(initial_project)

    def _inside_root(path: Path) -> bool:
        resolved = path.resolve()
        return resolved != store.root and store.root in resolved.parents

    def _relative(path: Path) -> str:
        return path.resolve().relative_to(store.root).as_posix()

    def _ancestors(path: Path) -> Set[str]:
        """Relative paths of every folder above ``path`` inside the projects root."""
        parts = Path(_relative(path)).parts[:-1]
        return {"/".join(parts[: index + 1]) for index in range(len(parts))}

    def target_dir(focus: str, project_name: str) -> Path:
        """Folder for new items: the selected folder, the selected file's folder, or the project root."""
        if focus:
            path = Path(focus)
            if path.is_dir() and _inside_root(path):
                return path
            if path.is_file() and _inside_root(path.parent):
                return path.parent
        projects = store.list_projects()
        project = project_name if project_name in projects else (projects[0] if projects else "")
        if not project:
            raise ValueError("Create a project first.")
        return store.root / project

    def open_file(value: Any) -> Tuple[Any, str, str, Dict[str, str], str]:
        selected = _path_value(value)
        path = Path(selected)
        if not path.is_file():
            return gr.update(), "", "", {}, "Select a file to open"
        try:
            project_path = path.relative_to(store.root)
            project_name = project_path.parts[0]
            files = store.load(project_name)
            relative_path = Path(*project_path.parts[1:]).as_posix()
            editor = gr.update(
                value=path.read_text(encoding="utf-8"),
                label=f"{project_name}/{relative_path}",
                language=EDITOR_LANGUAGES.get(path.suffix.lower()),
            )
            return editor, selected, project_name, files, f"Opened {relative_path}"
        except (OSError, ValueError) as error:
            return gr.update(), "", "", {}, f"Cannot open file: {error}"

    def click_entry(entry: TreeEntry):
        """Opening a file loads it into the editor; clicking a folder toggles and selects it."""

        def handler(expanded: Set[str], selected: str, project_name: str, files: Dict[str, str]):
            expanded = set(expanded)
            if entry.is_dir:
                if entry.relative in expanded:
                    expanded = _without(expanded, entry.relative)
                else:
                    expanded.add(entry.relative)
                return expanded, entry.path, "", gr.update(), selected, project_name, files, f"Selected folder {entry.relative}"
            editor, opened, opened_project, opened_files, message = open_file(entry.path)
            if not opened:
                return expanded, "", "", gr.update(), selected, project_name, files, message
            return expanded, entry.path, "", editor, opened, opened_project, opened_files, message

        return handler

    def delete_entry(entry: TreeEntry):
        """First click asks for confirmation; the second click deletes the file or folder."""

        def handler(pending: str, focus: str, selected: str, project_name: str, files: Dict[str, str], expanded: Set[str], version: int):
            if pending != entry.path:
                return entry.path, focus, expanded, version, gr.update(), selected, project_name, files, f"Click **Delete?** to remove `{entry.relative}`"
            target = Path(entry.path)
            try:
                if not _inside_root(target):
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
            if project_name not in store.list_projects():
                project_name, files = "", {}
            elif project_name:
                try:
                    files = store.load(project_name)
                except ValueError:
                    files = {}
            focus = "" if removed(focus) else focus
            return "", focus, _without(set(expanded), entry.relative), version + 1, editor, selected, project_name, files, f"Deleted `{entry.relative}`"

        return handler

    def create_project(expanded: Set[str], version: int):
        index = len(store.list_projects()) + 1
        name = f"project-{index}"
        while (store.root / name).exists():
            index += 1
            name = f"project-{index}"
        store.create(name)
        main = str(store.root / name / "main.py")
        editor, _, _, files, _ = open_file(main)
        return set(expanded) | {name}, main, "", version + 1, editor, main, name, files, f"Created {name}"

    def create_file(focus: str, project_name: str, files: Dict[str, str], selected: str, expanded: Set[str], version: int):
        try:
            directory = target_dir(focus, project_name)
            index = 1
            while (directory / f"untitled_{index}.py").exists():
                index += 1
            new_file = directory / f"untitled_{index}.py"
            new_file.write_text("", encoding="utf-8")
        except (OSError, ValueError) as error:
            return expanded, focus, "", version, gr.update(), selected, project_name, files, f"Cannot create file: {error}"
        expanded = set(expanded) | _ancestors(new_file)
        editor, opened, opened_project, opened_files, _ = open_file(str(new_file))
        if not opened:
            return expanded, str(new_file), "", version + 1, gr.update(), selected, project_name, files, f"Created {_relative(new_file)}"
        return expanded, str(new_file), "", version + 1, editor, opened, opened_project, opened_files, f"Created {_relative(new_file)}"

    def create_folder(focus: str, project_name: str, expanded: Set[str], version: int):
        try:
            directory = target_dir(focus, project_name)
            index = 1
            while (directory / f"folder_{index}").exists():
                index += 1
            new_folder = directory / f"folder_{index}"
            new_folder.mkdir()
        except (OSError, ValueError) as error:
            return expanded, focus, "", version, f"Cannot create folder: {error}"
        # Select the new folder so the next new file goes inside it.
        expanded = set(expanded) | _ancestors(new_folder) | {_relative(new_folder)}
        return expanded, str(new_folder), "", version + 1, f"Created {_relative(new_folder)}"

    def _save_selected(selected: str, content: str, project_name: str, files: Dict[str, str]) -> Tuple[Dict[str, str], str]:
        if not selected or not project_name:
            return files, "Open a project file first"
        project_root = store.root / project_name
        try:
            relative = Path(selected).relative_to(project_root).as_posix()
            # Write only the edited file so deleted files are never recreated from stale state.
            store.save(project_name, {relative: content})
            updated = dict(files or {})
            updated[relative] = content
            return updated, f"Autosaved {relative}"
        except (OSError, ValueError) as error:
            return files, f"Autosave failed: {error}"

    def add_user_message(task: str, history: Optional[List[Dict[str, str]]]) -> Tuple[Any, str, str]:
        """Show the prompt in the chat immediately and clear the prompt box."""
        task = (task or "").strip()
        if not task:
            return gr.update(), "", ""
        history = list(history or [])
        history.append({"role": "user", "content": task})
        # Gradio shows its own typing indicator below this while the agents run.
        return history, "", task

    def _session(project_name: str) -> str:
        """Agent memory is kept per project so each project has its own conversation."""
        return f"project:{project_name}" if project_name else "default"

    def load_chat(project_name: str) -> List[Dict[str, str]]:
        """Chat history shown in the chat box for the active project."""
        if not project_name:
            return []
        return [
            {"role": message.role, "content": message.content}
            for message in active_workflow.memory.chat_history(project_name)
        ]

    def _log_chat(project_name: str, task: str, answer: str) -> None:
        if project_name:
            active_workflow.memory.add_chat(project_name, "user", task)
            active_workflow.memory.add_chat(project_name, "assistant", answer)

    async def ask_code_mentor(
        task: str,
        language: str,
        selected: str,
        selected_code: str,
        history: Optional[List[Dict[str, str]]],
        project_name: str,
        files: Dict[str, str],
        proposals: List[Dict[str, Any]],
    ) -> Tuple[Any, Any, Dict[str, str], List[Dict[str, Any]]]:
        if not task:
            return gr.update(), gr.update(), files, proposals
        # Save unsaved user edits first; agent output is only proposed, never written here.
        if selected and not _same_text(selected_code, _disk_text(selected)):
            files, _ = _save_selected(selected, selected_code, project_name, files)
        history = list(history or [])
        try:
            result = await active_workflow.run(
                CodeMentorRequest(
                    task=task,
                    language=language,
                    code=selected_code,
                    session_id=_session(project_name),
                    project_files=files,
                )
            )
        except Exception as error:  # e.g. bad input, missing API key, or network failure
            label = "Input error" if isinstance(error, ValueError) else type(error).__name__
            answer = f"⚠️ {label}: {error}"
            history.append({"role": "assistant", "content": answer})
            _log_chat(project_name, task, answer)
            return history, "Request failed", files, proposals

        new_proposals: List[Dict[str, Any]] = []
        source = _generated_source(result.code)
        if source and selected and _inside_root(Path(selected)):
            new_proposals.append(_proposal(Path(selected), source, "Implementation"))
        if language == "Python" and project_name:
            tests = _generated_source(result.tests)
            if tests:
                stem = Path(selected).stem.removeprefix("test_") if selected else "main"
                test_path = store.root / project_name / "tests" / f"test_{stem}.py"
                if all(p["path"] != str(test_path) for p in new_proposals):
                    new_proposals.append(_proposal(test_path, tests, "Tests"))
        new_proposals = [p for p in new_proposals if p["content"] != p["original"]]

        answer = result.final_response
        _log_chat(project_name, task, answer)
        if new_proposals:
            summary = ", ".join(f"`{p['relative']}`" for p in new_proposals)
            answer += (
                f"\n\n---\n📝 **{len(new_proposals)} proposed change(s) waiting for your review** "
                f"below the editor: {summary}. Nothing has been saved yet."
            )
            status_text = "Review the proposed changes below the editor"
        else:
            status_text = "No file changes proposed"
        history.append({"role": "assistant", "content": answer})
        return history, status_text, files, new_proposals

    def _proposal(path: Path, content: str, kind: str) -> Dict[str, Any]:
        """A pending, unsaved change: the agent's content plus the file as it is on disk now."""
        try:
            original = path.read_text(encoding="utf-8") if path.is_file() else ""
        except (OSError, ValueError):
            original = ""
        return {
            "path": str(path),
            "relative": _relative(path),
            "kind": kind,
            "content": content,
            "original": original,
            "is_new": not path.exists(),
        }

    def _apply(
        accepted: List[Tuple[Dict[str, Any], str]],
        proposals: List[Dict[str, Any]],
        selected: str,
        project_name: str,
        files: Dict[str, str],
        expanded: Set[str],
        version: int,
    ):
        """Write accepted proposals to disk, then refresh the editor, Explorer, and file state."""
        expanded = set(expanded)
        editor = gr.update()
        saved, failed = [], []
        for proposal, content in accepted:
            path = Path(proposal["path"])
            try:
                if not _inside_root(path):
                    raise ValueError("outside the projects folder")
                parts = Path(_relative(path)).parts
                store.save(parts[0], {Path(*parts[1:]).as_posix(): content})
            except (OSError, ValueError) as error:
                failed.append(f"{proposal['relative']} ({error})")
                continue
            saved.append(proposal["path"])
            expanded |= _ancestors(path)
            if proposal["path"] == selected:
                editor = gr.update(value=content)
        remaining = [p for p in proposals if p["path"] not in saved]
        if project_name and saved:
            try:
                files = store.load(project_name)
            except ValueError:
                pass
        message = f"Saved {', '.join(_relative(Path(p)) for p in saved)}" if saved else ""
        if failed:
            message = (message + ". " if message else "") + f"Could not save {', '.join(failed)}"
        return remaining, editor, files, expanded, version + 1, message or "Nothing to save"

    def accept_proposal(path: str):
        def handler(content, proposals, selected, project_name, files, expanded, version):
            match = [p for p in proposals if p["path"] == path]
            if not match:
                return proposals, gr.update(), files, expanded, version, "That change was already handled"
            return _apply([(match[0], content)], proposals, selected, project_name, files, expanded, version)

        return handler

    def reject_proposal(path: str):
        def handler(proposals):
            remaining = [p for p in proposals if p["path"] != path]
            return remaining, f"Rejected changes to {_relative(Path(path))}"

        return handler

    def accept_all(proposals, selected, project_name, files, expanded, version, *edited):
        # Edited contents arrive in the same order as the proposals were rendered.
        accepted = [(p, edited[i] if i < len(edited) else p["content"]) for i, p in enumerate(proposals)]
        return _apply(accepted, proposals, selected, project_name, files, expanded, version)

    def reject_all(proposals):
        return [], f"Rejected {len(proposals)} proposed change(s)" if proposals else "Nothing to reject"

    def run_code(language: str, project_name: str, files: Dict[str, str]) -> Tuple[str, str]:
        try:
            output = run_project(files or store.load(project_name), language=language)
        except ValueError as error:
            output = f"Run blocked: {error}"
        return output, f"Ran {project_name}"

    def clear(project_name: str) -> Tuple[List[Any], str]:
        active_workflow.memory.clear(_session(project_name))
        if project_name:
            active_workflow.memory.clear_chat(project_name)
        return [], "Chat cleared"

    css = """
    .gradio-container { max-width: 1500px !important; }
    .cm-explorer-actions button { min-width: 34px !important; padding: 0 !important; }
    .cm-explorer-actions { gap: 4px; }
    #cm-explorer {
        max-height: 640px; overflow-y: auto; gap: 0 !important; padding: 4px;
        border: 1px solid var(--border-color-primary); border-radius: 8px;
    }
    #cm-explorer .gap { gap: 1px !important; }
    #cm-explorer .cm-target { padding: 2px 6px 6px; color: var(--body-text-color-subdued); font-size: 12px; }
    #cm-explorer .cm-tree-row { gap: 0 !important; flex-wrap: nowrap !important; align-items: center; border-radius: 4px; }
    #cm-explorer .cm-tree-row:hover { background: #f1f5f9; }
    #cm-explorer .cm-tree-row.cm-active { background: #e0e7ff; }
    #cm-explorer .cm-tree-row button {
        border: 0 !important; box-shadow: none !important; background: transparent !important;
        min-height: 26px; height: 26px;
    }
    #cm-explorer .cm-tree-name {
        justify-content: flex-start !important; text-align: left; white-space: pre !important;
        overflow: hidden; text-overflow: ellipsis; padding: 0 6px !important;
        font: 13px Consolas, monospace !important; font-weight: 400 !important;
    }
    #cm-explorer .cm-tree-delete {
        flex: 0 0 26px !important; width: 26px; padding: 0 !important;
        font-size: 12px !important; opacity: 0.55; border-radius: 4px !important;
    }
    #cm-explorer .cm-tree-delete img { width: 14px !important; height: 14px !important; margin: 0 !important; }
    #cm-explorer .cm-tree-row:hover .cm-tree-delete { opacity: 1; }
    #cm-explorer .cm-tree-delete:hover { background: #fee2e2 !important; }
    /* Fixed-height editor that scrolls internally instead of growing with the file. */
    #cm-editor .cm-editor { height: 690px !important; max-height: 690px !important; }
    #cm-editor .cm-scroller { overflow: auto !important; }
    .cm-chat-header { align-items: center; }
    .cm-composer { align-items: stretch; gap: 8px; }
    .cm-composer textarea { resize: none; }
    #cm-review .cm-review-header, #cm-review .cm-proposal-header { align-items: center; }
    #cm-review .cm-proposal { border: 1px solid var(--border-color-primary); border-radius: 8px; padding: 8px; }
    #cm-review .cm-editor { max-height: 360px; }
    #cm-review .cm-scroller { overflow: auto !important; }
    .cm-diff {
        max-height: 360px; overflow: auto; border: 1px solid var(--border-color-primary); border-radius: 6px;
        font: 12.5px/1.5 Consolas, monospace; background: #fff;
    }
    .cm-diff-line { white-space: pre; padding: 0 10px; min-width: max-content; }
    .cm-diff-add { background: #dcfce7; color: #14532d; }
    .cm-diff-del { background: #fee2e2; color: #7f1d1d; }
    .cm-diff-hunk { background: #eef2ff; color: #4338ca; }
    .cm-diff-ctx { color: #374151; }
    #cm-status { min-height: 24px; max-height: 24px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    #cm-explorer .cm-tree-delete.cm-confirm {
        flex: 0 0 auto !important; width: auto; padding: 0 8px !important; opacity: 1;
        background: #fee2e2 !important; color: #b91c1c !important; font-weight: 600;
    }
    """
    with gr.Blocks(title="CodeMentor AI IDE", css=css) as app:
        gr.Markdown("# CodeMentor AI IDE")
        project_state = gr.State(initial_project)
        files_state = gr.State(initial_files)
        starter_path = str(store.root / initial_project / "main.py")
        selected_state = gr.State(starter_path)
        expanded_state = gr.State({initial_project})
        # Last clicked Explorer item; new files and folders are created relative to it.
        focus_state = gr.State("")
        pending_delete_state = gr.State("")
        # Bumped after filesystem changes so the Explorer re-renders.
        tree_version = gr.State(0)
        # Prompt captured when the user presses Send, so the prompt box can be cleared at once.
        pending_task_state = gr.State("")
        # Agent-generated file changes waiting for the user to accept or reject them.
        proposals_state = gr.State([])
        with gr.Row():
            with gr.Column(scale=1, min_width=260):
                with gr.Row(elem_classes="cm-explorer-actions"):
                    gr.Markdown("### Explorer")
                    new_project_button = gr.Button("＋", size="sm", min_width=34)
                    new_file_button = gr.Button("＋▤", size="sm", min_width=34)
                    new_folder_button = gr.Button("＋□", size="sm", min_width=34)
                with gr.Column(elem_id="cm-explorer"):

                    @gr.render(inputs=[expanded_state, focus_state, pending_delete_state, project_state, tree_version])
                    def render_tree(expanded, focus, pending, project_name, _version):
                        try:
                            hint = _relative(target_dir(focus, project_name))
                        except ValueError:
                            hint = "no project"
                        gr.Markdown(f"New items go in `{hint}/`", elem_classes="cm-target")
                        entries = explorer_entries(str(store.root), expanded)
                        if not entries:
                            gr.Markdown("No projects yet. Click ＋ to create one.")
                        for entry in entries:
                            row_classes = ["cm-tree-row"] + (["cm-active"] if entry.path == focus else [])
                            confirming = pending == entry.path
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
                                click_entry(entry),
                                inputs=[expanded_state, selected_state, project_state, files_state],
                                outputs=[expanded_state, focus_state, pending_delete_state, selected_code, selected_state, project_state, files_state, status],
                                api_name=False,
                            )
                            delete_button.click(
                                delete_entry(entry),
                                inputs=[pending_delete_state, focus_state, selected_state, project_state, files_state, expanded_state, tree_version],
                                outputs=[pending_delete_state, focus_state, expanded_state, tree_version, selected_code, selected_state, project_state, files_state, status],
                                api_name=False,
                            )

            with gr.Column(scale=3, min_width=600):
                gr.Markdown("### Editor")
                selected_code = gr.Code(
                    value=initial_files.get("main.py", ""),
                    label=f"{initial_project}/main.py",
                    language="python",
                    lines=30,
                    elem_id="cm-editor",
                )
            with gr.Column(scale=2, min_width=420):
                with gr.Row(equal_height=True, elem_classes="cm-chat-header"):
                    gr.Markdown("### Assistant")
                    language = gr.Dropdown(choices=LANGUAGES, value="Python", show_label=False, container=False, scale=0, min_width=130)
                    clear_button = gr.Button("Clear chat", size="sm", scale=0, min_width=90)
                chat = gr.Chatbot(
                    show_label=False,
                    type="messages",
                    height=640,
                    bubble_full_width=False,
                    placeholder="Ask CodeMentor to build, fix, review, or test your code.",
                )
                with gr.Row(equal_height=True, elem_classes="cm-composer"):
                    task = gr.Textbox(
                        show_label=False,
                        container=False,
                        # lines=1 makes Enter send; Shift+Enter still adds lines up to max_lines.
                        lines=1,
                        max_lines=6,
                        scale=5,
                        placeholder="Ask for a feature, refactor, review, or test… (Enter to send, Shift+Enter for a new line)",
                    )
                    ask_button = gr.Button("Send", variant="primary", scale=1, min_width=80)
                status = gr.Markdown("Ready", elem_id="cm-status")
        # Human-in-the-loop review: nothing the agents generate is written until it is accepted here.
        with gr.Column(elem_id="cm-review"):

            @gr.render(inputs=proposals_state)
            def render_review(proposals):
                if not proposals:
                    return
                review_inputs = [proposals_state, selected_state, project_state, files_state, expanded_state, tree_version]
                apply_outputs = [proposals_state, selected_code, files_state, expanded_state, tree_version, status]
                with gr.Row(equal_height=True, elem_classes="cm-review-header"):
                    gr.Markdown(
                        f"### Review proposed changes ({len(proposals)})\n"
                        "Nothing has been saved yet. Check the diff, optionally edit, then accept or reject."
                    )
                    accept_all_button = gr.Button("Accept all", variant="primary", size="sm", scale=0, min_width=110)
                    reject_all_button = gr.Button("Reject all", variant="stop", size="sm", scale=0, min_width=110)
                edit_boxes = []
                for proposal in proposals:
                    added, removed = diff_stats(proposal["original"], proposal["content"])
                    label = "new file" if proposal["is_new"] else f"+{added} −{removed}"
                    with gr.Column(elem_classes="cm-proposal"):
                        with gr.Row(equal_height=True, elem_classes="cm-proposal-header"):
                            gr.Markdown(f"**{proposal['kind']}** · `{proposal['relative']}` · {label}")
                            accept_button = gr.Button("Accept", variant="primary", size="sm", scale=0, min_width=90)
                            reject_button = gr.Button("Reject", size="sm", scale=0, min_width=90)
                        with gr.Tabs():
                            with gr.Tab("Diff"):
                                gr.HTML(diff_html(proposal["original"], proposal["content"]))
                            with gr.Tab("Edit before saving"):
                                edit_box = gr.Code(
                                    value=proposal["content"],
                                    language=EDITOR_LANGUAGES.get(Path(proposal["path"]).suffix.lower()),
                                    interactive=True,
                                    show_label=False,
                                    lines=12,
                                )
                    edit_boxes.append(edit_box)
                    accept_button.click(
                        accept_proposal(proposal["path"]),
                        inputs=[edit_box] + review_inputs,
                        outputs=apply_outputs,
                        api_name=False,
                    )
                    reject_button.click(
                        reject_proposal(proposal["path"]),
                        inputs=proposals_state,
                        outputs=[proposals_state, status],
                        api_name=False,
                    )
                accept_all_button.click(accept_all, inputs=review_inputs + edit_boxes, outputs=apply_outputs, api_name=False)
                reject_all_button.click(reject_all, inputs=proposals_state, outputs=[proposals_state, status], api_name=False)

        run_button = gr.Button("Run project", variant="secondary")
        run_output = gr.Code(label="Execution and test output", language="shell", lines=8)

        new_project_button.click(
            create_project,
            inputs=[expanded_state, tree_version],
            outputs=[expanded_state, focus_state, pending_delete_state, tree_version, selected_code, selected_state, project_state, files_state, status],
            api_name=False,
        )
        new_file_button.click(
            create_file,
            inputs=[focus_state, project_state, files_state, selected_state, expanded_state, tree_version],
            outputs=[expanded_state, focus_state, pending_delete_state, tree_version, selected_code, selected_state, project_state, files_state, status],
            api_name=False,
        )
        new_folder_button.click(
            create_folder,
            inputs=[focus_state, project_state, expanded_state, tree_version],
            outputs=[expanded_state, focus_state, pending_delete_state, tree_version, status],
            api_name=False,
        )
        # .input fires only for user edits, not when a file is loaded into the editor.
        # always_last makes sure the final keystrokes are saved even while a save is running,
        # and hiding progress keeps the layout still while typing.
        selected_code.input(
            _save_selected,
            inputs=[selected_state, selected_code, project_state, files_state],
            outputs=[files_state, status],
            api_name=False,
            trigger_mode="always_last",
            show_progress="hidden",
        )
        # Show the prompt in the chat right away, then run the agents and replace the placeholder.
        for send in (ask_button.click, task.submit):
            send(
                add_user_message,
                inputs=[task, chat],
                outputs=[chat, task, pending_task_state],
                queue=False,
                api_name=False,
                show_progress="hidden",
            ).then(
                ask_code_mentor,
                inputs=[pending_task_state, language, selected_state, selected_code, chat, project_state, files_state, proposals_state],
                outputs=[chat, status, files_state, proposals_state],
                api_name=False,
                show_progress="hidden",
            )
        run_button.click(run_code, inputs=[language, project_state, files_state], outputs=[run_output, status], api_name=False)
        clear_button.click(clear, inputs=project_state, outputs=[chat, status], api_name=False)
        # Each project has its own chat: load it on page load and whenever the active project changes.
        app.load(load_chat, inputs=project_state, outputs=chat, api_name=False)
        project_state.change(load_chat, inputs=project_state, outputs=chat, api_name=False, show_progress="hidden")
    return app


def launch(database_path: str = "codementor.db", **kwargs: Any) -> None:
    workflow = CodeMentorWorkflow(memory=SQLiteMemory(database_path))
    kwargs.setdefault("server_name", "127.0.0.1")
    create_app(workflow).launch(**kwargs)
