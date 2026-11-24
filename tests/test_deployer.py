"""
Tests for DeployerAgent — no API calls needed.
_extract_code() is a pure static method; deploy() uses the filesystem only.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

# Set a dummy API key so BaseAgent init doesn't raise
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-unit-tests")

from codeagent_mcp.specialized import DeployerAgent


class TestExtractCode:
    def test_extracts_python_fenced_block(self):
        raw = "Here is the code:\n```python\nprint('hello')\n```\nEnd."
        assert DeployerAgent._extract_code(raw) == "print('hello')"

    def test_extracts_plain_fenced_block(self):
        raw = "```\nx = 1 + 1\n```"
        assert DeployerAgent._extract_code(raw) == "x = 1 + 1"

    def test_returns_raw_when_no_fences(self):
        raw = "x = 42"
        assert DeployerAgent._extract_code(raw) == "x = 42"

    def test_strips_whitespace(self):
        raw = "```python\n\n  x = 1\n\n```"
        assert DeployerAgent._extract_code(raw) == "x = 1"

    def test_multiline_code(self):
        raw = "```python\ndef add(a, b):\n    return a + b\n```"
        assert DeployerAgent._extract_code(raw) == "def add(a, b):\n    return a + b"

    def test_takes_first_block_when_multiple(self):
        raw = "```python\nfirst = 1\n```\n```python\nsecond = 2\n```"
        result = DeployerAgent._extract_code(raw)
        assert "first = 1" in result


@pytest.fixture(autouse=True)
def _default_output_dir(monkeypatch):
    monkeypatch.delenv("CODEAGENT_OUTPUT_DIR", raising=False)


class TestDeploy:
    def test_creates_dist_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("codeagent_mcp.base.anthropic.Anthropic"):
            agent = DeployerAgent()
        result = agent.deploy("x = 1", "test.py")
        assert (tmp_path / "dist" / "test.py").exists()
        assert "✅" in result

    def test_strips_fences_before_writing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("codeagent_mcp.base.anthropic.Anthropic"):
            agent = DeployerAgent()
        agent.deploy("```python\nx = 42\n```", "out.py")
        content = (tmp_path / "dist" / "out.py").read_text()
        assert content == "x = 42"
        assert "```" not in content

    def test_default_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("codeagent_mcp.base.anthropic.Anthropic"):
            agent = DeployerAgent()
        agent.deploy("pass")
        assert (tmp_path / "dist" / "app.py").exists()

    def test_output_dir_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CODEAGENT_OUTPUT_DIR", str(tmp_path / "out"))
        with patch("codeagent_mcp.base.anthropic.Anthropic"):
            agent = DeployerAgent()
        agent.deploy("x = 1", "app.py")
        assert (tmp_path / "out" / "app.py").read_text() == "x = 1"


class TestDeployRejectsUnsafeFilenames:
    """The filename comes from an AI client: it must never escape the output folder."""

    @pytest.mark.parametrize("filename", [
        "/tmp/codeagent_escape_test.py",   # absolute path would replace dist/ entirely
        "../escape.py",                    # climbs out of dist/
        "sub/dir/app.py",                  # no folders at all
        "notes.txt",                       # only .py files
        ".py",
        "",
    ])
    def test_rejected(self, filename, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("codeagent_mcp.base.anthropic.Anthropic"):
            agent = DeployerAgent()
        result = agent.deploy("x = 1", filename)
        assert result.startswith("ERROR")
        assert not Path("/tmp/codeagent_escape_test.py").exists()
        assert not (tmp_path / "escape.py").exists()
        assert not (tmp_path / "dist").exists() or not any((tmp_path / "dist").iterdir())


def test_refuses_code_that_does_not_parse(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("codeagent_mcp.base.anthropic.Anthropic"):
        agent = DeployerAgent()
    result = agent.deploy("```python\ndef broken(:\n    pass\n```", "app.py")
    assert result.startswith("ERROR") and "SyntaxError" in result
    assert not (tmp_path / "dist" / "app.py").exists()


class TestDeployToGithub:
    """deploy_to_github shares deploy()'s filename/syntax gates, then calls the
    GitHub REST API: get base SHA, create a branch, PUT the file, open a PR."""

    def _agent(self):
        with patch("codeagent_mcp.base.anthropic.Anthropic"):
            return DeployerAgent()

    def test_rejects_unsafe_filename_without_calling_github(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/repo")
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            result = self._agent().deploy_to_github("x = 1", "../escape.py", "me/repo")
        assert result.startswith("ERROR")
        mock_requests.get.assert_not_called()

    def test_refuses_code_that_does_not_parse(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/repo")
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            result = self._agent().deploy_to_github("def broken(:\n pass", "app.py", "me/repo")
        assert result.startswith("ERROR") and "SyntaxError" in result
        mock_requests.get.assert_not_called()

    def test_rejects_when_token_missing(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/repo")
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            result = self._agent().deploy_to_github("x = 1", "app.py", "me/repo")
        assert "GITHUB_TOKEN" in result
        mock_requests.get.assert_not_called()

    def test_rejects_repo_not_in_allowlist(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/other-repo")
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            result = self._agent().deploy_to_github("x = 1", "app.py", "me/repo")
        assert "GITHUB_REPO_ALLOWLIST" in result
        mock_requests.get.assert_not_called()

    def test_happy_path_opens_pr_on_new_branch(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/repo")
        ref_resp = MagicMock(status_code=200, **{"json.return_value": {"object": {"sha": "base-sha"}}})
        branch_resp = MagicMock(status_code=201)
        contents_resp = MagicMock(status_code=404)  # file does not exist yet
        put_resp = MagicMock(status_code=201)
        pr_resp = MagicMock(status_code=201, **{"json.return_value": {"html_url": "https://github.com/me/repo/pull/1"}})
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            mock_requests.get.side_effect = [ref_resp, contents_resp]
            mock_requests.post.side_effect = [branch_resp, pr_resp]
            mock_requests.put.return_value = put_resp
            result = self._agent().deploy_to_github("```python\nx = 1\n```", "app.py", "me/repo")

        assert result == "✅ Opened PR for review: https://github.com/me/repo/pull/1"
        branch_call = mock_requests.post.call_args_list[0]
        assert branch_call.kwargs["json"]["sha"] == "base-sha"
        assert branch_call.kwargs["json"]["ref"].startswith("refs/heads/codeagent/")
        put_call = mock_requests.put.call_args
        assert "sha" not in put_call.kwargs["json"]   # new file: no existing sha to send
        import base64
        assert base64.b64decode(put_call.kwargs["json"]["content"]).decode() == "x = 1"
        pr_call = mock_requests.post.call_args_list[1]
        assert pr_call.kwargs["json"]["base"] == "main"

    def test_updates_existing_file_with_its_sha(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/repo")
        ref_resp = MagicMock(status_code=200, **{"json.return_value": {"object": {"sha": "base-sha"}}})
        contents_resp = MagicMock(status_code=200, **{"json.return_value": {"sha": "existing-sha"}})
        pr_resp = MagicMock(status_code=201, **{"json.return_value": {"html_url": "https://github.com/me/repo/pull/2"}})
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            mock_requests.get.side_effect = [ref_resp, contents_resp]
            mock_requests.post.side_effect = [MagicMock(status_code=201), pr_resp]
            mock_requests.put.return_value = MagicMock(status_code=200)
            self._agent().deploy_to_github("x = 2", "app.py", "me/repo")
        assert mock_requests.put.call_args.kwargs["json"]["sha"] == "existing-sha"

    def test_github_api_error_is_reported_not_raised(self, monkeypatch):
        import requests as real_requests
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_REPO_ALLOWLIST", "me/repo")
        bad_resp = MagicMock(status_code=403, text="Forbidden")
        with patch("codeagent_mcp.specialized.requests") as mock_requests:
            mock_requests.HTTPError = real_requests.HTTPError
            ref_resp = MagicMock(status_code=200)
            ref_resp.raise_for_status.side_effect = real_requests.HTTPError(response=bad_resp)
            mock_requests.get.return_value = ref_resp
            result = self._agent().deploy_to_github("x = 1", "app.py", "me/repo")
        assert result.startswith("ERROR: GitHub API call failed") and "403" in result
