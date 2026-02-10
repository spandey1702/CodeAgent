import os
from openai import OpenAI
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    filename='code_agent.log',
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class BaseAgent:
    def __init__(self, role, instructions):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        self.client = OpenAI(api_key=api_key) 
        self.role = role
        self.instructions = instructions
        self.logger = logging.getLogger(self.role)
    
    def generate_response(self, user_query):
        self.logger.info(f"Processing request..")
        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"You are a {self.role}. {self.instructions}"},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.2
            )
            return completion.choices[0].message.content
        except Exception as e:
            self.logger.error(f"API Error: {e}")
            return f"ERROR: {e}"