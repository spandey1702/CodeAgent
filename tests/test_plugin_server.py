"""
The MCP server must import and register its tools. CI was green while a fresh
install couldn't start the server (mcp 2.x), because no test imported it.
"""
import asyncio
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-unit-tests")

from codeagent_mcp import plugin_server
from codeagent_mcp.specialized import Review, TestResult, TesterAgent

EXPECTED_TOOLS = {
    "develop_feature", "audit_code", "debug_code", "write_and_run_tests",
    "deploy_to_disk", "deploy_to_github", "explain_code", "refactor_code",
    "run_full_pipeline", "run_supervised_pipeline",
}


def test_server_registers_all_tools():
    tools = asyncio.run(plugin_server.mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def _agents(code="x = 1", reviews=(), fixes=(), test_results=None):
    """Mocked agent classes for the pipeline, with canned outputs in order.
    test_results defaults to always-pass so existing review-only tests don't
    need to care about the testing phase at all."""
    coder, reviewer, tester, debugger, explainer = (
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    coder.generate_response.return_value = code
    reviewer.review.side_effect = list(reviews)
    debugger.fix.side_effect = list(fixes)
    tester.write_tests.return_value = "test code"
    explainer.explain.return_value = "Sets x to 1."
    classes = dict(
        CoderAgent=MagicMock(return_value=coder),
        ReviewerAgent=MagicMock(return_value=reviewer),
        TesterAgent=MagicMock(return_value=tester),
        DebuggerAgent=MagicMock(return_value=debugger),
        ExplainerAgent=MagicMock(return_value=explainer),
        run_tests=MagicMock(
            side_effect=list(test_results) if test_results is not None else None,
            return_value=TestResult(passed=True) if test_results is None else None,
        ),
    )
    return classes, reviewer, tester, debugger


class TestWriteAndRunTests:
    def test_writes_then_runs_and_returns_pass_text(self):
        tester = MagicMock()
        tester.write_tests.return_value = "test code"
        with patch.multiple(
            plugin_server,
            TesterAgent=MagicMock(return_value=tester),
            run_tests=MagicMock(return_value=TestResult(passed=True)),
        ):
            result = plugin_server.write_and_run_tests("x = 1", "set x to 1")
        tester.write_tests.assert_called_once_with("x = 1", "set x to 1")
        assert result == "PASS"

    def test_returns_fail_text_with_output(self):
        tester = MagicMock()
        tester.write_tests.return_value = "test code"
        with patch.multiple(
            plugin_server,
            TesterAgent=MagicMock(return_value=tester),
            run_tests=MagicMock(return_value=TestResult(passed=False, output="1 failed")),
        ):
            result = plugin_server.write_and_run_tests("x = 1", "set x to 1")
        assert result == "FAIL\n1 failed"


def test_pipeline_does_not_deploy_after_failed_reviews(monkeypatch, tmp_path):
    """Regression: 'FAIL: ... password' used to count as PASS and get deployed."""
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    fail = Review(False, ["hardcoded password"])
    classes, reviewer, tester, debugger = _agents(reviews=[fail] * 3, fixes=["x = 2", "x = 3"])
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("write a login", "app.py")
    assert result.startswith("🛑")
    assert reviewer.review.call_count == 3
    assert debugger.fix.call_count == 2          # 3 checks, 2 debug rounds
    tester.write_tests.assert_not_called()       # never reached: review never passed
    assert not (tmp_path / "app.py").exists()


def test_reviewer_and_debugger_receive_the_requirements(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, reviewer, tester, debugger = _agents(
        reviews=[Review(False, ["ignores negatives"]), Review(True)], fixes=["x = 2"])
    with patch.multiple(plugin_server, **classes):
        plugin_server.run_full_pipeline("sum the list", "app.py")
    assert reviewer.review.call_args_list[0].args == ("x = 1", "sum the list")
    assert debugger.fix.call_args.args == ("x = 1", "FAIL\n- ignores negatives", "sum the list")


def test_syntax_error_skips_the_reviewer_and_goes_to_the_debugger(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, reviewer, tester, debugger = _agents(
        code="def f(:\n    pass", reviews=[Review(True)], fixes=["def f():\n    pass"])
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("define f", "app.py")
    assert "SyntaxError" in debugger.fix.call_args.args[1]
    assert reviewer.review.call_count == 1       # only the fixed code was reviewed
    assert "Passed review and tests on attempt 2" in result
    assert (tmp_path / "app.py").read_text() == "def f():\n    pass"


def test_pipeline_deploys_after_a_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, *_ = _agents(reviews=[Review(True)])
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("set x", "app.py")
    assert "Passed review and tests on attempt 1" in result
    assert (tmp_path / "app.py").read_text() == "x = 1"


def test_failed_tests_go_to_the_debugger_not_deploy(monkeypatch, tmp_path):
    """A clean review doesn't bypass testing: a failing test run still sends
    the code back to the Debugger, with the real test output as feedback."""
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    classes, reviewer, tester, debugger = _agents(
        code="def f(a, b): return a - b",
        reviews=[Review(True), Review(True)],
        fixes=["def f(a, b): return a + b"],
        test_results=[
            TestResult(passed=False, output="assert f(1, 2) == 3\nAssertionError"),
            TestResult(passed=True),
        ],
    )
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("write f(a, b) that adds a and b", "app.py")
    assert "Passed review and tests on attempt 2" in result
    assert debugger.fix.call_args.args[1].startswith("FAIL")
    assert "AssertionError" in debugger.fix.call_args.args[1]
    assert (tmp_path / "app.py").read_text() == "def f(a, b): return a + b"


def test_halts_after_max_attempts_of_failing_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path))
    fail_test = TestResult(passed=False, output="2 failed, 0 passed")
    classes, reviewer, tester, debugger = _agents(
        reviews=[Review(True)] * 3,
        fixes=["x = 2", "x = 3"],
        test_results=[fail_test] * 3,
    )
    with patch.multiple(plugin_server, **classes):
        result = plugin_server.run_full_pipeline("set x", "app.py")
    assert result.startswith("🛑")
    assert "passed review but failed tests" in result
    assert "2 failed, 0 passed" in result
    assert not (tmp_path / "app.py").exists()


def _supervised_agents(code="x = 1", decisions=(), reviews=(), fixes=(), test_results=None):
    """Mocked agent classes for run_supervised_pipeline, including the Supervisor
    and Deployer (run_full_pipeline's _agents() doesn't mock DeployerAgent since
    it writes to CODEAGENT_OUTPUT_DIR for real; the supervised pipeline mocks it
    so deploy_to_github can be asserted on without a real network call).
    test_results defaults to always-pass, same reasoning as _agents()."""
    supervisor, coder, reviewer, tester, debugger, deployer, explainer = (
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )
    supervisor.decide.side_effect = list(decisions)
    coder.generate_response.return_value = code
    reviewer.review.side_effect = list(reviews)
    tester.write_tests.return_value = "test code"
    debugger.fix.side_effect = list(fixes)
    deployer.deploy.return_value = "✅ Successfully deployed to dist/app.py"
    deployer.deploy_to_github.return_value = "✅ Opened PR for review: https://github.com/me/repo/pull/1"
    explainer.explain.return_value = "Sets x to 1."
    classes = dict(
        SupervisorAgent=MagicMock(return_value=supervisor),
        CoderAgent=MagicMock(return_value=coder),
        ReviewerAgent=MagicMock(return_value=reviewer),
        TesterAgent=MagicMock(return_value=tester),
        DebuggerAgent=MagicMock(return_value=debugger),
        DeployerAgent=MagicMock(return_value=deployer),
        ExplainerAgent=MagicMock(return_value=explainer),
        run_tests=MagicMock(
            side_effect=list(test_results) if test_results is not None else None,
            return_value=TestResult(passed=True) if test_results is None else None,
        ),
    )
    return classes, supervisor, reviewer, tester, debugger, deployer


class TestRunSupervisedPipeline:
    def test_review_then_test_then_deploy_to_disk(self):
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["REVIEW\nlooks new", "TEST\nchecking", "DEPLOY\nit passed"],
            reviews=[Review(True)],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert result.startswith("✅ Supervised pipeline complete after 3 step(s), 0 retries.")
        tester.write_tests.assert_called_once_with("x = 1", "set x")
        deployer.deploy.assert_called_once_with("x = 1", "app.py")
        deployer.deploy_to_github.assert_not_called()
        debugger.fix.assert_not_called()

    def test_deploy_before_tests_pass_is_converted_into_a_test_step(self):
        """The Supervisor's own gate isn't trusted: asking to DEPLOY before any
        TEST has passed gets silently redirected into a TEST step instead."""
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["DEPLOY\ntoo early", "DEPLOY\nnow for real"],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert result.startswith("✅ Supervised pipeline complete after 2 step(s), 0 retries.")
        assert supervisor.decide.call_count == 2
        tester.write_tests.assert_called_once_with("x = 1", "set x")
        deployer.deploy.assert_called_once_with("x = 1", "app.py")

    def test_debug_resets_a_previously_passed_test(self):
        """A DEBUG after a passing TEST invalidates that pass: the new code
        hasn't actually been tested yet, so DEPLOY must force a fresh TEST."""
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["TEST\nchecking", "DEBUG\ntweak it anyway", "DEPLOY\ngo", "DEPLOY\nnow for real"],
            fixes=["x = 2"],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert result.startswith("✅ Supervised pipeline complete after 4 step(s), 1 retry.")
        assert tester.write_tests.call_count == 2   # once before DEBUG, once forced after
        deployer.deploy.assert_called_once_with("x = 2", "app.py")

    def test_debug_then_review_then_test_then_deploy(self):
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["DEBUG\nfix it", "REVIEW\nrecheck", "TEST\ncheck", "DEPLOY\ngo"],
            reviews=[Review(True)],
            fixes=["x = 2"],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "1 retry" in result
        debugger.fix.assert_called_once_with("x = 1", "", "set x")
        deployer.deploy.assert_called_once_with("x = 2", "app.py")

    def test_deploy_to_github_when_requested(self):
        classes, *_, deployer = _supervised_agents(
            decisions=["DEPLOY\ntoo early", "DEPLOY\nnow for real"],
        )
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
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["MAYBE\nnot sure"]
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "unrecognized supervisor output" in result
        reviewer.review.assert_not_called()
        tester.write_tests.assert_not_called()
        debugger.fix.assert_not_called()
        deployer.deploy.assert_not_called()

    def test_stops_after_max_retries_without_asking_supervisor_again(self):
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["DEBUG\n1", "DEBUG\n2", "DEBUG\n3", "DEBUG\n4"],
            fixes=["x = 2", "x = 3", "x = 4"],
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "3-retry limit" in result
        assert supervisor.decide.call_count == 3    # the 4th DEBUG was never asked for
        deployer.deploy.assert_not_called()

    def test_stops_at_step_cap_when_never_deciding_to_debug(self):
        classes, supervisor, reviewer, tester, debugger, deployer = _supervised_agents(
            decisions=["REVIEW\nagain"] * 8,
            reviews=[Review(False, ["still broken"])] * 8,
        )
        with patch.multiple(plugin_server, **classes):
            result = plugin_server.run_supervised_pipeline("set x", "app.py")
        assert "8-step safety cap" in result
        assert supervisor.decide.call_count == 8
        debugger.fix.assert_not_called()
        deployer.deploy.assert_not_called()
