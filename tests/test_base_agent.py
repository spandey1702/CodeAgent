"""Tests for BaseAgent initialisation and retry logic."""
import os
import pytest
from unittest.mock import patch, MagicMock, call

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-unit-tests")

from agents.base import BaseAgent


def _mock_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing."""
    def __init__(self):
        super().__init__("Tester", "You are a test agent.")


class TestBaseAgentInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("agents.base.anthropic.Anthropic"):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                ConcreteAgent()

    def test_initialises_with_api_key(self):
        with patch("agents.base.anthropic.Anthropic") as mock_client:
            agent = ConcreteAgent()
            assert agent.role == "Tester"
            mock_client.assert_called_once()

    def test_uses_default_model(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_MODEL", raising=False)
        with patch("agents.base.anthropic.Anthropic"):
            agent = ConcreteAgent()
            assert agent._model_name == "claude-sonnet-5"

    def test_uses_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_MODEL", "claude-opus-5")
        with patch("agents.base.anthropic.Anthropic"):
            agent = ConcreteAgent()
            assert agent._model_name == "claude-opus-5"


class TestGenerateResponse:
    def test_returns_text_on_success(self):
        with patch("agents.base.anthropic.Anthropic") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.messages.create.return_value = _mock_text_response("generated code")

            agent = ConcreteAgent()
            result = agent.generate_response("write hello world")
            assert result == "generated code"

    def test_retries_on_transient_error(self):
        with patch("agents.base.anthropic.Anthropic") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.messages.create.side_effect = [
                Exception("rate limit"),
                _mock_text_response("success after retry"),
            ]

            with patch("agents.base.time.sleep"):
                agent = ConcreteAgent()
                result = agent.generate_response("test")
                assert result == "success after retry"
                assert mock_client.messages.create.call_count == 2

    def test_raises_after_all_retries_exhausted(self):
        with patch("agents.base.anthropic.Anthropic") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.messages.create.side_effect = Exception("API down")

            with patch("agents.base.time.sleep"):
                agent = ConcreteAgent()
                with pytest.raises(Exception, match="API down"):
                    agent.generate_response("test")
                assert mock_client.messages.create.call_count == 4
