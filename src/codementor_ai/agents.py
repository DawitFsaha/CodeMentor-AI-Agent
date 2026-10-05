"""Definitions for the specialized CodeMentor AI agents."""

from __future__ import annotations

from typing import Dict, Optional

from agents import Agent


COORDINATOR_INSTRUCTIONS = """You coordinate a coding task across specialist agents.
Identify the requested language, deliverables, and constraints. Route the task to the
Code Writer, Code Review and Debugging, and Testing agents in that order. Keep the
request in scope, preserve user requirements, and never claim code was executed unless
the workflow explicitly provides execution evidence. Your output is a concise routing
brief or, during the final pass, one structured answer containing code, review findings,
and tests."""

CODE_WRITER_INSTRUCTIONS = """You are the Code Writer Agent. Generate or modify code from
the user's requirements and the coordinator's routing brief. Respect the requested
language and constraints. Return the complete proposed code when code is requested,
plus a short implementation note. Do not review or test the code, and do not claim it
was executed."""

REVIEWER_INSTRUCTIONS = """You are the Code Review and Debugging Agent. Inspect the user
request and the writer's proposed code. Identify confirmed syntax or logic defects,
possible risks, readability issues, and concrete fixes. Separate confirmed problems
from hypotheses. Do not rewrite the whole solution unless needed to show a correction,
and do not claim execution."""

TESTING_INSTRUCTIONS = """You are the Testing Agent. Design tests for the proposed code and
the user's requirements. Include normal cases, edge cases, expected results where
useful, and scenarios that could expose the review findings. Return runnable tests in
the requested language when enough context is available. Do not claim the tests ran."""


def build_agents(model: Optional[str] = None) -> Dict[str, Agent]:
    """Create the four specialized agents used by the workflow."""
    shared = {"model": model} if model else {}
    return {
        "coordinator": Agent(
            name="Coordinator Agent",
            instructions=COORDINATOR_INSTRUCTIONS,
            **shared,
        ),
        "code_writer": Agent(
            name="Code Writer Agent",
            instructions=CODE_WRITER_INSTRUCTIONS,
            **shared,
        ),
        "reviewer": Agent(
            name="Code Review & Debugging Agent",
            instructions=REVIEWER_INSTRUCTIONS,
            **shared,
        ),
        "tester": Agent(
            name="Testing Agent",
            instructions=TESTING_INSTRUCTIONS,
            **shared,
        ),
    }