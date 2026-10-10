"""The specialized CodeMentor AI agents, one module per agent."""

from __future__ import annotations

from typing import Dict, Optional

from agents import Agent

from .code_writer import build_code_writer
from .coordinator import build_coordinator
from .reviewer import build_reviewer
from .tester import build_tester, build_tester_without_sandbox


def build_agents(model: Optional[str] = None) -> Dict[str, Agent]:
    """Create the agents used by the workflow, keyed by their role in it."""
    shared = {"model": model} if model else {}
    return {
        "coordinator": build_coordinator(**shared),
        "code_writer": build_code_writer(**shared),
        "reviewer": build_reviewer(**shared),
        "tester": build_tester(**shared),
        "tester_no_sandbox": build_tester_without_sandbox(**shared),
    }


__all__ = ["build_agents"]
