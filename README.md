# Brain

A modular AI service with interchangeable LLM backends for Retrieval-Augmented Generation (RAG).

## Project Structure

```
/brain/
├── .env                   # Environment variables
├── .gitignore             # Git ignore file
├── README.md              # This file
├── pyproject.toml         # Poetry configuration
├── poetry.lock            # Poetry lock file
└── src/                   # Source code
    ├── api/               # API layer
    │   ├── models/        # API data models
    │   │   ├── __init__.py
    │   │   └── schemas.py
    │   ├── routes/        # API routes
    │   ├── __init__.py
    │   ├── app.py         # FastAPI application setup
    │   └── dependencies.py # FastAPI dependencies
    ├── engine/            # Core engine
    │   ├── implementations/ # LLM provider implementations
    │   │   ├── __init__.py
    │   │   ├── anthropic_engine.py
    │   │   └── openai_engine.py
    │   ├── __init__.py
    │   ├── base.py        # Base Engine abstract class
    │   └── factory.py     # Factory for creating engine instances
    ├── tests/             # Test suite
    ├── config.py          # Configuration management
    └── server.py          # Main entry point
```

## Features

- **Modular Architecture**: Support for multiple LLM providers through a common interface
- **Streaming Responses**: Real-time streaming responses via Server-Sent Events (SSE)
- **Document Management**: Add and retrieve documents for the RAG system
- **Easy Configuration**: Configure via environment variables or `.env` file
- **High-Performance**: Built on FastAPI for high-performance API responses

## Supported LLM Providers

- **Anthropic Claude**: Integrated with Claude 3.7 Sonnet for both embeddings and responses
- **OpenAI**: Support for OpenAI embeddings and GPT models [TODO]

## Tech Stack

- Python 3.10+
- FastAPI
- Anthropic API
- OpenAI API
- Pydantic for data validation
- Server-Sent Events (SSE) for streaming

## Getting Started

### Prerequisites

- Python 3.10 or later
- API keys for Anthropic and/or OpenAI

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/andererogers/brain.git
   cd brain
   ```

2. Install dependencies with Poetry:
   ```bash
   poetry install
   ```

3. Create a `.env` file in the project root:
   ```
   # Server settings
   HOST=0.0.0.0
   PORT=8000
   DEBUG=true

   # LLM settings
   LLM_TYPE=anthropic  # Options: 'anthropic' or 'openai'

   # RAG settings
   RAG_TOP_K=3

   # Anthropic settings
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ANTHROPIC_EMBEDDING_MODEL=claude-3-7-embeddings-v1
   ANTHROPIC_LLM_MODEL=claude-3-7-sonnet-20250219

   # OpenAI settings
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_EMBEDDING_MODEL=text-embedding-3-large
   OPENAI_LLM_MODEL=gpt-4
   ```

### Running the Server

Start the server with:

```bash
python src/server.py
```

The server will be available at `http://localhost:8000` (or the host/port configured in your settings).

## API Usage

### Add Documents

```bash
curl -X POST "http://localhost:8000/documents" \
  -H "Content-Type: application/json" \
  -d '{"documents": ["Document 1 content", "Document 2 content"]}'
```

### Query (Non-Streaming)

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What information do you have about Python?"}'
```

### Streaming Response

```
GET http://localhost:8000/query/stream?query=What%20is%20RAG?
```

Consume the stream with JavaScript:

```javascript
const eventSource = new EventSource('/query/stream?query=What is RAG?');

eventSource.addEventListener('token', (event) => {
  // Append each token to the UI
  document.getElementById('response').textContent += event.data;
});

eventSource.addEventListener('metadata', (event) => {
  // Display source documents
  const metadata = JSON.parse(event.data);
  console.log('Sources:', metadata.sources);
});
```

## Development

### Project Organization

- `src/api`: API layer with FastAPI routes and dependencies
- `src/engine`: Core RAG implementations with abstract base classes
- `src/config.py`: Configuration management
- `src/server.py`: Main entry point

### Adding a New LLM Provider

1. Create a new implementation file in `src/engine/implementations/`
2. Implement the `BaseEngine` abstract class
3. Add the new implementation to the `EngineFactory` in `src/engine/factory.py`
4. Update the configuration to support the new provider

### Example CuRl's

````bash
curl "http://localhost:8000/info/health

curl -X POST http://localhost:8000/query/response -H "Content-Type: application/json" -d '{
    "query": "What is the capital of France?",
    "top_k": 5
  }' --no-buffer

curl -X POST http://localhost:8000/query/stream -H "Content-Type: application/json" -H "Accept: text/event-stream" -d '{
    "query": "What is the capital of Canada?",
    "top_k": 5
  }' --no-buffer
````
