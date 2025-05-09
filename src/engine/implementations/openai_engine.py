import json
import openai
import numpy as np

from typing import Dict, Any
from sklearn.metrics.pairwise import cosine_similarity

from src.engine import BaseEngine


class OpenAIEngine(BaseEngine):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key')
        self.embedding_model = config.get('embedding_model',
                                          'text-embedding-3-large')
        self.llm_model = config.get('llm_model', 'gpt-4')
        self.max_tokens = config.get('max_tokens', 1000)

        self.client = openai.OpenAI(api_key=self.api_key)
        self.documents = []
        self.embeddings = []

    def _create_system_message(self, context: str) -> str:
        """Create a system message with context."""
        return f"""You are a helpful assistant. Use the following information \
        to answer the user's question:

{context}

Answer based only on the information provided. If you don't know, say so."""

    def add_documents(self, documents):
        if not documents:
            return

        self.documents.extend(documents)

        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=documents
        )

        self.embeddings.extend(
            [item.embedding for item in response.embeddings]
        )

    # TODO: There should be a way to improve this
    async def get_relevant_docs(self, question, top_k=3):
        query_response = self.client.embeddings.create(
            model=self.embedding_model,
            input=[question]
        )
        query_embedding = query_response.embeddings[0].embedding

        # Find most similar documents
        similarities = []
        for doc_embedding in self.embeddings:
            query_vec = np.array(query_embedding).reshape(1, -1)
            doc_vec = np.array(doc_embedding).reshape(1, -1)
            similarity = cosine_similarity(query_vec, doc_vec)[0][0]
            similarities.append(similarity)

        # Get indices of top_k most similar documents
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        # Retrieve the most relevant documents
        relevant_docs = [self.documents[i] for i in top_indices]

        return relevant_docs

    async def stream_response(self, question, top_k=3):
        relevant_docs = await self.get_relevant_docs(question, top_k)
        context = "\n\n".join(relevant_docs)
        sys_message = self._create_system_message(context)

        yield {
            "event": "metadata",
            "data": json.dumps({
                "sources": relevant_docs
            })
        }

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

    def get_response(self, question, top_k=3):
        relevant_docs = self.get_relevant_docs(question, top_k)
        context = "\n\n".join(relevant_docs)
        sys_message = self._create_system_message(context)

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": sys_message},
                {"role": "user", "content": question}
                ],
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": relevant_docs
        }

