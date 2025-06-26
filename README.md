# Brain

A sophisticated multi-agent system that facilitates interactions between a central Large Language Model (LLM) and specialized agents using the Multi-Agent Communication Protocol (MCP). Brain provides both WebSocket and REST API interfaces for seamless integration with development tools and workflows.

## 🚀 Features

- **Production-Ready Multi-Agent System**: 5 auto-connecting MCP servers providing 33 specialized tools
- **Intelligent Query Processing**: LLM-powered intent analysis with automatic server routing
- **Real-time Communication**: WebSocket server with progress callbacks and metrics tracking
- **Comprehensive Development Tools**: Complete filesystem, git, code analysis, and development automation
- **Real-time Information Access**: Web search and content crawling via Exa integration
- **Performance Monitoring**: Token counting, timing metrics, and detailed query analytics
- **Robust Testing**: 83 comprehensive tests with 78% pass rate covering all functionality
- **Security-First Design**: Validated file operations and secure command execution
- **Multiple LLM Providers**: Support for Anthropic Claude and OpenAI GPT models
- **Professional CLI Integration**: Seamless integration with Brain Surf CLI client

## 🏗️ Architecture

### Core Components

- **Engine Layer**: Abstract LLM provider interface with Anthropic and OpenAI implementations
- **MCP Integration**: Multi-server client with intelligent query routing and tool federation
- **WebSocket Server**: Real-time communication interface for interactive clients
- **REST API**: HTTP endpoints with FastAPI for web integration
- **Built-in Servers**: Specialized MCP servers for development workflows

### Built-in MCP Servers

The system automatically connects to 5 specialized servers on startup:

1. **Filesystem Server** (8 tools): Complete file operations with home directory expansion and security validation
2. **Git Server** (11 tools): Full version control workflow including staging, commits, branches, and history
3. **Codebase Server** (6 tools): Project analysis, structure discovery, definition finding, and documentation
4. **DevTools Server** (6 tools): Development automation with secure command execution and comprehensive tooling
5. **Exa Server** (2 tools): Real-time web search, content crawling, and current information access

**Total: 33 tools across 5 servers - All auto-connecting on startup**

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) for dependency management

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd brain
   ```

2. **Install uv (if not already installed):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Create and activate virtual environment:**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

5. **For development, install dev dependencies:**
   ```bash
   uv pip install -r requirements-dev.txt
   ```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# LLM Engine Configuration
ENGINE_TYPE=anthropic  # Options: 'anthropic' or 'openai'

# Anthropic Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-7-sonnet-20250219
ANTHROPIC_EMBEDDING_MODEL=claude-3-7-embeddings-v1

# OpenAI Configuration (if using OpenAI)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Exa Search Configuration
EXA_API_KEY=your_exa_api_key_here

# Server Configuration
HOST=localhost
PORT=3789
DEBUG=true  # Enable detailed debug logging
```

## 🚀 Usage

### Starting the Server

```bash
python src/main.py
```

The Brain server will:
- Start WebSocket server on `ws://localhost:3789`
- Auto-connect to all 5 built-in MCP servers (33 tools total)
- Initialize configuration directory at `~/.brain/`
- Set up comprehensive logging to `~/.brain/brain.log`
- Display real-time server status and tool counts

### WebSocket Interface

Connect to `ws://localhost:3789` and send JSON commands:

#### Available Commands

**1. Query Processing**
```json
{
  "command": "query",
  "query": "analyze this project structure"
}
```

**2. List Connected Servers**
```json
{
  "command": "get_servers"
}
```

**3. List Tools from Specific Server**
```json
{
  "command": "list_tools",
  "server_id": "filesystem"
}
```

**4. Connect Custom MCP Server**
```json
{
  "command": "connect_server",
  "server_id": "custom_server",
  "server_config": "/path/to/server.py"
}
```

### REST API Interface

The server also exposes REST endpoints (requires FastAPI setup):

- `POST /query/response` - Standard query processing
- `POST /query/stream` - Streaming responses with Server-Sent Events
- `GET /info/*` - System information endpoints

## 🛠️ Development

### Testing and Code Quality

```bash
# Run comprehensive test suite
pytest                              # All 83 tests
pytest tests/test_integration.py    # Integration tests
pytest -v                          # Verbose output

# Code quality tools
black src/                          # Format code (88 char line length)
isort src/                          # Sort imports
ruff src/                           # Lint code
mypy src/                           # Type checking (strict mode)

# Manual testing
python test_mcp_servers.py          # Quick server validation
```

### Adding Dependencies

```bash
# Add production dependency
uv add package_name
uv pip freeze > requirements.txt

# Add development dependency
uv pip install --dev package_name
uv pip freeze --dev > requirements-dev.txt
```

### Project Structure

```
brain/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── engine/              # LLM provider abstraction
│   │   ├── base.py          # Abstract base engine
│   │   ├── factory.py       # Engine factory
│   │   └── implementations/ # LLM provider implementations
│   ├── mcp_brain/           # MCP client and servers
│   │   ├── mcp_client.py    # Multi-server MCP client
│   │   └── servers/         # Built-in MCP servers
│   ├── websocket_server/    # WebSocket server implementation
│   └── api/                 # REST API endpoints
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
└── .env                    # Environment configuration
```

## 🔧 Configuration

### MCP Server Settings

Custom server configurations are stored in `~/.brain/mcp.settings.json`:

```json
{
  "servers": {
    "custom_server": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "transport": "stdio"
    }
  }
}
```

### Logging

- **Location**: `~/.brain/brain.log`
- **Debug Mode**: Set `DEBUG=true` in `.env` for detailed logging
- **Tool Call Traces**: Debug mode includes detailed tool execution logs

## 🔗 Integration

### CLI Client

The Brain system is designed to work with the companion CLI client ([brain-surf-cli](../brain-surf-cli/)):

```bash
# Install CLI globally
npm link /path/to/brain-surf-cli

# Use the CLI
brain "analyze this codebase"
brain  # Start interactive REPL
```

### WebSocket Clients

Connect to the Brain server from any WebSocket client:

```javascript
const ws = new WebSocket('ws://localhost:3789');
ws.send(JSON.stringify({
  command: 'query',
  query: 'What files are in the current directory?'
}));
```

## 📚 API Reference

### Engine Interface

```python
from brain.engine.base import BaseEngine

class CustomEngine(BaseEngine):
    async def stream_response(self, messages, tools=None, system=None):
        # Implement streaming response
        pass
    
    async def get_response(self, messages, tools=None, system=None):
        # Implement standard response
        pass
```

### MCP Server Development

Built-in servers follow the MCP specification. See `src/mcp_brain/servers/` for examples.

## 🐛 Troubleshooting

### Common Issues

**Connection Issues:**
- Ensure the server is running on the correct port
- Check firewall settings for WebSocket connections
- Verify environment variables are set correctly

**MCP Server Issues:**
- Check `~/.brain/brain.log` for detailed error messages
- Ensure MCP server scripts are executable
- Verify Python path and dependencies

**API Key Issues:**
- Confirm API keys are set in `.env` file
- Test API keys with direct provider calls
- Check API key permissions and rate limits

For more detailed troubleshooting, enable debug mode with `DEBUG=true` in your `.env` file.
