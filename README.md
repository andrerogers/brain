# Brain

SSE Server & AI Processing Engine - A modular AI service with interchangeable LLM backends to stream or provide a response.

## Project Structure

```
/brain/
├── .env                   # Environment variables
├── .gitignore             # Git ignore file
├── README.md              # This file
├── pyproject.toml         # Tool configuration
├── requirements.txt       # Main dependencies
├── requirements-dev.txt   # Development dependencies
├── requirements-lock.txt  # Locked dependencies (generated)
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
- **Easy Configuration**: Configure via environment variables or `.env` file
- **High-Performance**: Built on FastAPI for high-performance API responses

## Supported LLM Providers

- **Anthropic Claude**: Integrated with Claude 3.7 Sonnet
- **OpenAI**: Support for OpenAI embeddings and GPT models

## Tech Stack

- Python 3.10+
- FastAPI
- Anthropic API
- OpenAI API
- Pydantic for data validation
- Server-Sent Events (SSE) for streaming
- uv for dependency management

## Developer Guide

### Prerequisites

- Python 3.10 or later
- API keys for Anthropic and/or OpenAI
- uv package manager (`pip install uv`)

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/brain.git
   cd brain
   ```

2. Create a virtual environment:
   ```bash
   # Create a new virtual environment
   uv venv

   # Activate the virtual environment
   # On Windows
   .venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   # Install main dependencies
   uv pip install -r requirements.txt
   
   # For development, install dev dependencies
   uv pip install -r requirements-dev.txt
   ```

### Environment Configuration

Create a `.env` file in the project root:
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

Start the development server:
```bash
python src/server.py
```

The server will be available at `http://localhost:8000` (or the host/port configured in your settings).

### Development Workflow

#### Adding New Dependencies

To add a new dependency:

```bash
# Add a production dependency
uv pip install package_name
uv pip freeze > requirements.txt

# Add a development dependency
uv pip install --dev package_name
uv pip freeze --dev > requirements-dev.txt

# Generate a lock file
uv pip freeze > requirements-lock.txt
```

#### Updating Dependencies

To update dependencies:

```bash
# Update all dependencies
uv pip install -U -r requirements.txt
uv pip freeze > requirements.txt

# Update a specific package
uv pip install -U package_name
uv pip freeze > requirements.txt

# Update development dependencies
uv pip install -U -r requirements-dev.txt
uv pip freeze --dev > requirements-dev.txt
```

#### Linting and Formatting

```bash
# Format code with Black
black src

# Sort imports with isort
isort src

# Lint with Ruff
ruff check src

# Type checking with mypy
mypy src
```

#### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_specific.py
```

#### Building for Distribution

Create a distributable package:

```bash
# Build a wheel
python -m build

# Install locally for testing
uv pip install -e .
```

### API Usage

#### Streaming Example (JavaScript)

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

// Handle connection open
eventSource.onopen = () => {
  console.log('Connection established');
};

// Handle errors
eventSource.onerror = (error) => {
  console.error('EventSource error:', error);
  eventSource.close();
};
```

#### REST API Examples

You can test the API using curl:

```bash
# Health check
curl "http://localhost:8000/info/health"

# Get a complete response
curl -X POST http://localhost:8000/query/response \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Canada?"}' \
  --no-buffer

# Stream a response
curl -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"query": "What is the capital of Canada?"}' \
  --no-buffer
```

## Troubleshooting

### Common Issues

1. **Missing dependencies**:
   - Run `uv pip install -r requirements.txt` to ensure all dependencies are installed

2. **Environment activation issues**:
   - Ensure you've activated the virtual environment before running any commands

3. **Permission errors**:
   - Use `sudo` on Linux/macOS if necessary for global installations
   - On Windows, try running the command prompt as administrator

4. **API key issues**:
   - Verify that your `.env` file contains valid API keys
   - Check for any whitespace in your API keys

### Debugging

For more verbose output:

1. Set `DEBUG=true` in your `.env` file
2. Run the server with debug logging:
   ```bash
   uvicorn src.server:app --reload --log-level debug
   ```

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/my-new-feature`
5. Submit a pull request

Please ensure your code follows the project's style guidelines and passes all tests.
