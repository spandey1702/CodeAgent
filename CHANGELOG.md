# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.1] - 2026-06-10

### Fixed
- Relative import in `plugin_server.py` — package now installs correctly via `pip` and `uvx`
- Removed committed log files and build artifacts from repository history

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
- ExplainerAgent and RefactorAgent as standalone tools
- FastMCP server exposing 7 tools: `run_full_pipeline`, `develop_feature`, `audit_code`, `debug_code`, `deploy_to_disk`, `explain_code`, `refactor_code`
- Exponential backoff retry logic in `BaseAgent` (3 retries: 1s, 2s, 4s)
- Compatible with Claude Desktop, Cursor, and Windsurf via MCP
- Published to PyPI as `codeagent-mcp`
