"""Static checks on generated code and tests. Nothing here runs the code."""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from .files import module_name
from .runner import EXECUTION_TIMEOUT_SECONDS


MAX_TEST_FUNCTIONS = 6


def check_python_tests(
    code: str, tests: str, module: str, other_files: Optional[Mapping[str, str]] = None
) -> List[str]:
    """Static checks on generated Python tests. Nothing is executed.

    ``code`` is the target file (importable as ``module``); ``other_files`` are the rest of the
    project's files by path, so tests may also import helper modules such as ``utils``.
    Returns human-readable problems: syntax errors, tests that import no project module,
    imported names a project module does not define, and too many or no tests.
    """
    problems: List[str] = []
    sources = {module_name(path): src for path, src in (other_files or {}).items() if path.endswith(".py")}
    sources[module] = code
    trees: Dict[str, Optional[ast.Module]] = {}
    for name, source in sources.items():
        try:
            trees[name] = ast.parse(source)
        except SyntaxError as error:
            trees[name] = None
            if name == module:
                problems.append(f"The proposed code is not valid Python (line {error.lineno}: {error.msg}).")
    try:
        test_tree = ast.parse(tests)
    except SyntaxError as error:
        return problems + [f"The tests are not valid Python (line {error.lineno}: {error.msg})."]

    test_functions = [
        node.name
        for node in ast.walk(test_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    ]
    if not test_functions:
        problems.append("No pytest test functions (named test_...) were found.")
    elif len(test_functions) > MAX_TEST_FUNCTIONS:
        problems.append(
            f"There are {len(test_functions)} test functions; keep only the {MAX_TEST_FUNCTIONS} "
            "or fewer that cover the main functionality."
        )

    def is_project_module(name: str) -> bool:
        # Exact modules, or packages that contain them (``helpers`` for ``helpers.text``).
        return any(known == name or known.startswith(name + ".") for known in sources)

    imports_project = False
    for node in test_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and is_project_module(node.module):
            imports_project = True
            tree = trees.get(node.module)
            if tree is None:
                continue
            defined = _top_level_names(tree)
            for alias in node.names:
                if alias.name != "*" and alias.name not in defined:
                    problems.append(
                        f"`from {node.module} import {alias.name}` fails: `{node.module}` does not "
                        f"define `{alias.name}`."
                    )
        elif isinstance(node, ast.Import) and any(is_project_module(alias.name) for alias in node.names):
            imports_project = True
    if not imports_project:
        problems.append(f"The tests do not import the code under test; use `from {module} import ...`.")
    return problems


def _top_level_names(tree: ast.Module) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def python_syntax_problem(source: str) -> str:
    """Why Python source does not parse, or "" when it does."""
    try:
        ast.parse(source)
    except SyntaxError as error:
        return f"not valid Python (line {error.lineno}: {error.msg})"
    return ""


def javascript_syntax_problem(source: str) -> str:
    """Parse JavaScript with ``node --check`` (it does not run the code). "" when it parses.

    Also "" when Node.js is not installed, because then nothing can be checked.
    """
    with tempfile.TemporaryDirectory(prefix="codementor-check-") as directory:
        target = Path(directory) / "check.js"
        target.write_text(source, encoding="utf-8")
        try:
            completed = subprocess.run(
                ["node", "--check", str(target)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=EXECUTION_TIMEOUT_SECONDS,
                shell=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
    if completed.returncode == 0:
        return ""
    lines = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
    message = next((line for line in lines if "Error" in line), lines[-1] if lines else "syntax error")
    location = next((line.rsplit(":", 1)[-1] for line in lines if line.endswith(tuple("0123456789")) and "check.js:" in line), "")
    return f"not valid JavaScript (line {location}: {message})" if location else f"not valid JavaScript ({message})"
