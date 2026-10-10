from __future__ import annotations

import asyncio

from agents import CodeInterpreterTool

from codementor_ai.agents import build_agents
from codementor_ai.memory import SQLiteMemory
from codementor_ai.project import MAX_TEST_FUNCTIONS, check_python_tests, python_test_target
from codementor_ai.workflow import CodeMentorRequest, CodeMentorWorkflow, verify_sandbox_claim


CODE = "def add(a, b):\n    return a + b\n"


def test_python_test_target_matches_saved_location_and_import():
    assert python_test_target("main.py") == ("tests/test_main.py", "main")
    assert python_test_target("src/app.py") == ("tests/test_app.py", "src.app")
    assert python_test_target("test_utils.py") == ("tests/test_utils.py", "test_utils")


def test_check_accepts_a_small_valid_test_file():
    tests = "from main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    assert check_python_tests(CODE, tests, "main") == []


def test_check_reports_common_failures_without_running_anything():
    wrong_language = "// CalculatorTest.java\npublic class CalculatorTest {}\n"
    assert "not valid Python" in check_python_tests(CODE, wrong_language, "main")[0]

    missing_name = "from main import subtract\n\ndef test_subtract():\n    assert subtract(3, 1) == 2\n"
    assert any("does not define `subtract`" in p for p in check_python_tests(CODE, missing_name, "main"))

    no_import = "def test_add():\n    assert 1 + 1 == 2\n"
    assert any("do not import" in p for p in check_python_tests(CODE, no_import, "main"))

    too_many = "from main import add\n" + "".join(
        f"\ndef test_{i}():\n    assert add({i}, 0) == {i}\n" for i in range(MAX_TEST_FUNCTIONS + 2)
    )
    assert any("keep only" in p for p in check_python_tests(CODE, too_many, "main"))


def test_tester_runs_tests_in_the_hosted_sandbox_and_keeps_them_minimal():
    tester = build_agents()["tester"]
    assert any(isinstance(tool, CodeInterpreterTool) for tool in tester.tools)
    instructions = " ".join(tester.instructions.split())
    assert "never more than 6" in instructions
    assert "expose the review findings" not in instructions


class Result:
    def __init__(self, text: str) -> None:
        self.final_output = text


class RetryRunner:
    """The first Tester answer imports a missing name; the retry fixes it."""

    calls = []

    @classmethod
    async def run(cls, agent, prompt):
        cls.calls.append((agent, prompt))
        if agent == "code_writer":
            return Result("```python\n" + CODE + "```")
        if agent == "tester":
            first = sum(1 for name, _ in cls.calls if name == "tester") == 1
            name = "subtract" if first else "add"
            return Result(f"```python\nfrom main import {name}\n\ndef test_it():\n    assert {name}(1, 1) == 2\n```")
        return Result("ok")


def test_workflow_gives_test_setup_and_retries_tests_with_static_problems(tmp_path, monkeypatch):
    monkeypatch.setattr(RetryRunner, "calls", [])
    workflow = CodeMentorWorkflow(
        agents={name: name for name in ("coordinator", "code_writer", "reviewer", "tester")},
        runner=RetryRunner,
        memory=SQLiteMemory(str(tmp_path / "memory.db")),
    )
    result = asyncio.run(workflow.run(CodeMentorRequest("Add numbers", language="Python", entrypoint="main.py")))

    tester_prompts = [prompt for agent, prompt in RetryRunner.calls if agent == "tester"]
    assert len(tester_prompts) == 2
    assert "Import the code with `from main import ...`" in tester_prompts[0]
    assert "does not define `subtract`" in tester_prompts[1]
    assert "from main import add" in result.tests


class Item:
    def __init__(self, kind: str) -> None:
        self.raw_item = type("Raw", (), {"type": kind})()


def test_sandbox_claim_is_kept_only_when_the_tool_really_ran():
    answer = "```python\ndef test_x():\n    assert True\n```\nExecuted in sandbox: 1 passed"
    assert verify_sandbox_claim(answer, [Item("code_interpreter_call"), Item("message")]) == answer
    rewritten = verify_sandbox_claim(answer, [Item("message")])
    assert "Executed in sandbox" not in rewritten
    assert rewritten.endswith("Not executed (no sandbox run was recorded).")
