"""Command-line entrypoint for CodeMentor AI."""

from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from .workflow import CodeMentorRequest, CodeMentorWorkflow


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the CodeMentor AI agent workflow.")
    parser.add_argument("task", help="Coding task for the agents")
    parser.add_argument("--language", default="", help="Programming language")
    parser.add_argument("--code", default="", help="Existing code to review or modify")
    args = parser.parse_args()
    result = asyncio.run(
        CodeMentorWorkflow().run(
            CodeMentorRequest(task=args.task, language=args.language, code=args.code)
        )
    )
    print(result.final_response)