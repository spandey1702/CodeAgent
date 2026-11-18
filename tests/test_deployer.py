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
