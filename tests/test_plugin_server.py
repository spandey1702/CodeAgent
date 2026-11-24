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
    "develop_feature", "audit_code", "debug_code", "deploy_to_disk", "deploy_to_github",
    "explain_code", "refactor_code", "run_full_pipeline", "run_supervised_pipeline",
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


def _supervised_agents(code="x = 1", decisions=(), reviews=(), fixes=()):
    """Mocked agent classes for run_supervised_pipeline, including the Supervisor
    and Deployer (run_full_pipeline's _agents() doesn't mock DeployerAgent since
    it writes to CODEAGENT_OUTPUT_DIR for real; the supervised pipeline mocks it
    so deploy_to_github can be asserted on without a real network call)."""
    supervisor, coder, reviewer, debugger, deployer, explainer = (
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    supervisor.decide.side_effect = list(decisions)
    coder.generate_response.return_value = code
    reviewer.review.side_effect = list(reviews)
    debugger.fix.side_effect = list(fixes)
    deployer.deploy.return_value = "✅ Successfully deployed to dist/app.py"
    deployer.deploy_to_github.return_value = "✅ Opened PR for review: https://github.com/me/repo/pull/1"
    explainer.explain.return_value = "Sets x to 1."
    classes = dict(
        SupervisorAgent=MagicMock(return_value=supervisor),
        CoderAgent=MagicMock(return_value=coder),
        ReviewerAgent=MagicMock(return_value=reviewer),
        DebuggerAgent=MagicMock(return_value=debugger),
        DeployerAgent=MagicMock(return_value=deployer),
        ExplainerAgent=MagicMock(return_value=explainer),
    )
    return classes, supervisor, reviewer, debugger, deployer


class TestRunSupervisedPipeline:
    def test_review_then_deploy_to_disk(self):
        classes, supervisor, reviewer, debugger, deployer = _supervised_agents(
            decisions=["REVIEW\nlooks new", "DEPLOY\nit passed"],
            reviews=[Review(True)],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert result.startswith("✅ Supervised pipeline complete after 2 step(s), 0 retries.")
        deployer.deploy.assert_called_once_with("x = 1", "app.py")
        deployer.deploy_to_github.assert_not_called()
        debugger.fix.assert_not_called()

    def test_debug_then_review_then_deploy(self):
        classes, supervisor, reviewer, debugger, deployer = _supervised_agents(
            decisions=["DEBUG\nfix it", "REVIEW\nrecheck", "DEPLOY\ngo"],
            reviews=[Review(True)],
            fixes=["x = 2"],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "1 retry" in result
        debugger.fix.assert_called_once_with("x = 1", "", "set x")
        deployer.deploy.assert_called_once_with("x = 2", "app.py")

    def test_deploy_to_github_when_requested(self):
        classes, *_ , deployer = _supervised_agents(decisions=["DEPLOY\ngo"])
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline(
                "set x", "app.py", deploy_target="github", repo="me/repo"
            )
        assert "Opened PR for review" in result
        deployer.deploy_to_github.assert_called_once_with("x = 1", "app.py", "me/repo")
        deployer.deploy.assert_not_called()

    def test_github_target_without_repo_is_an_error(self):
        classes, *_ = _supervised_agents(decisions=["DEPLOY\ngo"])
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline(
                "set x", "app.py", deploy_target="github"
            )
        assert result.startswith("ERROR") and "repo" in result

    def test_halts_when_supervisor_says_halt(self):
        classes, *_ = _supervised_agents(decisions=["HALT\nrequirement is unachievable"])
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("do the impossible", "app.py")
        assert result.startswith("🛑 Supervisor halted after 1 step(s).")
        assert "unachievable" in result

    def test_halts_on_unrecognized_decision_without_calling_other_agents(self):
        classes, supervisor, reviewer, debugger, deployer = _supervised_agents(
            decisions=["MAYBE\nnot sure"]
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "unrecognized supervisor output" in result
        reviewer.review.assert_not_called()
        debugger.fix.assert_not_called()
        deployer.deploy.assert_not_called()

    def test_stops_after_max_retries_without_asking_supervisor_again(self):
        classes, supervisor, reviewer, debugger, deployer = _supervised_agents(
            decisions=["DEBUG\n1", "DEBUG\n2", "DEBUG\n3", "DEBUG\n4"],
            fixes=["x = 2", "x = 3", "x = 4"],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "3-retry limit" in result
        assert supervisor.decide.call_count == 3    # the 4th DEBUG was never asked for
        deployer.deploy.assert_not_called()

    def test_stops_at_step_cap_when_never_deciding_to_debug(self):
        classes, supervisor, reviewer, debugger, deployer = _supervised_agents(
            decisions=["REVIEW\nagain"] * 8,
            reviews=[Review(False, ["still broken"])] * 8,
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "8-step safety cap" in result
        assert supervisor.decide.call_count == 8
        debugger.fix.assert_not_called()
        deployer.deploy.assert_not_called()
