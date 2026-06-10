"""Smoke tests — verify all agent classes instantiate correctly."""
import os
import pytest
from unittest.mock import patch

os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-unit-tests")

from agents.specialized import (
    CoderAgent, ReviewerAgent, DebuggerAgent, ExplainerAgent, DeployerAgent
)

AGENT_CLASSES = [CoderAgent, ReviewerAgent, DebuggerAgent, ExplainerAgent, DeployerAgent]

@pytest.mark.parametrize("agent_cls", AGENT_CLASSES, ids=lambda c: c.__name__)
def test_agent_instantiates(agent_cls):
    with patch("agents.base.genai.Client"):
        agent = agent_cls()
        assert agent.role
        assert agent.instructions
        assert agent._model_name
