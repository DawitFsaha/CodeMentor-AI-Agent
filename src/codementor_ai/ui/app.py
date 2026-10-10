"""Gradio mini-IDE: page layout and event wiring.

The handlers live in their own modules: ``explorer`` (project tree), ``assistant`` (chat and
agents), ``review`` (human-in-the-loop review of proposed changes), and ``run_panel``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

import gradio as gr

from ..core import CodeMentorWorkflow, SQLiteMemory
from ..project import ProjectStore
from .assistant import AssistantHandlers
from .constants import LANGUAGES
from .context import IDEContext
from .explorer import ExplorerHandlers, build_tree
from .review import ReviewHandlers, build_review
from .run_panel import RunHandlers
from .styles import CSS


def create_app(workflow: Optional[CodeMentorWorkflow] = None) -> Any:
    """Build the IDE around the projects directory and native file tree."""
    store = ProjectStore()
    if not store.list_projects():
        store.create("starter")
    ctx = IDEContext(workflow or CodeMentorWorkflow(), store)
    explorer = ExplorerHandlers(ctx)
    assistant = AssistantHandlers(ctx)
    review = ReviewHandlers(ctx)
    runner = RunHandlers(ctx)

    initial_project = store.list_projects()[0]
    initial_files = store.load(initial_project)
    # Every component and state, so the Explorer and review renderers can reference them.
    ui = SimpleNamespace()

    with gr.Blocks(title="CodeMentor AI IDE", css=CSS) as app:
        gr.Markdown("# CodeMentor AI IDE")
        _create_states(ui, store, initial_project, initial_files)
        with gr.Row():
            with gr.Column(scale=1, min_width=260):
                with gr.Row(elem_classes="cm-explorer-actions"):
                    gr.Markdown("### Explorer")
                    ui.new_project_button = gr.Button("＋", size="sm", min_width=34)
                    ui.new_file_button = gr.Button("＋▤", size="sm", min_width=34)
                    ui.new_folder_button = gr.Button("＋□", size="sm", min_width=34)
                with gr.Column(elem_id="cm-explorer"):
                    build_tree(explorer, ui)
            with gr.Column(scale=3, min_width=600):
                gr.Markdown("### Editor")
                ui.selected_code = gr.Code(
                    value=initial_files.get("main.py", ""),
                    label=f"{initial_project}/main.py",
                    language="python",
                    lines=30,
                    elem_id="cm-editor",
                )
            with gr.Column(scale=2, min_width=420):
                _create_assistant_panel(ui)
        # Human-in-the-loop review: nothing the agents generate is written until it is accepted here.
        with gr.Column(elem_id="cm-review"):
            build_review(review, ui)
        ui.run_button = gr.Button("Run project", variant="secondary")
        ui.run_output = gr.Code(label="Execution and test output", language="shell", lines=8)

        _wire_explorer_toolbar(ui, explorer)
        _wire_editor(ui, ctx)
        _wire_assistant(ui, assistant)
        ui.run_button.click(runner.run_code, inputs=[ui.language, ui.selected_state, ui.project_state, ui.files_state], outputs=[ui.run_output, ui.status], api_name=False)
        _wire_page_load(app, ui, explorer, assistant)
    return app


def _create_states(ui: SimpleNamespace, store: ProjectStore, initial_project: str, initial_files: dict) -> None:
    ui.project_state = gr.State(initial_project)
    ui.files_state = gr.State(initial_files)
    ui.selected_state = gr.State(str(store.root / initial_project / "main.py"))
    ui.expanded_state = gr.State({initial_project})
    # Last clicked Explorer item; new files and folders are created relative to it.
    ui.focus_state = gr.State("")
    ui.pending_delete_state = gr.State("")
    # Explorer row being renamed (absolute path) and the last row click, for double-clicks.
    ui.renaming_state = gr.State("")
    ui.last_click_state = gr.State({"item": "", "at": 0.0})
    # Bumped after filesystem changes so the Explorer re-renders.
    ui.tree_version = gr.State(0)
    # Prompt captured when the user presses Send, so the prompt box can be cleared at once.
    ui.pending_task_state = gr.State("")
    # Agent-generated file changes waiting for the user to accept or reject them.
    ui.proposals_state = gr.State([])


def _create_assistant_panel(ui: SimpleNamespace) -> None:
    with gr.Row(equal_height=True, elem_classes="cm-chat-header"):
        gr.Markdown("### Assistant")
        ui.language = gr.Dropdown(choices=LANGUAGES, value="Python", show_label=False, container=False, scale=0, min_width=130)
        ui.clear_button = gr.Button("Clear chat", size="sm", scale=0, min_width=90)
    ui.chat = gr.Chatbot(
        show_label=False,
        type="messages",
        height=640,
        bubble_full_width=False,
        placeholder="Ask CodeMentor to build, fix, review, or test your code.",
        elem_id="cm-chat",
    )
    with gr.Row(equal_height=True, elem_classes="cm-composer"):
        ui.task = gr.Textbox(
            show_label=False,
            container=False,
            # lines=1 makes Enter send; Shift+Enter still adds lines up to max_lines.
            lines=1,
            max_lines=6,
            scale=5,
            placeholder="Ask for a feature, refactor, review, or test… (Enter to send, Shift+Enter for a new line)",
        )
        ui.ask_button = gr.Button("Send", variant="primary", scale=1, min_width=80)
    ui.status = gr.Markdown("Ready", elem_id="cm-status")


def _wire_explorer_toolbar(ui: SimpleNamespace, explorer: ExplorerHandlers) -> None:
    ui.new_project_button.click(
        explorer.create_project,
        inputs=[ui.expanded_state, ui.tree_version, ui.language],
        outputs=[ui.expanded_state, ui.focus_state, ui.pending_delete_state, ui.tree_version, ui.selected_code, ui.selected_state, ui.project_state, ui.files_state, ui.status],
        api_name=False,
    )
    ui.new_file_button.click(
        explorer.create_file,
        inputs=[ui.focus_state, ui.project_state, ui.files_state, ui.selected_state, ui.expanded_state, ui.tree_version],
        outputs=[ui.expanded_state, ui.focus_state, ui.pending_delete_state, ui.tree_version, ui.selected_code, ui.selected_state, ui.project_state, ui.files_state, ui.status],
        api_name=False,
    )
    ui.new_folder_button.click(
        explorer.create_folder,
        inputs=[ui.focus_state, ui.project_state, ui.expanded_state, ui.tree_version],
        outputs=[ui.expanded_state, ui.focus_state, ui.pending_delete_state, ui.tree_version, ui.status],
        api_name=False,
    )


def _wire_editor(ui: SimpleNamespace, ctx: IDEContext) -> None:
    # .input fires only for user edits, not when a file is loaded into the editor.
    # always_last makes sure the final keystrokes are saved even while a save is running,
    # and hiding progress keeps the layout still while typing.
    ui.selected_code.input(
        ctx.save_selected,
        inputs=[ui.selected_state, ui.selected_code, ui.project_state, ui.files_state],
        outputs=[ui.files_state, ui.status],
        api_name=False,
        trigger_mode="always_last",
        show_progress="hidden",
    )


def _wire_assistant(ui: SimpleNamespace, assistant: AssistantHandlers) -> None:
    # Show the prompt in the chat right away, then run the agents.
    for send in (ui.ask_button.click, ui.task.submit):
        send(
            assistant.add_user_message,
            inputs=[ui.task, ui.chat],
            outputs=[ui.chat, ui.task, ui.pending_task_state],
            queue=False,
            api_name=False,
            show_progress="hidden",
        ).then(
            assistant.ask,
            inputs=[ui.pending_task_state, ui.language, ui.selected_state, ui.selected_code, ui.chat, ui.project_state, ui.files_state, ui.proposals_state],
            outputs=[ui.chat, ui.status, ui.files_state, ui.proposals_state],
            api_name=False,
            show_progress="hidden",
        )
    ui.clear_button.click(assistant.clear, inputs=ui.project_state, outputs=[ui.chat, ui.status], api_name=False)
    # The language dropdown follows the open file, so requests target that file by default.
    ui.selected_state.change(assistant.language_for_file, inputs=ui.selected_state, outputs=ui.language, api_name=False, show_progress="hidden")


def _wire_page_load(app: Any, ui: SimpleNamespace, explorer: ExplorerHandlers, assistant: AssistantHandlers) -> None:
    # Each project has its own chat: load it on page load and whenever the active project changes.
    app.load(
        explorer.ensure_project,
        inputs=[ui.project_state, ui.expanded_state, ui.selected_state],
        outputs=[ui.project_state, ui.expanded_state, ui.selected_state, ui.selected_code, ui.files_state],
        api_name=False,
    ).then(assistant.load_chat, inputs=ui.project_state, outputs=ui.chat, api_name=False)
    ui.project_state.change(assistant.load_chat, inputs=ui.project_state, outputs=ui.chat, api_name=False, show_progress="hidden")


def launch(database_path: str = "codementor.db", **kwargs: Any) -> None:
    workflow = CodeMentorWorkflow(memory=SQLiteMemory(database_path))
    kwargs.setdefault("server_name", "127.0.0.1")
    create_app(workflow).launch(**kwargs)
