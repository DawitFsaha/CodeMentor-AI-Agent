"""Validated project files and bounded local execution."""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Optional, Tuple


MAX_PROJECT_FILES = 50
MAX_FILE_SIZE = 50_000
EXECUTION_TIMEOUT_SECONDS = 10
# Compiling Java includes JVM start-up, so it gets more time than running a program.
JAVA_COMPILE_TIMEOUT_SECONDS = 30
JAVA_BUILD_DIR = "build"
MAX_TEST_FUNCTIONS = 6


def extract_code_block(text: str) -> str:
    """First fenced code block in an agent answer, or "" when the answer contains no code."""
    matches = re.findall(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```", text or "", re.DOTALL)
    return matches[0].strip() + "\n" if matches and matches[0].strip() else ""


def python_test_target(entrypoint: str) -> Tuple[str, str]:
    """Where generated tests for a Python file are saved, and the module they must import.

    For ``main.py`` this is ``("tests/test_main.py", "main")``; for ``src/app.py`` it is
    ``("tests/test_app.py", "src.app")``. Tests run with ``python -m pytest`` from the
    project root, so the module path is relative to that root.
    """
    path = PurePosixPath(entrypoint or "main.py")
    stem = path.stem[len("test_"):] if path.stem.startswith("test_") else path.stem
    return f"tests/test_{stem}.py", module_name(str(path))


def module_name(path: str) -> str:
    """Import name of a project file: ``src/app.py`` -> ``src.app``."""
    return ".".join(PurePosixPath(path).with_suffix("").parts)


_FENCE = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)
_FILE_LABEL = re.compile(r"File:\**\s*`?([A-Za-z0-9_./ -]+?)`?\s*\**\s*$")


def extract_files(text: str, default_path: str) -> Dict[str, str]:
    """Files proposed in an agent answer, keyed by project-relative path.

    A fenced code block belongs to the path on the line just above it, written as
    ``File: utils.py`` (bold or back-ticked forms are accepted). The first block without such
    a line belongs to ``default_path``; later unlabeled blocks (usage examples) are ignored.
    Invalid or unsafe paths are skipped.
    """
    files: Dict[str, str] = {}
    default_taken = False
    for match in _FENCE.finditer(text or ""):
        body = match.group(1).strip()
        if not body:
            continue
        lines_before = text[: match.start()].rstrip().split("\n")
        label = _FILE_LABEL.search(lines_before[-1]) if lines_before else None
        if label:
            path = label.group(1).strip()
        elif not default_taken:
            path, default_taken = default_path, True
        else:
            continue
        try:
            path = _validate_path(path)
        except ValueError:
            continue
        files.setdefault(path, body + "\n")
    return files


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


def parse_project_files(value: str) -> Dict[str, str]:
    """Parse the UI's JSON file map and reject unsafe or oversized projects."""
    try:
        files = json.loads(value or "{}")
    except json.JSONDecodeError as error:
        raise ValueError(f"Project files must be valid JSON: {error.msg}.") from error
    if not isinstance(files, dict):
        raise ValueError("Project files must be a JSON object mapping paths to text.")
    if not files:
        raise ValueError("Add at least one project file.")
    if len(files) > MAX_PROJECT_FILES:
        raise ValueError(f"Projects may contain at most {MAX_PROJECT_FILES} files.")

    validated: Dict[str, str] = {}
    for raw_path, content in files.items():
        path = _validate_path(raw_path)
        if not isinstance(content, str):
            raise ValueError(f"File '{path}' must contain text.")
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"File '{path}' exceeds {MAX_FILE_SIZE} characters.")
        validated[path] = content
    return dict(sorted(validated.items()))


def project_json(files: Mapping[str, str]) -> str:
    return json.dumps(dict(sorted(files.items())), indent=2)


def project_tree(files: Mapping[str, str]) -> str:
    lines = ["### PROJECT"]
    for path in sorted(files):
        depth = len(PurePosixPath(path).parts) - 1
        lines.append(f"{'  ' * depth}- `{path}`")
    return "\n".join(lines)


HIDDEN_NAMES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}


@dataclass(frozen=True)
class TreeEntry:
    """One visible row of the Explorer sidebar."""

    path: str
    relative: str
    label: str
    is_dir: bool
    depth: int


def explorer_entries(root_dir: str, expanded: Iterable[str] = ()) -> List[TreeEntry]:
    """List the visible directory tree, folders first, as Explorer rows.

    ``path`` is absolute and ``relative`` is relative to ``root_dir``. Only folders
    whose relative path is in ``expanded`` show their children.
    """
    root = Path(root_dir)
    open_folders = set(expanded)
    rows: List[TreeEntry] = []

    def walk(directory: Path, depth: int) -> None:
        entries = sorted(
            (entry for entry in directory.iterdir() if entry.name not in HIDDEN_NAMES),
            key=lambda entry: (entry.is_file(), entry.name.lower()),
        )
        indent = "    " * depth
        for entry in entries:
            relative = entry.relative_to(root).as_posix()
            if entry.is_dir():
                is_open = relative in open_folders
                marker = "▾ 📂" if is_open else "▸ 📁"
                rows.append(TreeEntry(str(entry), relative, f"{indent}{marker} {entry.name}", True, depth))
                if is_open:
                    walk(entry, depth + 1)
            else:
                label = f"{indent}   📄 {entry.name}"
                rows.append(TreeEntry(str(entry), relative, label, False, depth))

    if root.is_dir():
        walk(root, 0)
    return rows


def run_project(files: Mapping[str, str], entrypoint: str = "", language: str = "") -> str:
    """Run the program, then its pytest suite if it has one, in a temporary copy of the project.

    Python and JavaScript files run directly. Java projects are compiled with ``javac`` first
    and the entry class is then run with ``java``; if compilation fails, only the compiler
    output is shown. Each command runs without a shell and has its own timeout.
    """
    validated = parse_project_files(project_json(files))
    entrypoint = _entrypoint(validated, entrypoint, language)
    if entrypoint not in validated:
        raise ValueError(f"Entrypoint '{entrypoint}' is not in the project.")
    if _is_java(entrypoint) and not _JAVA_MAIN.search(validated[entrypoint]):
        # A helper class has no main method: run the project's class that does.
        entrypoint = _entrypoint(validated, "", "java")
    if _is_java(entrypoint):
        commands = _java_commands(validated, entrypoint)
    else:
        commands = [("Program", _command_for(language, entrypoint), EXECUTION_TIMEOUT_SECONDS)]
    if _is_python(language, entrypoint) and any(_is_test_file(path) for path in validated):
        commands.append(
            ("Tests", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], EXECUTION_TIMEOUT_SECONDS)
        )
    js_tests = sorted(path for path in validated if _is_js_test(path))
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
    sources = [path for path in files if _is_java(path) and not _is_java_test(path)]
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


def java_main_class(path: str, source: str) -> str:
    """Fully qualified class name for a Java file: its ``package`` plus the file name."""
    package = _JAVA_PACKAGE.search(source)
    name = PurePosixPath(path).stem
    return f"{package.group(1)}.{name}" if package else name


_JAVA_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_JAVA_MAIN = re.compile(r"\bstatic\s+void\s+main\s*\(")


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


def _is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _is_java(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() == ".java"


def _is_java_test(path: str) -> bool:
    """JUnit-style test sources are not compiled: running them needs the JUnit library."""
    parts = PurePosixPath(path).parts
    return _is_java(path) and (PurePosixPath(path).stem.endswith("Test") or "test" in parts[:-1] or "tests" in parts[:-1])


def is_runnable_source(path: str) -> bool:
    """Whether a file can be run as a program (Python, JavaScript, or Java, but not a test)."""
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".java":
        return not _is_java_test(path)
    if suffix == ".js":
        return not _is_js_test(path)
    return suffix == ".py" and not _is_test_file(path)


def _is_python(language: str, entrypoint: str) -> bool:
    return Path(entrypoint).suffix.lower() == ".py" or (
        not Path(entrypoint).suffix and language.lower().strip() in ("python", "py")
    )


def _validate_path(raw_path: object) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("File paths must be non-empty strings.")
    path = PurePosixPath(raw_path.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or str(path) != raw_path.replace("\\", "/"):
        raise ValueError(f"Unsafe project path: {raw_path}")
    return str(path)


LANGUAGE_SUFFIXES = {"python": ".py", "py": ".py", "javascript": ".js", "js": ".js", "java": ".java"}


SOURCE_SUFFIXES = (".py", ".js", ".java")
DEFAULT_ENTRY = {".py": "main.py", ".js": "main.js", ".java": "Main.java"}
SUFFIX_LANGUAGE = {".py": "Python", ".js": "JavaScript", ".java": "Java"}


def target_for_language(open_relative: str, language: str) -> str:
    """The file the agents write for a request.

    Normally the open source file. When the chosen language differs from the open file's
    language, a sibling file in the chosen language is used instead (``main.py`` with
    JavaScript selected becomes ``main.js``), so the open file is never rewritten in another
    language. Without an open source file, the language's default entry file is used.
    """
    suffix = LANGUAGE_SUFFIXES.get(language.lower().strip())
    path = PurePosixPath(open_relative) if open_relative else None
    if path is not None and path.suffix.lower() in SOURCE_SUFFIXES:
        if suffix is None or path.suffix.lower() == suffix:
            return open_relative
        return str(path.with_name(_stem_for(path.stem, suffix) + suffix))
    return DEFAULT_ENTRY.get(suffix or ".py", "main.py")


def _stem_for(stem: str, suffix: str) -> str:
    """File name conventions: Java uses PascalCase class names, Python snake_case."""
    if suffix == ".java":
        return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\-\s]+", stem) if part) or "Main"
    if suffix == ".py":
        return re.sub(r"(?<!^)(?=[A-Z])", "_", stem).lower()
    return stem[:1].lower() + stem[1:]


def test_target(entrypoint: str) -> Optional[Tuple[str, str]]:
    """Where generated tests for a file are saved, and how they load the code under test.

    Python: ``("tests/test_main.py", "main")`` (the module to import). JavaScript:
    ``("tests/main.test.js", "../main.js")`` (the path for ``require``). Other languages have
    no automatically run tests, so ``None``.
    """
    path = PurePosixPath(entrypoint)
    if path.suffix.lower() == ".py":
        return python_test_target(entrypoint)
    if path.suffix.lower() == ".js":
        return f"tests/{path.stem}.test.js", f"../{path}"
    return None


# Keep pytest from collecting this helper as a test when the module is imported in tests.
test_target.__test__ = False  # type: ignore[attr-defined]


def _is_js_test(path: str) -> bool:
    """Tests for Node's built-in runner: *.test.js / *.spec.js, or .js files in a test folder."""
    pure = PurePosixPath(path)
    if pure.suffix.lower() != ".js":
        return False
    return pure.name.endswith((".test.js", ".spec.js")) or bool({"test", "tests"} & set(pure.parts[:-1]))


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


def _entrypoint(files: Mapping[str, str], entrypoint: str, language: str) -> str:
    if entrypoint:
        return _validate_path(entrypoint)
    preferred_suffix = LANGUAGE_SUFFIXES.get(language.lower().strip(), ".py")
    # Test files are never run as the program itself.
    runnable = [path for path in files if is_runnable_source(path)]
    candidates = [path for path in runnable if PurePosixPath(path).suffix.lower() == preferred_suffix]
    # Fall back to any runnable file, e.g. a Java-only project with "Python" selected.
    candidates = candidates or runnable
    java = [path for path in candidates if _is_java(path) and _JAVA_MAIN.search(files[path])]
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
