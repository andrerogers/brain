from typing import Dict, Any
from openai import OpenAI

from engine import BaseEngine


class OpenAIEngine(BaseEngine):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key')
        self.llm_model = config.get('llm_model', 'gpt-4')
        self.max_tokens = config.get('max_tokens', 1000)

        self.client = OpenAI(api_key=self.api_key)

    def _create_system_message(self, question: str) -> str:
        return f"""You are a helpful assistant. Use the following information \
        to answer the user's question:

{question}

Answer based only on the information provided. If you don't know, say so."""

    async def stream_response(self, question):
        sys_message = self._create_system_message(question)
        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": sys_message},
                {"role": "user", "content": question}
                ],
            max_tokens=self.max_tokens,
            stream=True
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield {"event": "token", "data": chunk.choices[0].delta.content}

    def get_response(self, question):
        sys_message = self._create_system_message(question)

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": sys_message},
                {"role": "user", "content": question}
                ],
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.choices[0].message.content
        }

