# Brain Project: Multi-Agent System

## Overview

The "Brain" project is a sophisticated multi-agent system designed to facilitate complex interactions between a central Large Language Model (LLM) and various specialized agents, implemented as Multi-Agent Communication Protocol (MCP) servers. This repository details the core components and their interactions.

## Architecture

The project's architecture centers around a WebSocket server that acts as the primary communication hub. It orchestrates interactions between connected clients and various MCP servers via a `LangChainMCPClient`. The system is designed to allow an LLM to leverage tools exposed by these MCP servers.

- **WebSocket Server:** The central communication point, handling client connections and routing commands to the `LangChainMCPClient`.

- **LangChain MCP Client (****`mcp_brain.mcp_client.LangChainMCPClient`****):** Manages connections to various MCP servers, discovers their exposed tools, and orchestrates tool calls based on requests received from the WebSocket server.

- **MCP Servers:** Specialized agents (e.g., `LangChainExaMCPServer`) that expose functionalities as tools consumable by the `LangChainMCPClient`.

## WebSocket Server

The WebSocket server provides a real-time communication interface for clients to interact with the Brain system. Clients can connect to the server and send JSON-formatted commands to manage MCP server connections, list tools, and send queries for LLM processing.

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

#### 2. `disconnect_server`

Disconnects from a previously connected MCP server.

- **Purpose:** To remove an MCP server from the system and close its connection.

- **Parameters:**
  - `server_id` (string, required): The unique identifier of the server to disconnect.

- **Response (`type: server_disconnected`):

- **Error Response (`type: error`):

- **Example Request:**

#### 3. `list_tools`

Lists the tools available from a specific connected MCP server.

- **Purpose:** To discover the functionalities exposed by a connected agent.

- **Parameters:**
  - `server_id` (string, required): The unique identifier of the server whose tools you want to list.

- **Response (`type: tools_list`):

- **Error Response (`type: error`):

- **Example Request:**

#### 4. `query`

Sends a natural language query to the LLM for processing, potentially involving tool use.

- **Purpose:** To interact with the central LLM, which may then decide to use available MCP tools to fulfill the request.

- **Parameters:**
  - `query` (string, required): The natural language query for the LLM.

- **Response (`type: query_response`):

- **Intermediate Response (`type: thinking`):

- **Error Response (`type: error`):

- **Example Request:**

#### 5. `get_servers`

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

