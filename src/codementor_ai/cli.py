"""Command-line entrypoint for CodeMentor AI."""

from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from .memory import SQLiteMemory
from .workflow import CodeMentorRequest, CodeMentorWorkflow


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the CodeMentor AI agent workflow.")
    parser.add_argument("task", nargs="?", help="Coding task for the agents")
    parser.add_argument("--language", default="", help="Programming language")
    parser.add_argument("--code", default="", help="Existing code to review or modify")
    parser.add_argument("--session-id", default="default", help="Conversation session ID")
    parser.add_argument("--database", default="codementor.db", help="SQLite memory database")
    parser.add_argument("--ui", action="store_true", help="Launch the Gradio interface")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the Gradio interface (default: 7860, or the next free port)",
    )
    args = parser.parse_args()
    if args.ui:
        from .ui import launch

        launch(database_path=args.database, **({"server_port": args.port} if args.port else {}))
        return
    if not args.task:
        parser.error("task is required unless --ui is used")
    result = asyncio.run(
        CodeMentorWorkflow(memory=SQLiteMemory(args.database)).run(
            CodeMentorRequest(
                task=args.task,
                language=args.language,
                code=args.code,
                session_id=args.session_id,
            )
        )
    )
    print(result.final_response)