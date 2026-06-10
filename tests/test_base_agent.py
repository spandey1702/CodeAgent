"""Tests for BaseAgent initialisation and retry logic."""
import os
import pytest
from unittest.mock import patch, MagicMock, call

os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-unit-tests")

from agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing."""
    def __init__(self):
        super().__init__("Tester", "You are a test agent.")


class TestBaseAgentInit:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with patch("agents.base.genai.Client"):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                ConcreteAgent()

    def test_initialises_with_api_key(self):
        with patch("agents.base.genai.Client") as mock_client:
            agent = ConcreteAgent()
            assert agent.role == "Tester"
            mock_client.assert_called_once()

    def test_uses_default_model(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_MODEL", raising=False)
        with patch("agents.base.genai.Client"):
            agent = ConcreteAgent()
            assert agent._model_name == "gemini-2.0-flash"

    def test_uses_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_MODEL", "gemini-1.5-pro")
        with patch("agents.base.genai.Client"):
            agent = ConcreteAgent()
            assert agent._model_name == "gemini-1.5-pro"


class TestGenerateResponse:
    def test_returns_text_on_success(self):
        with patch("agents.base.genai.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.text = "generated code"
            mock_client = mock_client_cls.return_value
            mock_client.models.generate_content.return_value = mock_response

            agent = ConcreteAgent()
            result = agent.generate_response("write hello world")
            assert result == "generated code"

    def test_retries_on_transient_error(self):
        with patch("agents.base.genai.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.text = "success after retry"
            mock_client = mock_client_cls.return_value
            mock_client.models.generate_content.side_effect = [
                Exception("rate limit"),
                mock_response,
            ]

            with patch("agents.base.time.sleep"):
                agent = ConcreteAgent()
                result = agent.generate_response("test")
                assert result == "success after retry"
                assert mock_client.models.generate_content.call_count == 2

    def test_raises_after_all_retries_exhausted(self):
        with patch("agents.base.genai.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.models.generate_content.side_effect = Exception("API down")

            with patch("agents.base.time.sleep"):
                agent = ConcreteAgent()
                with pytest.raises(Exception, match="API down"):
                    agent.generate_response("test")
                assert mock_client.models.generate_content.call_count == 4
