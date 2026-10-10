from __future__ import annotations

from codementor_ai.memory import SQLiteMemory
from codementor_ai.project import check_python_tests, extract_files, run_project
from codementor_ai.ui import _name_problem


def test_extract_files_reads_labelled_blocks_and_skips_examples():
    answer = (
        "Split into a helper.\n\n"
        "```python\nfrom utils import add\nprint(add(1, 2))\n```\n\n"
        "File: `utils.py`\n```python\ndef add(a, b):\n    return a + b\n```\n\n"
        "Run it:\n```bash\npython main.py\n```"
    )
    assert extract_files(answer, "main.py") == {
        "main.py": "from utils import add\nprint(add(1, 2))\n",
        "utils.py": "def add(a, b):\n    return a + b\n",
    }


def test_extract_files_rejects_paths_outside_the_project():
    assert extract_files("File: ../evil.py\n```python\nx = 1\n```", "main.py") == {}


def test_tests_may_import_helper_modules_of_the_project():
    others = {"utils.py": "def add(a, b):\n    return a + b\n", "helpers/text.py": "def shout(s):\n    return s\n"}
    tests = "from utils import add\nfrom helpers.text import shout\n\ndef test_add():\n    assert add(1, 1) == 2\n"
    assert check_python_tests("from utils import add\n", tests, "main", others) == []
    wrong = "from utils import sub\n\ndef test_sub():\n    assert sub(1, 1) == 0\n"
    assert check_python_tests("", wrong, "main", others) == ["`from utils import sub` fails: `utils` does not define `sub`."]


def test_main_file_can_import_from_other_project_files():
    files = {
        "main.py": "from utils import add\nfrom helpers.text import shout\nprint(add(2, 3), shout('hi'))\n",
        "utils.py": "def add(a, b):\n    return a + b\n",
        "helpers/text.py": "def shout(s):\n    return s.upper()\n",
    }
    assert run_project(files, language="Python").endswith("Exit code: 0\n5 HI")


def test_rename_name_rules():
    assert _name_problem("utils.py", is_project=False) == ""
    assert _name_problem("my-app", is_project=True) == ""
    assert "contain" in _name_problem("a/b", is_project=False)
    assert "empty" in _name_problem("", is_project=False)
    assert "letters" in _name_problem("my app", is_project=True)


def test_renaming_a_project_keeps_its_chat_and_agent_memory(tmp_path):
    memory = SQLiteMemory(str(tmp_path / "memory.db"))
    memory.add_chat("demo", "user", "hello")
    memory.add("project:demo", "user", "prompt")
    memory.rename_project("demo", "calc")
    assert [m.content for m in memory.chat_history("calc")] == ["hello"]
    assert memory.chat_history("demo") == []
    assert [m.content for m in memory.recent("project:calc")] == ["prompt"]
