import os
import logging
import anthropic
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-5-5"

# Room for adaptive thinking plus a full file of code. Thinking tokens count
# against this limit, so a small value silently cuts code off mid-function.
MAX_TOKENS = 16000

# Models that accept server-side refusal fallbacks: if the model declines a
# request, the API retries it on a suitable fallback model in the same call.
_FALLBACK_MODELS = {
    "claude-sonnet-5-5",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-fable-5-1",
    "claude-fable-5-2",
}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AgentResponseError(RuntimeError):
    """The API call succeeded, but the reply can't be used (declined, cut off, or empty)."""


class BaseAgent:
    def __init__(self, role: str, instructions: str, effort: str = "high"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment variables. "
                "Please set it in your .env file and try again."
            )

        self.role = role
        self.instructions = instructions
        self.effort = effort
        self.logger = logging.getLogger(self.role)

        # The SDK retries rate limits (429), server errors (5xx) and connection
        # errors with exponential backoff. Bad requests and auth errors are not
        # retried: they would fail the same way every time.
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=4)
        self._model_name = os.getenv("ANTHROPIC_API_MODEL", DEFAULT_MODEL)
        self._system_instruction = f"You are a {self.role}. {self.instructions}"

    def generate_response(self, user_query: str, output_schema: dict | None = None) -> str:
        """
        Call the Claude API and return the text response.

        With output_schema (a JSON schema), the reply is guaranteed to be JSON
        matching it (structured outputs), so it can be parsed deterministically.

        Raises AgentResponseError if the model declines the request, if the
        reply was cut off at MAX_TOKENS (the code would be incomplete), or if
        it contains no text.
        """
        self.logger.info(f"[{self.role}] Processing request...")
        output_config = {"effort": self.effort}
        if output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
        request = {
            "model": self._model_name,
            "max_tokens": MAX_TOKENS,
            "system": self._system_instruction,
            "output_config": output_config,
            "messages": [{"role": "user", "content": user_query}],
        }
        if self._model_name in _FALLBACK_MODELS:
            response = self._client.beta.messages.create(
                **request, betas=[_FALLBACK_BETA], fallbacks="default"
            )
        else:
            response = self._client.messages.create(**request)

        if response.stop_reason == "refusal":
            raise AgentResponseError(f"[{self.role}] The model declined this request.")
        if response.stop_reason == "max_tokens":
            raise AgentResponseError(
                f"[{self.role}] The reply was cut off at {MAX_TOKENS} tokens, so it is incomplete."
            )

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise AgentResponseError(f"[{self.role}] The reply contained no text.")
        return text
