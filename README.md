# CodeMentor AI

CodeMentor AI is a four-agent mini coding copilot built with the OpenAI Agents SDK. It
comes with a local Gradio IDE where the agents write, review, and test code for your
project, and you approve every change before it is saved. It implements the goals and
agent roles in the [project plan](documentation/Project%20Plan.pdf).

**Architecture and workflow diagrams:** [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md)

## Features

- **Four collaborating agents** run in a sequential pipeline: Coordinator, Code Writer,
  Code Review & Debugging, and Testing.
- **Web search for current facts.** The Code Writer and Reviewer can search the web for
  current library APIs, deprecations, error messages, and package security advisories, and
  cite their sources.
- **Human-in-the-loop review.** Generated code and tests are shown as diffs. You can edit,
  accept, or reject each file; nothing is written until you accept.
- **Gradio IDE.**
  - Explorer for all projects: open files, create files and folders in the selected
    folder, and delete with confirmation.
  - Scrollable code editor with autosave.
  - Chat assistant whose history is kept per project.
  - **Run project** with a 10-second timeout.
- **Memory.** Agent session memory and chat history are stored per project in SQLite.
- **Guardrails.** Request size limits, secret redaction, safe file paths, untrusted-context
  handling, and non-interactive code (no `input()`).

## How it works

Each request follows the pattern from the project plan:

```text
User Request -> Coordinator -> Code Writer -> Review & Debugging -> Testing -> Coordinator
```

| Agent | Responsibility | Tools |
| --- | --- | --- |
| Coordinator Agent | Writes a routing brief, then assembles the final answer with implementation, review, and test sections. | — |
| Code Writer Agent | Creates or modifies code from the requirements. | Web search |
| Code Review & Debugging Agent | Separates confirmed defects from possible risks and suggests fixes. | Web search |
| Testing Agent | Writes normal and edge-case tests. | — |

Later agents receive the earlier outputs, and each request makes five model calls plus any
web searches. Agents are instructed not to claim that code ran without evidence, not to
expose secrets, and to treat session history and web content as untrusted.

In the IDE, the Code Writer's code and the Testing Agent's tests become proposals for the
open file and `tests/test_<name>.py`. You review them before anything is saved. See
[ARCHITECTURE.md](documentation/ARCHITECTURE.md) for sequence diagrams, the data model,
and the guardrail details.

## Setup

Requirements: Python 3.9 or newer, an OpenAI API key, and Node.js only if you want to run
JavaScript projects. Run these commands from the project root in PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The editable install reads all dependencies from `pyproject.toml` and adds the
`codementor` command to `.venv`.

Create a `.env` file in the project root (copy `.env.example`):

```dotenv
OPENAI_API_KEY=your-api-key
```

The app loads `.env` automatically. Never commit `.env` or share the API key.

Run the automated tests (they use fake agents, so they need no API key):

```powershell
python -m pytest -q
```

Expected output: `13 passed`. Note that `tests/test_workflow.py` writes two sample
messages to `codementor.db` in the current folder.

## Using the IDE

```powershell
codementor --ui
```

Open the address it prints (normally <http://127.0.0.1:7860>). If that port is busy, Gradio
uses the next free one, so stop an old server with **Ctrl+C** before starting a new one.

| Area | How to use it |
| --- | --- |
| **Explorer** | Click a file to open it; click a folder to expand it and make it the target for new items. **＋** creates a project, **＋▤** a file, **＋□** a folder. The trash icon deletes after a second confirming click. |
| **Editor** | Edits autosave as you type. |
| **Assistant** | Choose the language, type a request, and press **Enter** (**Shift+Enter** adds a line). The open file and the project's files are sent as context. Each project keeps its own chat; **Clear chat** clears it. |
| **Review proposed changes** | Appears below the editor after a request. For each file, check the **Diff**, optionally change it in **Edit before saving**, then **Accept** or **Reject**, or use **Accept all** / **Reject all**. |
| **Run project** | Runs `pytest` if the project has `test_*.py` files, otherwise `main.py` (or `main.js`), and shows the output. |

Projects are stored under `projects/` and conversations in `codementor.db`, both in the
folder where you start the app.

## Command line

Run one request without the IDE:

```powershell
codementor "Write a Python function that adds two numbers" --language Python
codementor "Review this function" --language Python --code "def add(a, b): return a + b"
```

| Option | Purpose |
| --- | --- |
| `--language` | Programming language for the request |
| `--code` | Existing code to review or modify |
| `--session-id` | Conversation session to continue (default `default`) |
| `--database` | SQLite memory file (default `codementor.db`) |
| `--ui` | Launch the Gradio IDE instead |

The command prints the Coordinator's final answer. It does not change any files.

## Project structure

```text
CodeMentor-AI-Agent/
├── src/codementor_ai/
│   ├── agents.py        # Agent definitions, instructions, and web search tools
│   ├── workflow.py      # Sequential multi-agent workflow and request/result types
│   ├── guardrails.py    # Input limits and secret redaction
│   ├── memory.py        # SQLite agent memory and per-project chat history
│   ├── project.py       # File validation, Explorer listing, bounded runner
│   ├── workspace.py     # Project storage under projects/
│   ├── ui.py            # Gradio IDE with human-in-the-loop review
│   ├── cli.py           # codementor command
│   └── assets/          # UI icons
├── tests/               # Pytest suite (fake agents, no API calls)
├── documentation/       # Project plan, course brief, ARCHITECTURE.md
├── projects/            # Your IDE projects (created at runtime)
├── codementor.db        # SQLite memory (created at runtime)
├── .env.example
└── pyproject.toml
```

## Costs, privacy, and safety

- Every request makes five model calls; web searches are billed separately.
- Your request, the open file, and the project's files are sent to OpenAI. Common
  credential formats are redacted first, but do not put real secrets in project files.
- **Run project** executes code with your user's permissions. A temporary copy and a
  timeout limit accidents, but it is not a security sandbox. The server only listens on
  `127.0.0.1`.

## Scope and known limitations

- Memory is local SQLite. There is no vector store or retrieval-augmented generation
  (RAG) yet; external knowledge comes from hosted web search.
- All five agent steps always run, including when you only want a review.
- The assistant proposes changes to the open file and one test file per request.
- Pending proposals are lost if you reload the page.
- There is no authentication or multi-user hosting.
