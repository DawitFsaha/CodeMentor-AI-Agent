from __future__ import annotations

import shutil

import pytest

from codementor_ai.project import (
    is_runnable_source,
    javascript_syntax_problem,
    run_project,
    target_for_language,
    test_target,
)
from codementor_ai.project import ProjectStore

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js on PATH")

MAIN = (
    "const { add } = require('./utils.js');\n"
    "function divide(a, b) {\n  if (b === 0) throw new Error('Cannot divide by zero.');\n  return a / b;\n}\n"
    "module.exports = { add, divide };\n"
    "if (require.main === module) {\n  console.log(`2 + 3 = ${add(2, 3)}`);\n}\n"
)
UTILS = "function add(a, b) {\n  return a + b;\n}\nmodule.exports = { add };\n"
TESTS = (
    "const test = require('node:test');\nconst assert = require('node:assert/strict');\n"
    "const { add, divide } = require('../main.js');\n"
    "test('add', () => assert.equal(add(2, 3), 5));\n"
    "test('divide by zero throws', () => assert.throws(() => divide(1, 0)));\n"
)


def test_chosen_language_decides_the_target_file():
    assert target_for_language("main.py", "JavaScript") == "main.js"
    assert target_for_language("main.js", "JavaScript") == "main.js"
    assert target_for_language("main.py", "Java") == "Main.java"
    assert target_for_language("", "JavaScript") == "main.js"
    assert target_for_language("README.md", "Python") == "main.py"


def test_javascript_tests_live_in_tests_and_require_the_code():
    assert test_target("main.js") == ("tests/main.test.js", "../main.js")
    assert test_target("src/app.js") == ("tests/app.test.js", "../src/app.js")
    assert test_target("Main.java") is None
    assert not is_runnable_source("tests/main.test.js")
    assert is_runnable_source("main.js")


def test_new_projects_start_in_the_selected_language(tmp_path):
    store = ProjectStore(str(tmp_path / "projects"))
    store.create("web", "JavaScript")
    store.create("app", "Java")
    store.create("tool")
    assert list(store.load("web")) == ["main.js"]
    assert list(store.load("app")) == ["Main.java"]
    assert list(store.load("tool")) == ["main.py"]


@needs_node
def test_javascript_project_runs_program_then_node_tests():
    output = run_project({"main.js": MAIN, "utils.js": UTILS, "tests/main.test.js": TESTS}, language="JavaScript")
    program, tests = output.split("\n\n=== Tests")
    assert program == "=== Program: node main.js ===\nExit code: 0\n2 + 3 = 5"
    assert "node --test --test-reporter=spec tests/main.test.js ===\nExit code: 0" in tests
    assert "pass 2" in tests and "fail 0" in tests


@needs_node
def test_javascript_syntax_is_checked_without_running_it():
    assert javascript_syntax_problem(UTILS) == ""
    assert javascript_syntax_problem("def add(a, b):\n    return a + b\n").startswith("not valid JavaScript")
