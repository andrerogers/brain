from typing import Dict, List

from huggingface_hub import InferenceClient


class HFClient:
    def __init__(
        self,
        api_key: str,
        default_model: str = "meta-llama/Llama-3.2-3B-Instruct"
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.client = InferenceClient(api_key=self.api_key)

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat_completion(
            messages, stop=["Task"], max_tokens=1000)
        answer = response.choices[0].message.content
        return answer
