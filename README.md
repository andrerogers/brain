# Brain

A sophisticated multi-agent system that orchestrates interactions between specialized AI agents and MCP-based tool providers. The system features a three-phase agent workflow (Planning → Orchestration → Execution) with real-time WebSocket communication and comprehensive observability.

## 🚀 Features

- **Multi-Agent Orchestration**: Three specialized agents (Planning, Orchestrator, Execution) with distinct responsibilities
- **Real-time Communication**: FastAPI WebSocket server with streaming progress updates and session management
- **Intelligent Agent Workflow**: Three-phase reasoning system with task decomposition and tool orchestration
- **Comprehensive Tool Integration**: 5 auto-connecting MCP servers providing 33 specialized tools
- **Advanced Observability**: Logfire integration with comprehensive tracing and performance monitoring
- **Production-Ready Architecture**: Session-based client management with concurrent connection support
- **Comprehensive Development Tools**: Complete filesystem, git, code analysis, and development automation
- **Real-time Information Access**: Web search and content crawling via Exa integration
- **Security-First Design**: Validated file operations and secure command execution
- **Pydantic AI Framework**: Multi-agent orchestration with comprehensive instrumentation

## 🏗️ Architecture

### Core Components

- **Agent System** (`src/agent/`): Multi-agent orchestration with specialized capabilities
  - `AgentEngine`: Central coordination hub managing agent lifecycle and workflow
  - `WorkflowExecutor`: Coordinates three-phase agent workflow with progress tracking
  - `agents/`: Specialized agent implementations (Planning, Orchestrator, Execution)
  - `models.py`: Pydantic models for agent configurations and data structures
  - `tasks.py`: Task management with reasoning chains and progress tracking

- **Application Layer** (`src/app/`): High-level coordination and WebSocket handling
  - `AppCoordinator`: System-wide coordination and resource management
  - `WebSocketHandler`: Command routing and session management
  - `AppStreamingHandler`: Real-time progress updates and client communication
  - `ToolBridge`: Unified tool abstraction layer with validation
  - `ToolAdapters`: Adapter pattern for different tool types (MCP, Langchain)

- **MCP Infrastructure** (`src/tools/`): Multi-server MCP client with enhanced capabilities
  - `MCPClient`: Multi-server connection management with session tracking
  - `servers/`: Built-in MCP servers for development workflows (5 servers, 33 tools)
  - Intelligent tool selection and parameter validation
  - Comprehensive error handling and retry logic

- **WebSocket Server** (`src/server.py`): FastAPI-based real-time communication
  - Session-based client management with UUID tracking
  - Rich command set for agent interaction and system status
  - Real-time progress streaming and workflow visibility
  - Concurrent connection support with clean session isolation

### Multi-Agent Workflow System

The system implements a three-phase agent workflow for sophisticated query processing:

**Phase 1: Planning Agent** (`agents/planning_agent.py`)
- **Role**: Query analysis and strategic planning
- **Capabilities**: Query complexity analysis, task breakdown with dependency mapping, resource estimation
- **Tools**: Primarily codebase and filesystem tools for analysis
- **Output**: Structured task list with priority and dependency information

**Phase 2: Orchestrator Agent** (`agents/orchestrator_agent.py`)
- **Role**: Workflow coordination and tool orchestration
- **Capabilities**: Tool selection based on task requirements, execution sequence optimization, dependency resolution
- **Tools**: Access to all available tools for intelligent selection
- **Output**: Optimized execution plans with tool mappings and parameters

**Phase 3: Execution Agent** (`agents/execution_agent.py`)
- **Role**: Tool execution and result processing
- **Capabilities**: Tool execution with comprehensive error handling, result aggregation and synthesis, progress reporting
- **Tools**: Executes all tools as orchestrated by the system
- **Output**: Synthesized results with reasoning chain and final response

### Built-in MCP Servers (Auto-Connecting)

The system automatically connects to 5 specialized MCP servers on startup, providing 33 total tools:

1. **Filesystem Server** (`servers/filesystem_server.py`) - **8 tools**:
   - File operations: read, write, edit, list, search, create directories, delete files, get file info
   - Home directory expansion support (~/path resolution)
   - Security path validation and access control

2. **Git Server** (`servers/git_server.py`) - **11 tools**:
   - Version control: status, diff, log, commit, branch management, stash operations
   - History search, file staging, commit viewing, reset operations
   - Git workflow automation and repository information

3. **Codebase Server** (`servers/codebase_server.py`) - **6 tools**:
   - Project analysis: structure discovery, definition finding, reference tracking
   - Architecture understanding and code context generation
   - Project documentation and technical insights

4. **DevTools Server** (`servers/devtools_server.py`) - **6 tools**:
   - Development automation: test execution, linting, formatting, type checking
   - Secure command execution with comprehensive shell utility whitelist
   - Dependency management and development workflow automation

5. **Exa Server** (`servers/exa_server.py`) - **2 tools**:
   - Real-time web search with intelligent content extraction  
   - URL crawling with content cleaning (removes navigation, ads, footers)
   - Current events and real-time information access

### Agent Workflow

WebSocket Query → server.py → app/handler.py → app/streaming.py → app/coordinator.py → agent/engine.py → agent/workflow.py → agents → tool_bridge → tool_adapters → MCP servers

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
# LLM Configuration for Pydantic AI Agents
ANTHROPIC_API_KEY=your_anthropic_key    # Required for agent system
OPENAI_API_KEY=your_openai_key          # Optional: for OpenAI models

# Agent Model Configuration
PLANNING_MODEL=anthropic:claude-3-5-sonnet-latest
ORCHESTRATOR_MODEL=anthropic:claude-3-5-sonnet-latest
EXECUTION_MODEL=anthropic:claude-3-5-sonnet-latest

# MCP Server API Keys
EXA_API_KEY=your_exa_api_key            # For web search functionality

# Server Configuration
HOST=localhost                          # WebSocket server host
PORT=3789                              # WebSocket server port

# Observability and Logging
DEBUG=false                             # Enable detailed debug logging
LOGFIRE_ENABLED=true                    # Enable Pydantic AI + Logfire observability
LOGFIRE_TOKEN=your_logfire_token        # Optional: Logfire project token
LOGFIRE_SERVICE_NAME=brain              # Service name for Logfire traces
```

## 🚀 Usage

### Starting the Server

```bash
python src/main.py
```

The Brain server will:

- Start FastAPI WebSocket server on `ws://localhost:3789`
- Auto-connect to all 5 built-in MCP servers (33 tools total)
- Initialize agent engine with Planning, Orchestrator, and Execution agents
- Set up Logfire observability and comprehensive tracing
- Initialize configuration directory at `~/.brain/`
- Set up comprehensive logging to `~/.brain/brain.log`
- Display real-time server status and agent workflow capabilities

### WebSocket Interface

Connect to `ws://localhost:3789` and send JSON commands:

#### Available Commands

**Agent Commands:**

```json
{
  "command": "agent_query",
  "query": "analyze this project structure"
}
```

```json
{
  "command": "get_agents"
}
```

```json
{
  "command": "get_workflow"
}
```

```json
{
  "command": "get_tasks"
}
```

```json
{
  "command": "get_reasoning"
}
```

```json
{
  "command": "cancel_workflow"
}
```

**System Commands:**

```json
{
  "command": "get_servers"
}
```

```json
{
  "command": "list_tools",
  "server_id": "filesystem"
}
```

```json
{
  "command": "system_status"
}
```

```json
{
  "command": "tool_execute",
  "tool_name": "read_file",
  "parameters": {"path": "./src/main.py"}
}
```

```json
{
  "command": "complexity_analysis",
  "query": "analyze codebase complexity"
}
```

### Response Messages

The server sends various response types:

- `agent_response`: Multi-agent workflow results with reasoning chain
- `workflow_progress`: Real-time workflow progress updates
- `agent_status`: Individual agent status and performance metrics
- `thinking`: Intermediate processing status with phase information
- `tool_execution`: Tool execution results and metrics
- `error`: Error messages with detailed context and recovery guidance

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
│   ├── server.py            # FastAPI WebSocket server
│   ├── agent/               # Multi-agent orchestration
│   │   ├── engine.py        # Agent engine coordination
│   │   ├── workflow.py      # Three-phase workflow executor
│   │   ├── models.py        # Pydantic models
│   │   ├── tasks.py         # Task management
│   │   └── agents/          # Specialized agent implementations
│   │       ├── planning_agent.py
│   │       ├── orchestrator_agent.py
│   │       └── execution_agent.py
│   ├── app/                 # Application layer
│   │   ├── coordinator.py   # System coordination
│   │   ├── handler.py       # WebSocket command routing
│   │   ├── streaming.py     # Real-time progress updates
│   │   ├── tool_bridge.py   # Tool abstraction layer
│   │   └── tool_adapters.py # Unified tool interface
│   └── tools/               # MCP infrastructure
│       ├── client.py        # Multi-server MCP client
│       └── servers/         # Built-in MCP servers
│           ├── filesystem_server.py
│           ├── git_server.py
│           ├── codebase_server.py
│           ├── devtools_server.py
│           └── exa_server.py
├── documentation/           # Architecture documentation
│   ├── architecture.md
│   └── system_introduction.md
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
└── .env                    # Environment configuration
```

## 🔧 Configuration

### Data Storage

- **Configuration**: `~/.brain/` directory for user settings
- **MCP Settings**: `~/.brain/mcp.settings.json` for server configurations
- **Logs**: `~/.brain/brain.log` with configurable debug levels
- **Session Data**: In-memory with automatic cleanup

### Logging and Observability

- **Location**: `~/.brain/brain.log`
- **Debug Mode**: Set `DEBUG=true` in `.env` for detailed logging
- **Logfire Integration**: Comprehensive tracing and performance monitoring
- **Agent Workflow Visibility**: Real-time agent collaboration and tool orchestration
- **Tool Call Traces**: Debug mode includes detailed tool execution logs

## 🔗 Integration

### WebSocket Clients

Connect to the Brain server from any WebSocket client:

```javascript
const ws = new WebSocket("ws://localhost:3789");
ws.send(
  JSON.stringify({
    command: "agent_query",
    query: "What files are in the current directory?",
  }),
);
```

### Real-time Progress Updates

The server provides streaming progress updates during agent workflow execution:

```javascript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'workflow_progress':
      console.log(`Phase: ${message.phase}, Progress: ${message.progress}%`);
      break;
    case 'agent_status':
      console.log(`Agent: ${message.agent}, Status: ${message.status}`);
      break;
    case 'agent_response':
      console.log('Final Result:', message.result);
      break;
  }
};
```

## 📚 API Reference

### Agent Development

```python
from pydantic_ai import Agent
from brain.agent.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self, name: str, model: str):
        super().__init__(name, model)
        self.agent = Agent(model=model)
    
    async def process(self, query: str, context: dict) -> dict:
        # Implement agent-specific processing
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
