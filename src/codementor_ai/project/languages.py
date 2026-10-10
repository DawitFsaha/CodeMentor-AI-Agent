"""Language rules: which file a request targets, where tests go, and what can run."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Optional, Tuple

from .files import module_name


LANGUAGE_SUFFIXES = {"python": ".py", "py": ".py", "javascript": ".js", "js": ".js", "java": ".java"}
SOURCE_SUFFIXES = (".py", ".js", ".java")
DEFAULT_ENTRY = {".py": "main.py", ".js": "main.js", ".java": "Main.java"}
SUFFIX_LANGUAGE = {".py": "Python", ".js": "JavaScript", ".java": "Java"}

JAVA_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
JAVA_MAIN = re.compile(r"\bstatic\s+void\s+main\s*\(")


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


def python_test_target(entrypoint: str) -> Tuple[str, str]:
    """Where generated tests for a Python file are saved, and the module they must import.

    For ``main.py`` this is ``("tests/test_main.py", "main")``; for ``src/app.py`` it is
    ``("tests/test_app.py", "src.app")``. Tests run with ``python -m pytest`` from the
    project root, so the module path is relative to that root.
    """
    path = PurePosixPath(entrypoint or "main.py")
    stem = path.stem[len("test_"):] if path.stem.startswith("test_") else path.stem
    return f"tests/test_{stem}.py", module_name(str(path))


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


def is_python(language: str, entrypoint: str) -> bool:
    return Path(entrypoint).suffix.lower() == ".py" or (
        not Path(entrypoint).suffix and language.lower().strip() in ("python", "py")
    )


def is_java(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() == ".java"


def is_python_test(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def is_javascript_test(path: str) -> bool:
    """Tests for Node's built-in runner: *.test.js / *.spec.js, or .js files in a test folder."""
    pure = PurePosixPath(path)
    if pure.suffix.lower() != ".js":
        return False
    return pure.name.endswith((".test.js", ".spec.js")) or bool({"test", "tests"} & set(pure.parts[:-1]))


def is_java_test(path: str) -> bool:
    """JUnit-style test sources are not compiled: running them needs the JUnit library."""
    parts = PurePosixPath(path).parts
    return is_java(path) and (PurePosixPath(path).stem.endswith("Test") or "test" in parts[:-1] or "tests" in parts[:-1])


def is_runnable_source(path: str) -> bool:
    """Whether a file can be run as a program (Python, JavaScript, or Java, but not a test)."""
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".java":
        return not is_java_test(path)
    if suffix == ".js":
        return not is_javascript_test(path)
    return suffix == ".py" and not is_python_test(path)


def java_main_class(path: str, source: str) -> str:
    """Fully qualified class name for a Java file: its ``package`` plus the file name."""
    package = JAVA_PACKAGE.search(source)
    name = PurePosixPath(path).stem
    return f"{package.group(1)}.{name}" if package else name
