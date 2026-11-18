"""
The MCP server must import and register its tools. CI was green while a fresh
install couldn't start the server (mcp 2.x), because no test imported it.
"""
import asyncio
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-unit-tests")

from codeagent_mcp import plugin_server
from codeagent_mcp.specialized import Review

EXPECTED_TOOLS = {
    "develop_feature", "audit_code", "debug_code", "deploy_to_disk",
    "explain_code", "refactor_code", "run_full_pipeline",
}


def test_server_registers_all_tools():
    tools = asyncio.run(plugin_server.mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def _agents(code="x = 1", reviews=(), fixes=()):
    """Mocked agent classes for the pipeline, with canned outputs in order."""
    coder, reviewer, debugger, explainer = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    coder.generate_response.return_value = code
    reviewer.review.side_effect = list(reviews)
    debugger.fix.side_effect = list(fixes)
    explainer.explain.return_value = "Sets x to 1."
    classes = dict(
        CoderAgent=MagicMock(return_value=coder),
        ReviewerAgent=MagicMock(return_value=reviewer),
        DebuggerAgent=MagicMock(return_value=debugger),
        ExplainerAgent=MagicMock(return_value=explainer),
    )
    return classes, reviewer, debugger


def test_pipeline_does_not_deploy_after_failed_reviews(monkeypatch, tmp_path):
    """Regression: 'FAIL: ... password' used to count as PASS and get deployed."""
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    fail = Review(False, ["hardcoded password"])
    classes, reviewer, debugger = _agents(reviews=[fail] * 3, fixes=["x = 2", "x = 3"])
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("write a login", "app.py")
    assert result.startswith("🛑")
    assert reviewer.review.call_count == 3
    assert debugger.fix.call_count == 2          # 3 checks, 2 debug rounds
    assert not (tmp_path / "app.py").exists()


def test_reviewer_and_debugger_receive_the_requirements(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, reviewer, debugger = _agents(
        reviews=[Review(False, ["ignores negatives"]), Review(True)], fixes=["x = 2"])
    with patch.multiple(plugin_server, **classes):
        plugin_server.run_full_pipeline("sum the list", "app.py")
    assert reviewer.review.call_args_list[0].args == ("x = 1", "sum the list")
    assert debugger.fix.call_args.args == ("x = 1", "FAIL\n- ignores negatives", "sum the list")


def test_syntax_error_skips_the_reviewer_and_goes_to_the_debugger(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, reviewer, debugger = _agents(
        code="def f(:\n    pass", reviews=[Review(True)], fixes=["def f():\n    pass"])
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("define f", "app.py")
    assert "SyntaxError" in debugger.fix.call_args.args[1]
    assert reviewer.review.call_count == 1       # only the fixed code was reviewed
    assert "Passed review on attempt 2" in result
    assert (tmp_path / "app.py").read_text() == "def f():\n    pass"


def test_pipeline_deploys_after_a_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, _, _ = _agents(reviews=[Review(True)])
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("set x", "app.py")
    assert "Passed review on attempt 1" in result
    assert (tmp_path / "app.py").read_text() == "x = 1"
