# Brain

## Overview

The "Brain" project is a multi-agent system designed to facilitate complex interactions between a central Large Language Model (LLM) and various specialized agents, implemented with Multi-Agent Communication Protocol (MCP).

## WebSocket Server

The WebSocket server provides a real-time communication interface for clients to interact with the Brain system. Clients can connect to the server and send JSON-formatted commands to manage MCP server connections, list tools, and send queries for LLM processing.

## Development
#### Create a new virtual environment
````bash
uv venv
````

#### Activate the virtual environment
````bash
source .venv/bin/activate
````

#### Install main dependencies
````bash
uv pip install -r requirements.txt
````

#### For development, install dev dependencies
````bash
uv pip install -r requirements-dev.txt

````

#### Environment Configuration
Create a .env file in the project root:

````bash
# Server settings
HOST=0.0.0.0
PORT=8000
DEBUG=true

# LLM settings
LLM_TYPE=anthropic  # Options: 'anthropic' or 'openai'

# Anthropic settings
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_EMBEDDING_MODEL=claude-3-7-embeddings-v1
ANTHROPIC_LLM_MODEL=claude-3-7-sonnet-20250219

# OpenAI settings
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_LLM_MODEL=gpt-4
````

#### Running the Server

````bash
python src/server.py
````

The server will be available at http://localhost:8000 (or the host/port configured in your settings).

#### Add a production dependency
````bash
uv add package_name
uv pip freeze > requirements.txt
````

#### Add a development dependency
````bash
uv pip install --dev package_name
uv pip freeze --dev > requirements-dev.txt
````


#### Update all dependencies
````bash
uv pip install -U -r requirements.txt
uv pip freeze > requirements.txt
````

#### Update a specific package
````bash
uv pip install -U package_name
uv pip freeze > requirements.txt
````

#### Update development dependencies
````bash
uv pip install -U -r requirements-dev.txt
uv pip freeze --dev > requirements-dev.txt
````

### How to Connect

The WebSocket server typically runs on `ws://localhost:3789`. You can connect to it using a WebSocket client (e.g., `wscat`, a custom script, or a browser's WebSocket API).

Example using `wscat`:

```bash
wscat -c ws://localhost:3789
```

Upon successful connection, the server may send an initial `status` message with information about currently connected MCP servers.

### Supported Commands

All commands are sent as JSON objects over the WebSocket connection. Each command must have a `

command` field.

#### 1. `connect_server`

Connects the MCP client to a new or existing MCP server.

- **Purpose:** To register and establish a connection with an MCP server, making its tools available to the system.

- **Parameters:**
  - `server_id` (string, required): A unique identifier for the server (e.g., "math_local", "exa_remote").
    - `server_config` (string or object, required): The configuration for the server.
      - If a string starting with `http://` or `https://`, it's treated as a remote HTTP server URL.
      - If a string representing a file path (e.g., `./my_server.py`), it's treated as a local stdio server script.
      - If an object, it should contain `command`, `args` (optional), and `transport` (e.g., `{"command": "python", "args": ["path/to/script.py"], "transport": "stdio"}`).

#### 2. `list_tools`

Lists the tools available from a specific connected MCP server.

- **Purpose:** To discover the functionalities exposed by a connected agent.

- **Parameters:**
  - `server_id` (string, required): The unique identifier of the server whose tools you want to list.

- **Response (`type: tools_list`):

- **Error Response (`type: error`):

- **Example Request:**

#### 3. `query`

Sends a natural language query to the LLM for processing, potentially involving tool use.

- **Purpose:** To interact with the central LLM, which may then decide to use available MCP tools to fulfill the request.

- **Parameters:**
  - `query` (string, required): The natural language query for the LLM.

- **Response (`type: query_response`):

- **Intermediate Response (`type: thinking`):

- **Error Response (`type: error`):

- **Example Request:**

#### 4. `get_servers`

Retrieves information about all currently connected MCP servers.

- **Purpose:** To get an overview of all active MCP agents in the system.

- **Parameters:** None.

- **Response (`type: servers_list`):

- **Error Response (`type: error`):

- **Example Request:**

## Setup & Installation (High-Level)

To get started with the project, you will typically need to:

1. **Clone the repository:**

1. **Set up a Python virtual environment:**

1. **Install dependencies:**

1. **Configure environment variables:** Create a `.env` file in the root directory based on a template (if provided) and fill in your specific configurations (e.g., API keys, local paths).

1. **Run the application:**
  - To start the WebSocket server, you would typically run `python -m brain.src.main` or a similar entry point.

