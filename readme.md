# 🤖 codeagent-mcp


A **self-healing SDLC pipeline** as an MCP plugin.

Describe what you want in plain English. CodeAgent writes it, reviews it, debugs it, and deploys it to disk — automatically, inside Claude, Cursor, or Windsurf.

---

## How it works

```
Your prompt
    │
    ▼
CoderAgent      →  writes the first draft
    │
    ▼
ReviewerAgent   →  audits for bugs / quality  (PASS / FAIL)
    │   ▲
    │   │  auto-retry up to 3×
    ▼   │
DebuggerAgent   →  fixes issues and re-submits for review
    │
    ▼
DeployerAgent   →  saves clean code to dist/
```

Each agent is a separate Gemini instance with a specialised system prompt. The pipeline is fully autonomous — you prompt once, it handles the rest.

---

## Install

```bash
pip install codeagent-mcp
```

Or run without installing via `uvx`:

```bash
uvx codeagent-mcp
```

---

## Setup

Create a `.env` file (or set environment variables directly):

```env
GOOGLE_API_KEY=your_gemini_api_key_here

# Optional — defaults shown
GOOGLE_API_MODEL=gemini-2.0-flash
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).

---

## Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codeagent": {
      "command": "uvx",
      "args": ["codeagent-mcp"],
      "env": {
        "GOOGLE_API_KEY": "your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see the CodeAgent tools available immediately.

---

## Add to Cursor

Edit `.cursor/mcp.json` in your project root (or the global config):

```json
{
  "mcpServers": {
    "codeagent": {
      "command": "uvx",
      "args": ["codeagent-mcp"],
      "env": {
        "GOOGLE_API_KEY": "your_key_here"
      }
    }
  }
}
```

---

## Add to Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "codeagent": {
      "command": "uvx",
      "args": ["codeagent-mcp"],
      "env": {
        "GOOGLE_API_KEY": "your_key_here"
      }
    }
  }
}
```

---

## Available Tools

| Tool | What it does |
|------|-------------|
| `run_full_pipeline(prompt, filename?)` | ⚡ **Full autonomous pipeline** — generate → review → debug → deploy in one call |
| `develop_feature(prompt)` | Generate code from a plain-English description |
| `audit_code(code)` | Review code — returns `PASS` or `FAIL` + details |
| `debug_code(code, feedback)` | Fix bugs based on reviewer feedback |
| `deploy_to_disk(code, filename?)` | Save cleaned code to `dist/` |
| `explain_code(code)` | Plain-English explanation of what code does |
| `refactor_code(code, instructions)` | Targeted refactor (e.g. "make it async", "add type hints") |

---

## Example usage in Claude

> *"Use run_full_pipeline to build a FastAPI endpoint that accepts a JSON body with name and email, validates both fields, and returns a confirmation message. Save it as api.py"*

Claude calls your plugin, which:
1. Generates the FastAPI code
2. Reviews it (catches missing input validation, etc.)
3. Auto-debugs if needed
4. Saves `dist/api.py` to your disk

---

## CLI usage

Start the MCP server manually:

```bash
codeagent
```

Run the interactive terminal pipeline:

```bash
codeagent --cli
```

---

## Project structure

```
codeagent-mcp/
├── agents/
│   ├── __init__.py         # Exports all agents
│   ├── base.py             # BaseAgent — shared Gemini setup
│   ├── specialized.py      # CoderAgent, ReviewerAgent, DebuggerAgent, DeployerAgent
│   └── plugin_server.py    # MCP server + all tool definitions
├── dist/                   # Generated code lands here
├── pyproject.toml          # Package config
├── requirements.txt        # Dev dependencies
└── readme.md
```

---

## Local development

```bash
git clone https://github.com/spandey1702/CodeAgent
cd codeagent-mcp
pip install -e .

# Run the server locally
python agents/plugin_server.py

# Or the CLI
python agents/plugin_server.py --cli
```

---

## Publish to PyPI

```bash
pip install build twine
python -m build
twine upload dist/*
```

---

## License

MIT
