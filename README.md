# CodeMentor AI

CodeMentor AI is a multi-agent coding assistant built with the OpenAI Agents SDK. You
describe a coding task in a local Gradio IDE, and four AI agents work together to write the
code, review it, and write tests for it. You see the proposed changes as a diff and decide
whether to save them.

## The agents

| Agent | What it does |
| --- | --- |
| **Coordinator** | Understands the request, plans the work, and combines the results into one answer. |
| **Code Writer** | Writes or changes the code. Can search the web for current library docs. |
| **Code Reviewer & Debugger** | Finds bugs and risks and suggests fixes. Can search the web for deprecations and security issues. |
| **Tester** | Writes a few focused tests for the main functionality and runs them in OpenAI's hosted sandbox before answering, so they pass. |

## How a request flows

```text
You type a request
   │
   ▼
Coordinator  ──►  Code Writer  ──►  Reviewer  ──►  Tester  ──►  Coordinator
 (plan)            (code)            (review)        (tests)       (final answer)
   │
   ▼
Answer appears in the chat
   │
   ▼
You review the proposed code and tests as diffs ──► Accept (saved) or Reject (discarded)
   │
   ▼
Run project: runs your program, then its tests, and shows the output
```

- Each agent receives the earlier agents' results.
- Conversations are saved per project in SQLite (`codementor.db`), so the agents remember
  earlier requests.
- Nothing the agents generate is written to your files until you accept it.

## Quick start

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env      # then set OPENAI_API_KEY in .env
codementor --ui                  # opens the IDE at http://127.0.0.1:7860
codementor --ui --port 8100      # use another port if 7860 is busy or reserved
```

Run the tests with `python -m pytest -q`. They use fake agents, so no API key is needed.

**Languages:** projects can be written in Python, JavaScript (needs Node.js), or Java (needs a
JDK with `javac` and `java` on PATH).

- Pick the language in the dropdown before clicking **＋**: a new project starts with
  `main.py`, `main.js`, or `Main.java`.
- The dropdown follows the open file. If you change it to another language, the assistant
  writes a new file in that language (for example `main.js` next to `main.py`) instead of
  rewriting the open one.
- JavaScript runs with Node.js as CommonJS (`require` / `module.exports`); tests use Node's
  built-in `node:test` and run as `tests/<name>.test.js`.
- Java is compiled with plain `javac`, so it can use the standard library only.
- Generated tests are run in the sandbox before you see them only for Python.

You can also make a single request from the terminal:

```powershell
codementor "Write a Python function that adds two numbers" --language Python
```

## Learn more

[documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) has the architecture
diagrams, guardrails, data model, and known limitations.
