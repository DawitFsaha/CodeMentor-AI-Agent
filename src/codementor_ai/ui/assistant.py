"""Assistant panel: the chat, sending requests to the agents, and per-project history."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

from ..core import CodeMentorRequest
from ..project import SUFFIX_LANGUAGE, extract_files, target_for_language, test_target
from .context import IDEContext
from .helpers import disk_text, generated_source, same_text


class AssistantHandlers:
    """Event handlers for the chat. Each returns values for the outputs it is wired to."""

    def __init__(self, ctx: IDEContext) -> None:
        self.ctx = ctx

    @staticmethod
    def add_user_message(task: str, history: Optional[List[Dict[str, str]]]) -> Tuple[Any, str, str]:
        """Show the prompt in the chat immediately and clear the prompt box."""
        task = (task or "").strip()
        if not task:
            return gr.update(), "", ""
        history = list(history or [])
        history.append({"role": "user", "content": task})
        # Gradio shows its own typing indicator below this while the agents run.
        return history, "", task

    async def ask(
        self,
        task: str,
        language: str,
        selected: str,
        selected_code: str,
        history: Optional[List[Dict[str, str]]],
        project_name: str,
        files: Dict[str, str],
        proposals: List[Dict[str, Any]],
    ) -> Tuple[Any, Any, Dict[str, str], List[Dict[str, Any]]]:
        """Run the agents and turn their code into proposals; nothing is written to disk here."""
        ctx = self.ctx
        if not task:
            return gr.update(), gr.update(), files, proposals
        # Save unsaved user edits first; agent output is only proposed, never written here.
        if selected and not same_text(selected_code, disk_text(selected)):
            files, _ = ctx.save_selected(selected, selected_code, project_name, files)
        history = list(history or [])
        # The agents write the open file, or a new file in the chosen language when the
        # dropdown differs from the open file's language (e.g. main.py + JavaScript -> main.js).
        target = target_for_language(ctx.project_relative(selected, project_name), language)
        try:
            result = await ctx.workflow.run(
                CodeMentorRequest(
                    task=task,
                    language=language,
                    code=selected_code,
                    session_id=ctx.session(project_name),
                    project_files=files,
                    entrypoint=target,
                )
            )
        except Exception as error:  # e.g. bad input, missing API key, or network failure
            label = "Input error" if isinstance(error, ValueError) else type(error).__name__
            answer = f"⚠️ {label}: {error}"
            history.append({"role": "assistant", "content": answer})
            ctx.log_chat(project_name, task, answer)
            return history, "Request failed", files, proposals

        new_proposals = self._proposals(result, target, project_name)
        answer = result.final_response
        ctx.log_chat(project_name, task, answer)
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

    def _proposals(self, result: Any, target: str, project_name: str) -> List[Dict[str, Any]]:
        """One proposal per file in the Code Writer's answer, plus the generated test file."""
        ctx = self.ctx
        proposals: List[Dict[str, Any]] = []
        if project_name:
            project_root = (ctx.store.root / project_name).resolve()
            for relative, content in extract_files(result.code, target).items():
                path = project_root.joinpath(*PurePosixPath(relative).parts)
                if project_root not in path.resolve().parents:
                    continue
                if relative == target:
                    kind = "Implementation" if path.exists() else "New file"
                else:
                    kind = "Helper file" if path.exists() else "New file"
                proposals.append(ctx.proposal(path, content, kind))
        tests_location = test_target(target)
        if tests_location and project_name:
            tests = generated_source(result.tests)
            if tests:
                # Same location the Testing Agent was told to use.
                test_path = ctx.store.root / project_name / tests_location[0]
                if all(p["path"] != str(test_path) for p in proposals):
                    proposals.append(ctx.proposal(test_path, tests, "Tests"))
        return [p for p in proposals if p["content"] != p["original"]]

    def load_chat(self, project_name: str) -> List[Dict[str, str]]:
        """Chat history shown in the chat box for the active project."""
        if not project_name:
            return []
        return [
            {"role": message.role, "content": message.content}
            for message in self.ctx.workflow.memory.chat_history(project_name)
        ]

    def clear(self, project_name: str) -> Tuple[List[Any], str]:
        memory = self.ctx.workflow.memory
        memory.clear(self.ctx.session(project_name))
        if project_name:
            memory.clear_chat(project_name)
        return [], "Chat cleared"

    @staticmethod
    def language_for_file(selected: str):
        """Keep the language dropdown in step with the open file."""
        language_name = SUFFIX_LANGUAGE.get(Path(selected).suffix.lower()) if selected else None
        return gr.update(value=language_name) if language_name else gr.update()
