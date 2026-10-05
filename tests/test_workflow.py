from __future__ import annotations

import asyncio

from codementor_ai.workflow import CodeMentorRequest, CodeMentorWorkflow


class FakeResult:
    def __init__(self, final_output: str) -> None:
        self.final_output = final_output


class RecordingRunner:
    calls = []

    @classmethod
    async def run(cls, agent, prompt):
        cls.calls.append((agent, prompt))
        output = {
            "coordinator": "route the request",
            "code_writer": "def greet(): return 'hello'",
            "reviewer": "No confirmed issues found.",
            "tester": "assert greet() == 'hello'",
        }[agent]
        return FakeResult(output)


def test_workflow_runs_agents_in_required_order_and_returns_all_outputs(monkeypatch):
    monkeypatch.setattr(RecordingRunner, "calls", [])
    agents = {
        "coordinator": "coordinator",
        "code_writer": "code_writer",
        "reviewer": "reviewer",
        "tester": "tester",
    }
    workflow = CodeMentorWorkflow(agents=agents, runner=RecordingRunner)

    result = asyncio.run(
        workflow.run(CodeMentorRequest(task="Write a greeting function", language="Python"))
    )

    assert [agent for agent, _ in RecordingRunner.calls] == [
        "coordinator",
        "code_writer",
        "reviewer",
        "tester",
        "coordinator",
    ]
    assert "route the request" in RecordingRunner.calls[1][1]
    assert "def greet" in RecordingRunner.calls[2][1]
    assert "No confirmed issues" in RecordingRunner.calls[3][1]
    assert result.final_response == "route the request"
    assert result.tests == "assert greet() == 'hello'"