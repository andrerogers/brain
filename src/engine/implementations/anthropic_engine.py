from typing import Dict, Any
from anthropic import Anthropic

from engine import BaseEngine


class AnthropicEngine(BaseEngine):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key')
        self.llm_model = config.get('llm_model', 'claude-3-7-sonnet-20250219')
        self.max_tokens = config.get('max_tokens', 1000)

        self.client = Anthropic(api_key=self.api_key)

    def _create_prompt(self, query: str, context: str = "") -> str:
        if len(context) > 0:
            """Create a prompt with the query and context."""
            return f"""Use the following information to answer the user's question:

    Context:
    {context}

    User Question: {query}

    Answer:"""
        else:
            return f"""Answer the user's question:
    User Question: {query}

    Answer:"""

    async def stream_response(self, question):
        prompt = self._create_prompt(question)

        with self.client.messages.stream(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
        ) as stream:
            for text in stream.text_stream:
                yield {"event": "token", "data": text}

    async def get_response(self, question):
        prompt = self._create_prompt(question)

        response = self.client.messages.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.content[0].text
        }
