# from fastapi import FastAPI
# from pydantic import BaseModel
# from typing import List
# from dotenv import load_dotenv
#
# import os
# import re
#
# from hf_client.client import HFClient
#
# load_dotenv()
#
# app = FastAPI()
# client = HFClient(os.getenv("HF_API_KEY"))
#
#
# class Message(BaseModel):
#     role: str
#     content: str
#
#
# class ChatRequest(BaseModel):
#     message: str
#     history: List[Message]
#
#
# # Define a response model to include token counts and processed context
# class ChatResponse(BaseModel):
#     response: str
#     request_token_count: int
#     response_token_count: int
#
#
# def count_tokens(text: str) -> int:
#     # Count tokens by splitting text based on whitespace
#     tokens = re.findall(r'\S+', text)
#     return len(tokens)
#
#
# @app.get("/heartbeat")
# async def heartbeat():
#     return {"status": "OK"}
#
#
# @app.post("/chat", response_model=ChatResponse)
# async def chat_endpoint(request: ChatRequest):
#     # Extract context from the request
#     context = request.message
#
#     # Token count of the request context
#     request_token_count = count_tokens(context)
#
#     messages = [
#         {"role": "user", "content": context}
#     ]
#
#     response = await client.chat(messages)
#     print(response)
#
#     # Example with streaming
#     # print("\nStreaming response:")
#     # async for chunk in client.chat([message], stream=True):
#     #     print(chunk, end="", flush=True)
#
# # Token count of the response context
#     response_token_count = count_tokens(response)
#
#     # Return the processed context and token counts in a JSON response
#     return ChatResponse(
#         response=response,
#         request_token_count=request_token_count,
#         response_token_count=response_token_count
#     )
#
#
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="localhost", port=3000)
import os
import asyncio
from pathlib import Path
from model_manager import ModelManager
from llm_engine import LocalLLMEngine

from dotenv import load_dotenv

load_dotenv()


async def main():
    # Get cache directory from environment variable or use default
    cache_dir = os.getenv('HF_HOME', str(
        Path.home() / 'models' / 'huggingface'))

    # Initialize LLM Engine
    engine = LocalLLMEngine(
        default_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    )

    # Initialize model manager
    model_manager = ModelManager(cache_dir=cache_dir)

    # Print available models
    print("\nRegistered Models:")
    for model_info in model_manager.list_registered_models():
        status = "Downloaded" if model_info.is_downloaded else "Not Downloaded"
        size = f"{model_info.size_gb:.2f}GB" if model_info.size_gb else "N/A"
        print(f"- {model_info.model_id}: {status}, Size: {size}")

    try:
        # Example 1: Generate with default model
        print("\nGenerating with default model...")
        responses = await engine.generate(
            model_manager,
            "What is machine learning?",
            max_new_tokens=100
        )
        print("Response:", responses[0])
        #
        # # Example 2: Generate with a different model
        # print("\nSwitching to a different model...")
        # responses = await engine.generate(
        #     "Explain what is Python in simple terms.",
        #     model_id="gpt2",
        #     max_new_tokens=50
        # )
        # print("Response:", responses[0])
        #
        # # Example 3: Load a specific model with 4-bit quantization
        # print("\nLoading model with 4-bit quantization...")
        # await engine.load_model(
        #     "mistralai/Mistral-7B-Instruct-v0.3",
        #     load_in_4bit=True
        # )
        #
        # responses = await engine.generate(
        #     "Write a short poem about coding.",
        #     max_new_tokens=100
        # )
        # print("Response:", responses[0])
        #
    finally:
        # Clean up resources
        engine.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
