from typing import Dict, List, Any
from anthropic import Anthropic

from engine import BaseEngine


class AnthropicEngine(BaseEngine):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key')
        self.llm_model = config.get('llm_model', 'claude-3-7-sonnet-20250219')
        self.max_tokens = config.get('max_tokens', 1000)
        self.messages = []

        self.client = Anthropic(api_key=self.api_key)

    async def stream_response(self, question):
        prompt = self._create_prompt(question)

        with self.client.messages.stream(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
        ) as stream:
            for text in stream.text_stream:
                yield {"event": "token", "data": text}

    async def get_response(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], system_message: str = '') -> Dict[str, Any]:
        self.messages.extend(messages)

        if system_message == '':
            response = self.client.messages.create(
                model=self.llm_model,
                messages=self.messages,
                max_tokens=self.max_tokens,
                tools=tools
            )
        else:
            response = self.client.messages.create(
                model=self.llm_model,
                system=system_message,
                messages=self.messages,
                max_tokens=self.max_tokens,
                tools=tools
            )

        return response
