"""Styles for the IDE: Explorer, editor, chat, review panel, and status line."""

CSS = """
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
/* Chat: answers use the full width on the left, prompts are compact bubbles on the right,
   and nothing inside a message may be wider than the panel. */
#cm-chat .bubble-wrap { padding: 12px 10px 4px !important; }
#cm-chat .message-row { margin: 6px 0 !important; }
#cm-chat .message-row.bot-row { max-width: 100% !important; width: 100%; }
#cm-chat .message-row.user-row { max-width: 85% !important; margin-left: auto !important; }
#cm-chat .flex-wrap.bot, #cm-chat .flex-wrap.user { min-width: 0; max-width: 100%; }
#cm-chat .flex-wrap.bot { width: 100%; padding: 10px 14px !important; border-radius: 10px !important; }
#cm-chat .flex-wrap.user { padding: 8px 12px !important; border-radius: 10px !important; }
#cm-chat .message, #cm-chat .message > * { min-width: 0; max-width: 100%; }
#cm-chat .prose {
    font-size: 14px !important; line-height: 1.55 !important;
    overflow-wrap: anywhere; word-break: normal;
}
#cm-chat .prose > :first-child { margin-top: 0 !important; }
#cm-chat .prose > :last-child { margin-bottom: 0 !important; }
#cm-chat .prose h1, #cm-chat .prose h2, #cm-chat .prose h3, #cm-chat .prose h4 {
    font-weight: 650 !important; line-height: 1.3 !important; margin: 14px 0 6px !important;
}
#cm-chat .prose h1 { font-size: 17px !important; }
#cm-chat .prose h2 {
    font-size: 15.5px !important; padding-bottom: 4px;
    border-bottom: 1px solid var(--border-color-primary);
}
#cm-chat .prose h3, #cm-chat .prose h4 { font-size: 14.5px !important; }
#cm-chat .prose p { margin: 6px 0 !important; }
#cm-chat .prose ul, #cm-chat .prose ol { margin: 4px 0 8px !important; padding-left: 1.4em !important; }
#cm-chat .prose li { margin: 3px 0 !important; padding-left: 2px; font-size: inherit !important; }
/* Bullets outside the text so wrapped lines line up with the first line. */
#cm-chat .prose ul { list-style: disc outside !important; }
#cm-chat .prose ul ul { list-style-type: circle !important; }
#cm-chat .prose ol { list-style: decimal outside !important; }
#cm-chat .prose li ul, #cm-chat .prose li ol { font-size: inherit !important; margin: 2px 0 !important; }
#cm-chat .prose table td, #cm-chat .prose table th { font-size: 13px !important; }
#cm-chat .prose table td code, #cm-chat .prose table th code { font-size: 12px !important; }
#cm-chat .prose li > p { margin: 0 !important; }
#cm-chat .prose hr { margin: 14px 0 !important; }
#cm-chat .prose blockquote {
    margin: 8px 0 !important; padding: 4px 10px !important;
    border-left: 3px solid var(--border-color-primary); color: var(--body-text-color-subdued);
}
#cm-chat .prose :not(pre) > code { font-size: 12.5px !important; padding: 1px 4px; border-radius: 4px; }
/* Code blocks and tables scroll sideways inside the message instead of widening it. */
#cm-chat .code_wrap, #cm-chat .prose pre { max-width: 100% !important; }
#cm-chat .prose pre {
    overflow-x: auto !important; white-space: pre !important; overflow-wrap: normal;
    margin: 8px 0 !important; padding: 10px 12px !important;
    font-size: 12.5px !important; line-height: 1.5 !important; border-radius: 8px !important;
}
#cm-chat .prose pre code { white-space: pre !important; overflow-wrap: normal; }
#cm-chat .prose table {
    display: block; max-width: 100%; overflow-x: auto;
    font-size: 13px !important; margin: 8px 0 !important;
}
#cm-chat .prose th, #cm-chat .prose td { padding: 5px 10px !important; }
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
#cm-explorer .cm-renaming { padding: 2px 4px; background: #e0e7ff; }
#cm-explorer .cm-rename-box textarea, #cm-explorer .cm-rename-box input {
    font: 13px Consolas, monospace !important; padding: 2px 6px !important; min-height: 26px;
}
#cm-explorer .cm-rename-save, #cm-explorer .cm-rename-cancel { flex: 0 0 28px !important; width: 28px; padding: 0 !important; }
#cm-explorer .cm-tree-delete.cm-confirm {
    flex: 0 0 auto !important; width: auto; padding: 0 8px !important; opacity: 1;
    background: #fee2e2 !important; color: #b91c1c !important; font-weight: 600;
}
"""
