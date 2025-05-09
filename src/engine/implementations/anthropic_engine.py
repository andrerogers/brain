import json
import anthropic
import numpy as np

from typing import Dict, Any
from sklearn.metrics.pairwise import cosine_similarity

from src.engine import BaseEngine


class AnthropicEngine(BaseEngine):
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key')
        self.embedding_model = config.get('embedding_model',
                                          'claude-3-7-embeddings-v1')
        self.llm_model = config.get('llm_model', 'claude-3-7-sonnet-20250219')
        self.max_tokens = config.get('max_tokens', 1000)

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.documents = []
        self.embeddings = []

    def _create_prompt(self, query: str, context: str) -> str:
        if context:
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
        # If there are no embeddings, return an empty list
        if not self.embeddings:
            return []

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
        prompt = self._create_prompt(question, context)

        yield {
            "event": "metadata",
            "data": json.dumps({
                "sources": relevant_docs
            })
        }

        with self.client.messages.stream(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
        ) as stream:
            for text in stream.text_stream:
                yield {"event": "token", "data": text}

    async def get_response(self, question, top_k=3):
        relevant_docs = await self.get_relevant_docs(question, top_k)
        context = "\n\n".join(relevant_docs)
        prompt = self._create_prompt(question, context)

        response = self.client.messages.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.content[0].text,
            "sources": relevant_docs
        }
