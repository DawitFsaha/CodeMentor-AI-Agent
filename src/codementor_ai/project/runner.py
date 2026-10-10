"""Bounded local execution of a project: run the program, then its tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import List, Mapping, Optional, Tuple

from .files import parse_project_files, project_json, validate_path
from .languages import (
    JAVA_MAIN,
    LANGUAGE_SUFFIXES,
    is_java,
    is_java_test,
    is_javascript_test,
    is_python,
    is_python_test,
    is_runnable_source,
    java_main_class,
)


EXECUTION_TIMEOUT_SECONDS = 10
# Compiling Java includes JVM start-up, so it gets more time than running a program.
JAVA_COMPILE_TIMEOUT_SECONDS = 30
JAVA_BUILD_DIR = "build"


def run_project(files: Mapping[str, str], entrypoint: str = "", language: str = "") -> str:
    """Run the program, then its tests if it has any, in a temporary copy of the project.

    Python and JavaScript files run directly. Java projects are compiled with ``javac`` first
    and the entry class is then run with ``java``; if compilation fails, only the compiler
    output is shown. Python tests run with pytest and JavaScript tests with ``node --test``.
    Each command runs without a shell and has its own timeout.
    """
    validated = parse_project_files(project_json(files))
    entrypoint = _entrypoint(validated, entrypoint, language)
    if entrypoint not in validated:
        raise ValueError(f"Entrypoint '{entrypoint}' is not in the project.")
    if is_java(entrypoint) and not JAVA_MAIN.search(validated[entrypoint]):
        # A helper class has no main method: run the project's class that does.
        entrypoint = _entrypoint(validated, "", "java")
    if is_java(entrypoint):
        commands = _java_commands(validated, entrypoint)
    else:
        commands = [("Program", _command_for(language, entrypoint), EXECUTION_TIMEOUT_SECONDS)]
    if is_python(language, entrypoint) and any(is_python_test(path) for path in validated):
        commands.append(
            ("Tests", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], EXECUTION_TIMEOUT_SECONDS)
        )
    js_tests = sorted(path for path in validated if is_javascript_test(path))
    if entrypoint.lower().endswith(".js") and js_tests:
        # Node's built-in test runner (node:test), so no npm packages are needed.
        commands.append(("Tests", ["node", "--test", "--test-reporter=spec", *js_tests], EXECUTION_TIMEOUT_SECONDS))
    sections = []
    with tempfile.TemporaryDirectory(prefix="codementor-") as directory:
        root = Path(directory)
        for path, content in validated.items():
            target = root.joinpath(*PurePosixPath(path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for title, command, timeout in commands:
            exit_code, text = _execute(command, root, timeout)
            sections.append(f"=== {title}: {_display(command)} ===\n{text}")
            if title == "Compile" and exit_code != 0:
                sections.append("=== Program ===\nNot run because compilation failed.")
                break
    return "\n\n".join(sections)


def _java_commands(files: Mapping[str, str], entrypoint: str) -> List[Tuple[str, List[str], int]]:
    """Compile all non-test Java sources into ``build/``, then run the entry class."""
    sources = [path for path in files if is_java(path) and not is_java_test(path)]
    if entrypoint not in sources:
        sources.append(entrypoint)
    compile_command = ["javac", "-encoding", "UTF-8", "-d", JAVA_BUILD_DIR, *sources]
    run_command = [
        "java",
        "-Dstdout.encoding=UTF-8",
        "-Dstderr.encoding=UTF-8",
        "-cp",
        JAVA_BUILD_DIR,
        java_main_class(entrypoint, files[entrypoint]),
    ]
    return [
        ("Compile", compile_command, JAVA_COMPILE_TIMEOUT_SECONDS),
        ("Program", run_command, EXECUTION_TIMEOUT_SECONDS),
    ]


def _execute(command: List[str], root: Path, timeout: int = EXECUTION_TIMEOUT_SECONDS) -> Tuple[Optional[int], str]:
    """Run one command; returns its exit code (None if it did not finish) and a report."""
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            # No keyboard is attached: input() raises EOFError instead of hanging.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"Timed out after {timeout} seconds."
    except FileNotFoundError:
        hint = " Install a JDK (Java 11 or newer) and add it to PATH." if command[0] in ("javac", "java") else ""
        return None, f"Could not start '{command[0]}'. Is it installed and on PATH?{hint}"
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, f"Exit code: {completed.returncode}\n{output or '(no output)'}"


def _display(command: List[str]) -> str:
    """Readable command line, e.g. 'python main.py' instead of the interpreter's full path."""
    program = "python" if command[0] == sys.executable else command[0]
    return " ".join([program, *command[1:]])


def _entrypoint(files: Mapping[str, str], entrypoint: str, language: str) -> str:
    if entrypoint:
        return validate_path(entrypoint)
    preferred_suffix = LANGUAGE_SUFFIXES.get(language.lower().strip(), ".py")
    # Test files are never run as the program itself.
    runnable = [path for path in files if is_runnable_source(path)]
    candidates = [path for path in runnable if PurePosixPath(path).suffix.lower() == preferred_suffix]
    # Fall back to any runnable file, e.g. a Java-only project with "Python" selected.
    candidates = candidates or runnable
    java = [path for path in candidates if is_java(path) and JAVA_MAIN.search(files[path])]
    if java:
        return min(java, key=lambda path: (PurePosixPath(path).name != "Main.java", path))
    for preferred in ("main.py", "index.py", "main.js", "index.js"):
        if preferred in candidates:
            return preferred
    if candidates:
        return min(candidates)
    raise ValueError("No runnable source file exists in the project.")


def _command_for(language: str, entrypoint: str) -> List[str]:
    normalized = language.lower().strip()
    suffix = Path(entrypoint).suffix.lower()
    if suffix == ".py" or (not suffix and normalized in ("python", "py")):
        return [sys.executable, *PurePosixPath(entrypoint).parts]
    if suffix == ".js" or (not suffix and normalized in ("javascript", "js")):
        return ["node", *PurePosixPath(entrypoint).parts]
    raise ValueError("Run supports Python (.py), JavaScript (.js), and Java (.java) files.")
