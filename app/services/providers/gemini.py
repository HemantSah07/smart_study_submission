import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

class GeminiProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip() if api_key else ""
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def generate_content(self, prompt: str, model: str = "gemini-2.5-flash", **kwargs) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")

        # Clean model name if format has prefixes or brackets
        clean_model = model.split()[0].strip()

        # Handle system_instruction if provided in kwargs
        system_instruction = kwargs.get("system_instruction")
        generation_config = kwargs.get("generation_config", {})

        gen_model = genai.GenerativeModel(
            model_name=clean_model,
            system_instruction=system_instruction,
            generation_config=generation_config if generation_config else None
        )

        request_options = kwargs.get("request_options", {"timeout": 30})
        response = gen_model.generate_content(prompt, request_options=request_options)
        if response and response.text:
            return response.text
        return ""
