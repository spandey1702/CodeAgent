import os
import logging
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class BaseAgent:
    def __init__(self, role, instructions):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables. Please set it and try again.")
        
        openai.api_key = api_key
        openai.api_base = os.getenv("GOOGLE_API_BASE", "https://generativelanguage.googleapis.com/v1beta2/")  # Default API endpoint
        
        self.role = role
        self.instructions = instructions
        self.logger = logging.getLogger(self.role)
    
    def generate_response(self, user_query):
        self.logger.info(f"Processing request via Gemini...")
        try:
            model_name = os.getenv("GOOGLE_API_MODEL", "gemini-3")
            
            completion = openai.ChatCompletion.create(
                model=model_name,  
                messages=[
                    {"role": "system", "content": f"You are a {self.role}. {self.instructions}"},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.2
            )
            if 'choices' in completion and len(completion['choices']) > 0:
                return completion['choices'][0]['message']['content']
            else:
                self.logger.error("Invalid API response structure.")
                return "ERROR: Invalid API response structure."
        except openai.error.AuthenticationError:
            self.logger.error("Authentication failed. Check your API key.")
            return "ERROR: Authentication failed. Check your API key."
        except openai.error.OpenAIError as e:
            self.logger.error(f"OpenAI API Error: {e}")
            return f"ERROR: {e}"
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return f"ERROR: {e}"