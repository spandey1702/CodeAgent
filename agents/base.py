import os
import time
import logging
import anthropic
from dotenv import load_dotenv

load_dotenv()

# How long to wait between retries (seconds): 1s, 2s, 4s
_RETRY_DELAYS = [1, 2, 4]


class BaseAgent:
    def __init__(self, role: str, instructions: str):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment variables. "
                "Please set it in your .env file and try again."
            )

        self.role = role
        self.instructions = instructions
        self.logger = logging.getLogger(self.role)

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model_name = os.getenv("ANTHROPIC_API_MODEL", "claude-sonnet-5")
        self._system_instruction = f"You are a {self.role}. {self.instructions}"

    def generate_response(self, user_query: str) -> str:
        """
        Call the Claude API and return the text response.

        Retries up to 3 times with exponential backoff (1 s → 2 s → 4 s)
        on transient errors (rate-limit, network blip, etc.).
        Raises the last exception if all attempts fail.
        """
        self.logger.info(f"[{self.role}] Processing request...")
        last_exc: Exception | None = None

        for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
            if delay:
                self.logger.warning(
                    f"[{self.role}] Retrying in {delay}s (attempt {attempt}/{len(_RETRY_DELAYS) + 1})..."
                )
                time.sleep(delay)
            try:
                response = self._client.messages.create(
                    model=self._model_name,
                    max_tokens=4096,
                    system=self._system_instruction,
                    output_config={"effort": "low"},
                    messages=[{"role": "user", "content": user_query}],
                )
                return next(block.text for block in response.content if block.type == "text")
            except Exception as e:
                self.logger.error(f"[{self.role}] API error (attempt {attempt}): {e}")
                last_exc = e

        raise last_exc  # type: ignore[misc]  # all retries exhausted
