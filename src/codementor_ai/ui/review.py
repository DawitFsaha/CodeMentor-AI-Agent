"""Human-in-the-loop review: proposed changes are shown as diffs and saved only when accepted."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Set, Tuple

import gradio as gr

from .constants import EDITOR_LANGUAGES
from .context import IDEContext
from .diff import diff_html, diff_stats


class ReviewHandlers:
    """Event handlers for the review panel. Each returns values for the outputs it is wired to."""

    def __init__(self, ctx: IDEContext) -> None:
        self.ctx = ctx

    def apply(
        self,
        accepted: List[Tuple[Dict[str, Any], str]],
        proposals: List[Dict[str, Any]],
        selected: str,
        project_name: str,
        files: Dict[str, str],
        expanded: Set[str],
        version: int,
    ):
        """Write accepted proposals to disk, then refresh the editor, Explorer, and file state."""
        ctx = self.ctx
        expanded = set(expanded)
        editor = gr.update()
        saved, failed = [], []
        for proposal, content in accepted:
            path = Path(proposal["path"])
            try:
                if not ctx.inside_root(path):
                    raise ValueError("outside the projects folder")
                parts = Path(ctx.relative(path)).parts
                ctx.store.save(parts[0], {Path(*parts[1:]).as_posix(): content})
            except (OSError, ValueError) as error:
                failed.append(f"{proposal['relative']} ({error})")
                continue
            saved.append(proposal["path"])
            expanded |= ctx.ancestors(path)
            if proposal["path"] == selected:
                editor = gr.update(value=content)
        remaining = [p for p in proposals if p["path"] not in saved]
        if project_name and saved:
            try:
                files = ctx.store.load(project_name)
            except ValueError:
                pass
        message = f"Saved {', '.join(ctx.relative(Path(p)) for p in saved)}" if saved else ""
        if failed:
            message = (message + ". " if message else "") + f"Could not save {', '.join(failed)}"
        return remaining, editor, files, expanded, version + 1, message or "Nothing to save"

    def accept_proposal(self, path: str):
        def handler(content, proposals, selected, project_name, files, expanded, version):
            match = [p for p in proposals if p["path"] == path]
            if not match:
                return proposals, gr.update(), files, expanded, version, "That change was already handled"
            return self.apply([(match[0], content)], proposals, selected, project_name, files, expanded, version)

        return handler

    def reject_proposal(self, path: str):
        def handler(proposals):
            remaining = [p for p in proposals if p["path"] != path]
            return remaining, f"Rejected changes to {self.ctx.relative(Path(path))}"

        return handler

    def accept_all(self, proposals, selected, project_name, files, expanded, version, *edited):
        # Edited contents arrive in the same order as the proposals were rendered.
        accepted = [(p, edited[i] if i < len(edited) else p["content"]) for i, p in enumerate(proposals)]
        return self.apply(accepted, proposals, selected, project_name, files, expanded, version)

    @staticmethod
    def reject_all(proposals):
        return [], f"Rejected {len(proposals)} proposed change(s)" if proposals else "Nothing to reject"


def build_review(handlers: ReviewHandlers, ui: SimpleNamespace) -> None:
    """Declare the review panel. Call inside the review column of the layout."""

    @gr.render(inputs=ui.proposals_state)
    def render_review(proposals):
        if not proposals:
            return
        review_inputs = [ui.proposals_state, ui.selected_state, ui.project_state, ui.files_state, ui.expanded_state, ui.tree_version]
        apply_outputs = [ui.proposals_state, ui.selected_code, ui.files_state, ui.expanded_state, ui.tree_version, ui.status]
        with gr.Row(equal_height=True, elem_classes="cm-review-header"):
            gr.Markdown(
                f"### Review proposed changes ({len(proposals)})\n"
                "Nothing has been saved yet. Check the diff, optionally edit, then accept or reject."
            )
            accept_all_button = gr.Button("Accept all", variant="primary", size="sm", scale=0, min_width=110)
            reject_all_button = gr.Button("Reject all", variant="stop", size="sm", scale=0, min_width=110)
        edit_boxes = []
        for proposal in proposals:
            edit_box, accept_button, reject_button = _proposal_card(proposal)
            edit_boxes.append(edit_box)
            accept_button.click(
                handlers.accept_proposal(proposal["path"]),
                inputs=[edit_box] + review_inputs,
                outputs=apply_outputs,
                api_name=False,
            )
            reject_button.click(
                handlers.reject_proposal(proposal["path"]),
                inputs=ui.proposals_state,
                outputs=[ui.proposals_state, ui.status],
                api_name=False,
            )
        accept_all_button.click(handlers.accept_all, inputs=review_inputs + edit_boxes, outputs=apply_outputs, api_name=False)
        reject_all_button.click(handlers.reject_all, inputs=ui.proposals_state, outputs=[ui.proposals_state, ui.status], api_name=False)


def _proposal_card(proposal: Dict[str, Any]):
    """One proposed file: header with Accept/Reject, then Diff and Edit-before-saving tabs."""
    added, removed = diff_stats(proposal["original"], proposal["content"])
    label = "new file" if proposal["is_new"] else f"+{added} −{removed}"
    if proposal.get("problem"):
        label += f" · ⚠️ {proposal['problem']}"
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
    return edit_box, accept_button, reject_button
