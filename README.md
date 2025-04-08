# Brain 

A Python monorepo containing microservices for AI-powered applications.

```bash
monorepo/
├── pyproject.toml        # Project dependencies and metadata
├── services/             # Contains each microservice
│   ├── sse_server/       # SSE server using FastAPI
│   ├── llm_engine/       # LLM processing service
│   ├── fine_tuning/      # Fine-tuning service
│   ├── rag_engine/       # RAG engine service
│   └── memory/           # Memory service (long/short term)
├── shared/               # Shared code, models, utilities
│   ├── models/           # Shared data models
│   ├── config/           # Configuration utilities
│   └── utils/            # Shared utility functions
└── scripts/              # Deployment and utility scripts
    ├── local_dev.py      # Script to run all services locally
    └── deploy.py         # Deployment orchestration
```

## Services

- **SSE Server**: FastAPI-based Server-Sent Events endpoint for real-time updates
- **LLM Engine**: Processing engine for Large Language Models
- **Fine Tuning**: Service for fine-tuning LLMs
- **RAG Engine**: Retrieval-Augmented Generation implementation
- **Memory**: Long and short-term memory storage services

## Tech Stack

- Python 3.10+
- FastAPI
- Hugging Face Transformers
- (Future support for OpenAI, Anthropic)

## Getting Started

### Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) for Python version management
- [Poetry](https://python-poetry.org/) for dependency management

### Environment Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-services.git
cd ai-services

# Install the correct Python version with pyenv
# The .python-version file will automatically set the Python version
pyenv install 3.10.12 # if not already installed
pyenv local 3.10.12   # explicitly set the version (optional, as .python-version handles this)

# Install dependencies with Poetry
poetry install

# Activate the virtual environment
poetry env activate 

# Load environment variables
source .env
```

### Running Services Locally

```bash
# Start all services in development mode
python scripts/local_dev.py
```

## Development

Each service is designed to run independently while sharing common utilities and models from the `shared` directory.

### Adding Dependencies

```bash
# Add a core dependency
poetry add package-name

# Add a service-specific dependency
poetry add --group service-name package-name

# Add a development dependency
poetry add --group dev package-name
```

## Deployment

Designed for home server deployment with support for future scaling.

```bash
# Deploy services
python scripts/deploy.py
```
