# CodeMentor AI

CodeMentor AI is a four-agent mini coding copilot built with the OpenAI Agents SDK.
It implements the tasks and deliverables defined on the project plan (documentation/Projet Plan).

## Agents

- **Coordinator Agent:** extracts the task, routes the work, and synthesizes the final response.
- **Code Writer Agent:** creates or modifies code from the requirements.
- **Code Review & Debugging Agent:** identifies confirmed defects, possible risks, and fixes.
- **Testing Agent:** produces normal and edge-case tests with expected results where useful.

## Collaboration Pattern

Each request follows this explicit sequential pattern:

```text
User Request -> Coordinator -> Code Writer -> Review & Debugging -> Testing -> Coordinator
```

The later agents receive the relevant earlier outputs. The final Coordinator response
contains implementation, review, and testing sections. Agents are instructed not to
claim execution without evidence and not to expose secrets.

## Setup And Run

Run these commands from the project root in PowerShell.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The editable install reads all dependencies, including the tested OpenAI Agents SDK
versions and pytest, from `pyproject.toml`. It also makes the `codementor` command
available inside `.venv`.

Create a `.env` file in the project root. Copy `.env.example` or create it manually:

```dotenv
OPENAI_API_KEY=your-api-key
```

The CLI loads `.env` automatically. Never commit `.env` or share the API key.

Run the automated test before making an API request:

```powershell
python -m pytest -q
```

Expected output:

```text
1 passed
```

Finally, run the real multi-agent workflow:

```powershell
codementor "Write a Python function that adds two numbers" --language Python
```

The command makes five model calls through the Coordinator, Code Writer, Review,
Testing, and final Coordinator steps. It requires a valid `OPENAI_API_KEY` and may
incur API usage costs.

To review existing code instead, provide `--code`:

```powershell
codementor "Review this function" --language Python --code "def add(a, b): return a + b"
```

## Scope Boundary

This implementation is Basic. Memory, vector
stores, RAG, databases, Gradio, and other Week 2 components are not included.
