# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.0] - 2026-11-17

### Breaking
- The package is renamed from `agents` to `codeagent_mcp` (the old name collides with other packages, such as OpenAI's `openai-agents`). Run the server with `python -m codeagent_mcp.plugin_server`; the `codeagent` command is unchanged.

### Fixed
- **Review gate passed failed reviews.** The pipeline checked whether "PASS" appeared anywhere in the reply, so "FAIL: hardcoded password" counted as a pass and the code was deployed. The reviewer now returns a structured verdict (JSON via structured outputs: `PASS`/`FAIL` plus a list of issues), so the decision is a field, not a word to search for.
- **Fresh installs couldn't start the server.** `mcp>=1.2.0` resolved to mcp 2.x, which renamed `FastMCP`. Pinned to `mcp>=1.2.0,<2`.
- **`deploy_to_disk` could write outside `dist/`.** An absolute path or `../` in the filename escaped the folder. Filenames must now be a plain `.py` name.
- **Truncated or declined replies were passed on as code.** Replies cut off at `max_tokens`, refusals, and empty replies now raise `AgentResponseError`. `max_tokens` raised from 4,096 to 16,000, since thinking tokens count against it.
- Retries: the agent no longer retries every error four times on top of the SDK's own retries. The SDK retries rate limits, server errors and connection errors (`max_retries=4`); bad requests and auth errors fail immediately.

### Changed
- Migrated from Gemini to the Claude API. Default model `claude-sonnet-5-5`, with server-side refusal fallbacks enabled on models that support them.
- Effort per agent: `high` for the coder, reviewer and debugger, `low` for the explainer (previously `low` for all).
- New `CODEAGENT_OUTPUT_DIR` setting for where deployed files go.
- README install instructions now use GitHub: the package is not currently on PyPI.
- The reviewer and debugger now receive the original requirements, so the review checks the code does what was asked, not only general quality. `audit_code` and `debug_code` take an optional `requirements` argument.
- Code must parse before it's reviewed or deployed. A syntax error goes straight to the debugger without a reviewer call, and `deploy_to_disk` refuses code that doesn't parse.
- Prompt-injection hardening: code and requirements are passed inside tags with a random per-request suffix, and every agent is told to treat their content as data, never instructions.
- The examples are now runnable scripts.
- Removed unused dependencies (`fastmcp`, `pydantic`, `pydantic-settings`, `httpx`, `tqdm`) and the outdated `agents/main.py`.

### Added
- Tests for the structured verdict, requirements passing, the syntax check, untrusted-input wrapping, unsafe filenames, response handling, and an MCP server import test (CI previously never imported the server).

---

## [0.1.1] - 2026-06-10

### Fixed
- Relative import in `plugin_server.py` — package now installs correctly via `pip` and `uvx`
- Removed committed log files and build artifacts from the repository (they remain in git history)

### Added
- Pytest test suite covering `BaseAgent`, `DeployerAgent`, and all specialized agents
- GitHub Actions CI — runs tests on Python 3.10, 3.11, and 3.12 on every push and PR

### Changed
- `.gitignore` now excludes `*.log`, `dist/`, `build/`, and `*.egg-info/`

---

## [0.1.0] - 2026-05-28

### Added
- Initial release
- 4-stage autonomous SDLC pipeline: CoderAgent → ReviewerAgent → DebuggerAgent → DeployerAgent
- ExplainerAgent, and `explain_code` and `refactor_code` as standalone tools (refactoring uses CoderAgent)
- FastMCP server exposing 7 tools: `run_full_pipeline`, `develop_feature`, `audit_code`, `debug_code`, `deploy_to_disk`, `explain_code`, `refactor_code`
- Exponential backoff retry logic in `BaseAgent` (3 retries: 1s, 2s, 4s)
- Compatible with Claude Desktop, Cursor, and Windsurf via MCP
- Published to PyPI as `codeagent-mcp`
