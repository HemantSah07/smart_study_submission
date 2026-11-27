import logging

logger = logging.getLogger(__name__)

class ClaudeProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip() if api_key else ""
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")

    def chat(self, messages: list, system: str = "", model: str = "claude-3-5-haiku-20241022") -> str:
        if not self.client:
            raise ValueError("Anthropic client is not configured.")

        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                formatted_messages.append({"role": role, "content": content})

        response = self.client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=formatted_messages
        )
        if response and response.content:
            return response.content[0].text
        return ""
