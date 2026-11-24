"""Tests for BaseAgent initialisation and response handling."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-unit-tests")

from codeagent_mcp.base import BaseAgent, AgentResponseError, MAX_TOKENS


def _mock_response(*texts: str, stop_reason: str = "end_turn") -> MagicMock:
    blocks = []
    for text in texts:
        block = MagicMock()
        block.type = "text"
        block.text = text
        blocks.append(block)
    response = MagicMock()
    response.content = blocks
    response.stop_reason = stop_reason
    return response


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing."""
    def __init__(self):
        super().__init__("Tester", "You are a test agent.")


@pytest.fixture
def client(monkeypatch):
    """A mocked Anthropic client. Both endpoints return the same canned reply."""
    monkeypatch.delenv("ANTHROPIC_API_MODEL", raising=False)
    with patch("codeagent_mcp.base.anthropic.Anthropic") as client_cls:
        yield client_cls


def _create(client_cls):
    """The create() mock the agent will call for the default model (beta, with fallbacks)."""
    return client_cls.return_value.beta.messages.create


class TestBaseAgentInit:
    def test_raises_without_api_key(self, monkeypatch, client):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ConcreteAgent()

    def test_initialises_with_api_key(self, client):
        agent = ConcreteAgent()
        assert agent.role == "Tester"
        client.assert_called_once()

    def test_sdk_handles_retries(self, client):
        ConcreteAgent()
        assert client.call_args.kwargs["max_retries"] == 4

    def test_uses_default_model(self, client):
        assert ConcreteAgent()._model_name == "claude-sonnet-5-5"

    def test_uses_custom_model_from_env(self, monkeypatch, client):
        monkeypatch.setenv("ANTHROPIC_API_MODEL", "claude-opus-5-5")
        assert ConcreteAgent()._model_name == "claude-opus-5-5"

    def test_explicit_model_wins_over_env(self, monkeypatch, client):
        monkeypatch.setenv("ANTHROPIC_API_MODEL", "claude-opus-5-5")
        agent = BaseAgent("Tester", "You are a test agent.", model="claude-haiku-4-5")
        assert agent._model_name == "claude-haiku-4-5"


class TestGenerateResponse:
    def test_returns_text_on_success(self, client):
        _create(client).return_value = _mock_response("generated code")
        assert ConcreteAgent().generate_response("write hello world") == "generated code"

    def test_joins_multiple_text_blocks(self, client):
        _create(client).return_value = _mock_response("part one ", "part two")
        assert ConcreteAgent().generate_response("x") == "part one part two"

    def test_sends_effort_and_max_tokens(self, client):
        _create(client).return_value = _mock_response("ok")
        ConcreteAgent().generate_response("x")
        kwargs = _create(client).call_args.kwargs
        assert kwargs["output_config"] == {"effort": "high"}
        assert kwargs["max_tokens"] == MAX_TOKENS

    def test_enables_refusal_fallbacks_on_supported_model(self, client):
        _create(client).return_value = _mock_response("ok")
        ConcreteAgent().generate_response("x")
        kwargs = _create(client).call_args.kwargs
        assert kwargs["fallbacks"] == "default"
        assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]

    def test_plain_endpoint_for_other_models(self, monkeypatch, client):
        monkeypatch.setenv("ANTHROPIC_API_MODEL", "claude-haiku-5-5")
        client.return_value.messages.create.return_value = _mock_response("ok")
        assert ConcreteAgent().generate_response("x") == "ok"
        client.return_value.beta.messages.create.assert_not_called()

    def test_truncated_reply_raises(self, client):
        # A reply cut off at max_tokens is incomplete code: never pass it on
        _create(client).return_value = _mock_response("def half_a_func", stop_reason="max_tokens")
        with pytest.raises(AgentResponseError, match="cut off"):
            ConcreteAgent().generate_response("x")

    def test_refusal_raises(self, client):
        _create(client).return_value = _mock_response(stop_reason="refusal")
        with pytest.raises(AgentResponseError, match="declined"):
            ConcreteAgent().generate_response("x")

    def test_no_text_raises(self, client):
        _create(client).return_value = _mock_response()
        with pytest.raises(AgentResponseError, match="no text"):
            ConcreteAgent().generate_response("x")

    def test_api_errors_are_not_retried_by_the_agent(self, client):
        # Retrying is the SDK's job (max_retries); the agent calls the API once
        _create(client).side_effect = RuntimeError("API down")
        with pytest.raises(RuntimeError, match="API down"):
            ConcreteAgent().generate_response("x")
        assert _create(client).call_count == 1
