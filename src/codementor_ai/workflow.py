"""Sequential collaboration pattern for the CodeMentor AI agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agents import Runner

from .agents import build_agents


@dataclass(frozen=True)
class CodeMentorRequest:
    """The user input shared across the workflow."""

    task: str
    language: str = ""
    code: str = ""

    def as_prompt(self) -> str:
        language = self.language or "not specified"
        code = self.code or "No existing code supplied."
        return f"Task:\n{self.task}\n\nLanguage: {language}\n\nExisting code:\n{code}"


@dataclass(frozen=True)
class CodeMentorResult:
    """All outputs produced by one completed collaboration run."""

    routing_brief: str
    code: str
    review: str
    tests: str
    final_response: str


class CodeMentorWorkflow:
    """Run Coordinator -> Writer -> Reviewer -> Tester -> Coordinator."""

    def __init__(
        self,
        agents: Optional[Dict[str, Any]] = None,
        runner: Any = Runner,
    ) -> None:
        self.agents = agents or build_agents()
        self.runner = runner

    async def _run(self, agent_name: str, prompt: str) -> str:
        result = await self.runner.run(self.agents[agent_name], prompt)
        return result.final_output

    async def run(self, request: CodeMentorRequest) -> CodeMentorResult:
        original = request.as_prompt()
        routing_brief = await self._run("coordinator", original)
        code = await self._run(
            "code_writer",
            f"Coordinator routing brief:\n{routing_brief}\n\n{original}",
        )
        review = await self._run(
            "reviewer",
            f"Original request:\n{original}\n\nProposed code:\n{code}",
        )
        tests = await self._run(
            "tester",
            f"Original request:\n{original}\n\nProposed code:\n{code}\n\nReview:\n{review}",
        )
        final_response = await self._run(
            "coordinator",
            "Assemble the final response from these workflow outputs. Include clear "
            "sections for implementation, review, and tests. State that code and tests "
            "were not executed unless execution evidence is present.\n\n"
            f"Original request:\n{original}\n\nRouting brief:\n{routing_brief}\n\n"
            f"Implementation:\n{code}\n\nReview:\n{review}\n\nTests:\n{tests}",
        )
        return CodeMentorResult(routing_brief, code, review, tests, final_response)