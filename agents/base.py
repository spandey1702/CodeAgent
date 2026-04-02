import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class BaseAgent:
    def __init__(self, role, instructions):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found in environment variables. "
                "Please set it in your .env file and try again."
            )

        self.role = role
        self.instructions = instructions
        self.logger = logging.getLogger(self.role)

        self._client = genai.Client(api_key=api_key)
        self._model_name = os.getenv("GOOGLE_API_MODEL", "gemini-2.0-flash")
        self._system_instruction = f"You are a {self.role}. {self.instructions}"

    def generate_response(self, user_query: str) -> str:
     self.logger.info(f"[{self.role}] Processing request...")
     try:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=self._system_instruction,
                temperature=0.2,
            ),
        )
        return response.text
     except Exception as e:
        self.logger.error(f"[{self.role}] API error: {e}")
        raise  # Re-raise instead of returning error string