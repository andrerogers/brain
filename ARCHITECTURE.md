# Brain: Multi-Agent System Architecture

## Overview

Brain is a sophisticated multi-agent system that facilitates intelligent interactions between a central LLM and specialized tool-providing agents via the Model Control Protocol (MCP). The system provides real-time WebSocket communication and seamless integration with development workflows through 5 specialized MCP servers providing 33 tools.

## Execution Flow

```
WebSocket Query → server.py → app/handler.py → app/streaming.py → app/coordinator.py → agent/engine.py → agent/workflow.py → agents → tool_bridge → tool_adapters → MCP servers
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Brain Multi-Agent System                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ ┌─────────────────┐  WebSocket   ┌─────────────────────────────────┐ │
│ │   WebSocket     │◄────────────►│        Application Layer        │ │
│ │   Clients       │              │                                 │ │
│ │  (brain-cli)    │              │ ┌─────────────────────────────┐ │ │
│ └─────────────────┘              │ │      app/handler.py         │ │ │
│                                  │ │   (Command Routing)         │ │ │
│ ┌─────────────────┐              │ └─────────────────────────────┘ │ │
│ │   server.py     │              │               │                 │ │
│ │   (FastAPI      │              │               ▼                 │ │
│ │   WebSocket     │              │ ┌─────────────────────────────┐ │ │
│ │   Server)       │◄─────────────┤ │    app/streaming.py         │ │ │
│ └─────────────────┘              │ │  (Real-time Updates)        │ │ │
│                                  │ └─────────────────────────────┘ │ │
│                                  │               │                 │ │
│                                  │               ▼                 │ │
│                                  │ ┌─────────────────────────────┐ │ │
│                                  │ │   app/coordinator.py        │ │ │
│                                  │ │  (System Coordination)      │ │ │
│                                  │ └─────────────────────────────┘ │ │
│                                  └─────────────┬───────────────────┘ │
│                                                │                     │
│ ┌──────────────────────────────────────────────▼───────────────────┐ │
│ │                    Agent Engine Layer                            │ │
│ │  ┌─────────────────┐    ┌────────────────────────────────────┐   │ │
│ │  │ agent/engine.py │    │      agent/workflow.py             │   │ │
│ │  │   (Agent        │◄──►│    (Multi-Agent Orchestrator)      │   │ │
│ │  │  Coordination)  │    │                                    │   │ │
│ │  └─────────────────┘    └────────────────────────────────────┘   │ │
│ │                                          │                        │ │
│ │                                          ▼                        │ │
│ │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │ │
│ │  │  Planning   │ │Orchestrator │ │ Execution   │                │ │
│ │  │   Agent     │ │   Agent     │ │   Agent     │                │ │
│ │  └─────────────┘ └─────────────┘ └─────────────┘                │ │
│ └──────────────────────────────┬─────────────────────────────────────┘ │
│                                │                                     │
│ ┌──────────────────────────────▼─────────────────────────────────────┐ │
│ │                    Tool Infrastructure Layer                      │ │
│ │  ┌─────────────────┐    ┌─────────────────────────────────────┐   │ │
│ │  │app/tool_bridge.py│◄──►│       app/tool_adapters.py          │   │ │
│ │  │  (Tool Access   │    │     (Unified Tool Interface)       │   │ │
│ │  │   & Validation) │    │                                     │   │ │
│ │  └─────────────────┘    └─────────────────────────────────────┘   │ │
│ │                                          │                        │ │
│ │                                          ▼                        │ │
│ │  ┌─────────────────────────────────────────────────────────────┐   │ │
│ │  │                tools/client.py                              │   │ │
│ │  │            (MCP Multi-Server Client)                        │   │ │
│ │  └─────────────────────────────────────────────────────────────┘   │ │
│ └──────────────────────────────┬─────────────────────────────────────┘ │
│                                │                                     │
│ ┌──────────────────────────────▼─────────────────────────────────────┐ │
│ │                       MCP Servers (33 Tools)                     │ │
│ │ ┌───────────┐ ┌───────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │ │
│ │ │Filesystem │ │    Git    │ │Codebase │ │DevTools │ │   Exa   │  │ │
│ │ │ (8 tools) │ │(11 tools) │ │(6 tools)│ │(6 tools)│ │(2 tools)│  │ │
│ │ └───────────┘ └───────────┘ └─────────┘ └─────────┘ └─────────┘  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. WebSocket Server Layer

#### Main Entry Point (`src/main.py`)

#### WebSocket Server (`src/server.py`)

### 2. Application Layer

#### WebSocket Handler (`src/app/handler.py`)

#### Streaming Handler (`src/app/streaming.py`)

#### Application Coordinator (`src/app/coordinator.py`)

### 3. Agent Engine Layer

#### Agent Engine (`src/agent/engine.py`)

##### Planning Agent (`src/agent/agents/planning_agent.py`)

- **Role**: Query analysis and strategic planning
- **Capabilities**:
  - Query complexity analysis
  - Task breakdown with dependency mapping
  - Resource and capability estimation
- **Tools**: Primarily codebase and filesystem tools for analysis

##### Orchestrator Agent (`src/agent/agents/orchestrator_agent.py`)

- **Role**: Workflow coordination and tool orchestration
- **Capabilities**:
  - Tool selection based on task requirements
  - Execution sequence optimization
  - Dependency resolution and planning
- **Tools**: Access to all available tools for selection

##### Execution Agent (`src/agent/agents/execution_agent.py`)

- **Role**: Tool execution and result processing
- **Capabilities**:
  - Tool execution with comprehensive error handling
  - Result aggregation and synthesis
  - Progress reporting and status updates
- **Tools**: Executes all tools as orchestrated by the system

#### Workflow Executor (`src/agent/workflow.py`)

### 4. Tool Infrastructure Layer

#### Tool Bridge (`src/app/tool_bridge.py`)

- **Position**: Provides application-level tool abstraction

#### Tool Adapters (`src/app/tool_adapters.py`)

- **Position**: Unified interface layer for different tool types

#### MCP Client (`src/tools/client.py`)

- **Position**: Multi-server MCP communication layer
- **Technology**: LangChain MCP adapters with MultiServerMCPClient

### 5. MCP Servers (Tool Providers)

#### Auto-Connecting Built-in Servers

##### Filesystem Server (`src/tools/servers/filesystem_server.py`)

##### Git Server (`src/tools/servers/git_server.py`)

##### Codebase Server (`src/tools/servers/codebase_server.py`)

##### DevTools Server (`src/tools/servers/devtools_server.py`)

##### Exa Server (`src/tools/servers/exa_server.py`)

## Detailed Execution Flow

### 1. System Initialization

```
main.py
├── Load configuration (.env and Pydantic settings)
├── Initialize Logfire observability and tracing
├── Create BrainServer with WebSocket configuration
├── Auto-connect to 5 built-in MCP servers (33 tools)
├── Initialize application coordinator and agent engine
└── Start FastAPI WebSocket server on port 3789
```

### 2. Client Connection and Session Management

```
WebSocket Connection Request
├── server.py accepts connection and generates session UUID
├── Initialize session manager for client context
├── Send initial status with connected servers and tool counts
├── Register client in connection registry
└── Enter message processing loop
```

### 3. Query Processing Flow

```
WebSocket Query Received
├── server.py: Receive and parse WebSocket message
├── app/handler.py: Route command and validate session
├── app/streaming.py: Initialize progress streaming and session tracking
├── app/coordinator.py: Coordinate system resources and initiate processing
├── agent/engine.py: Initialize agent workflow with tool bridge injection
├── agent/workflow.py: Execute three-phase agent workflow
│   ├── Planning Agent: Analyze query → create task list
│   ├── Orchestrator Agent: Review tasks → create execution plans
│   └── Execution Agent: Execute plans → synthesize results
├── tool_bridge: Validate and route tool requests
├── tool_adapters: Provide unified tool interface
├── tools/client.py: Execute via MCP session management
├── MCP servers: Return tool execution results
└── Stream final reasoning chain back to client
```

### 4. Tool Execution Sub-Flow

```
Tool Execution Request
├── tool_bridge: Validate parameters and find server
├── tool_adapters: Create unified tool interface
├── tools/client.py: Create MCP session for appropriate server
├── LangChain MCP adapter: Convert to server-specific format
├── MCP server: Execute tool and return results
├── tools/client.py: Process results and update metrics
├── tool_bridge: Format response and handle errors
└── Return structured response to agent
```

## Key Design Patterns

### 1. Streaming Architecture

- **Pattern**: Publisher-Subscriber with real-time updates
- **Implementation**: WebSocket with progress callbacks through app/streaming.py
- **Benefits**: Real-time visibility into complex multi-agent workflows

### 2. Multi-Layer Command Routing

- **Pattern**: Chain of Responsibility with specialized handlers
- **Implementation**: server.py → app/handler.py → app/streaming.py → app/coordinator.py
- **Benefits**: Clear separation of concerns, extensible command handling

### 3. Tool Abstraction and Adaptation

- **Pattern**: Adapter pattern with unified interfaces
- **Implementation**: tool_bridge → tool_adapters → MCP client
- **Benefits**: Consistent tool access, extensible tool types, type safety

### 4. Multi-Agent Orchestration

- **Pattern**: Three-phase workflow with specialized agents
- **Implementation**: Planning → Orchestration → Execution via agent/workflow.py
- **Benefits**: Modular reasoning, specialized capabilities, clear workflow progression

### 5. Session-Based State Management

- **Pattern**: Session isolation with UUID-based tracking
- **Implementation**: Session management across all layers
- **Benefits**: Concurrent client support, isolated contexts, progress tracking

## Performance and Observability

### Logfire Integration

- **Automatic Tracing**: All agent operations and tool executions
- **Performance Monitoring**: Token usage, execution times, success rates
- **Real-time Dashboards**: System health and workflow visibility
- **Error Tracking**: Structured error reporting with context

### Metrics Collection

- **Query Metrics**: Processing time, complexity analysis, success rates
- **Tool Metrics**: Execution patterns, performance per server, error rates
- **Agent Metrics**: Individual agent performance and coordination efficiency
- **System Metrics**: Connection health, memory usage, concurrent sessions

### Streaming Progress Updates

- **Real-time Status**: Current workflow phase and progress percentage
- **Tool Execution**: Live tool execution status and results
- **Error Reporting**: Immediate error notification with recovery guidance
- **Session Tracking**: Individual client progress and context

## Security and Validation

### Path Security

- **Filesystem Server**: Restricted to allowed directories with validation
- **Home Directory**: Safe expansion of `~/` paths
- **Path Traversal**: Prevention of directory traversal attacks

### Command Security

- **DevTools Server**: Whitelisted command execution only
- **Parameter Validation**: Comprehensive validation with error guidance
- **Input Sanitization**: Structured error responses without data leakage

### Session Security

- **UUID-based**: Secure session identification
- **Isolation**: Complete session context isolation
- **Cleanup**: Automatic resource cleanup on disconnect

## Configuration and Deployment

### Environment Configuration

```bash
# LLM Provider Selection
ENGINE_TYPE=anthropic  # or openai

# API Keys
ANTHROPIC_API_KEY=your_key
EXA_API_KEY=your_key

# Server Configuration
HOST=localhost
PORT=3789
DEBUG=true  # Detailed logging and tracing
```

### Data Storage

- **Configuration**: `~/.brain/` directory for user settings
- **MCP Settings**: `~/.brain/mcp.settings.json` for server configurations
- **Logs**: `~/.brain/brain.log` with configurable debug levels
- **Session Data**: In-memory with automatic cleanup

This architecture enables Brain to provide sophisticated multi-agent assistance while maintaining clean separation of concerns, real-time communication capabilities, and robust error handling throughout the entire system stack.

