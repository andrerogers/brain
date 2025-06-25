# Brain + Brain-Surf-CLI Integration Setup

This document describes how to set up the complete Claude Code replica system with both the Brain server and Brain-Surf-CLI working together.

## Prerequisites

### System Requirements
- Python 3.10+ (for Brain server)
- Node.js 18+ (for CLI)
- Git (for git operations)

### Python Dependencies (Brain Server)
The Brain server requires additional MCP dependencies:

```bash
cd /mnt/dev_drive/projects/brain
source .venv/bin/activate

# Install additional MCP dependencies
pip install mcp fastmcp langchain-mcp-adapters

# Or add to requirements.txt:
echo "mcp>=1.0.0" >> requirements.txt
echo "fastmcp>=0.1.0" >> requirements.txt  
echo "langchain-mcp-adapters>=0.1.0" >> requirements.txt

pip install -r requirements.txt
```

### Node.js Dependencies (CLI)
```bash
cd /mnt/dev_drive/projects/brain-surf-cli
npm install
npm link  # To use 'brain' command globally
```

## Setup Steps

### 1. Configure Brain Server

Update your Brain server's `.env` file:
```bash
# Brain Server Configuration
DEBUG=true
ENGINE_TYPE=anthropic
ANTHROPIC_API_KEY=your_key_here

# WebSocket settings
WS_HOST=localhost
WS_PORT=3789

# Enable development features
ENABLE_DEV_SERVERS=true
```

### 2. Start Brain Server

```bash
cd /mnt/dev_drive/projects/brain
source .venv/bin/activate
python src/main.py
```

The server will:
- Auto-connect to built-in MCP servers (filesystem, git, codebase, devtools)
- Start WebSocket server on ws://localhost:3789
- Log which servers and tools are available

### 3. Test CLI Connection

```bash
# Test basic connection
brain status

# Test file operations
brain "list ."

# Test git operations  
brain "git status"

# Test project analysis
brain "analyze this project"

# Start interactive session
brain
```

## New MCP Servers

The integration includes 4 new built-in MCP servers:

### 1. Filesystem Server (`filesystem_server.py`)
**Tools:**
- `read_file(path, start_line, end_line)` - Read file contents
- `write_file(path, content, create_dirs)` - Write/create files
- `edit_file(path, old_content, new_content)` - Edit files precisely
- `list_directory(path, show_hidden, recursive)` - List directory contents
- `search_files(pattern, directory, file_pattern, max_results)` - Search in files
- `create_directory(path, parents)` - Create directories
- `get_file_info(path)` - File metadata and stats
- `delete_file(path)` - Delete files (with safety checks)

**Security:** Path validation prevents access outside allowed directories

### 2. Git Server (`git_server.py`)
**Tools:**
- `git_status(path)` - Working directory status
- `git_diff(file_path, staged, path)` - Show differences
- `git_log(limit, file_path, path)` - Commit history
- `git_add(file_paths, path)` - Stage files
- `git_commit(message, path)` - Create commits
- `git_branch_info(path)` - Branch and remote info
- `git_search_history(query, limit, path)` - Search commits
- `git_show_commit(commit_hash, path)` - Show commit details
- `git_reset_file(file_path, path)` - Reset files
- `git_stash(message, path)` - Stash changes
- `git_stash_list(path)` - List stashes

### 3. Codebase Server (`codebase_server.py`)
**Tools:**
- `analyze_project(path)` - Project structure and technology analysis
- `get_project_structure(path, max_depth)` - Hierarchical directory tree
- `find_definition(symbol, file_path, path)` - Find symbol definitions
- `find_references(symbol, file_path, path)` - Find symbol references
- `explain_codebase(path)` - Architectural analysis
- `get_project_context(path)` - Essential context for AI

**Features:** 
- Multi-language support (JavaScript, TypeScript, Python, Rust, Go, Java)
- Technology detection (frameworks, build tools, package managers)
- Pattern-based symbol finding

### 4. Development Tools Server (`devtools_server.py`)
**Tools:**
- `run_tests(pattern, file_path, path)` - Execute test suites
- `run_command_safe(command, path, timeout)` - Safe command execution
- `lint_code(file_path, path)` - Code linting
- `format_code(file_path, path)` - Code formatting
- `check_types(file_path, path)` - Type checking
- `install_dependencies(path)` - Install project dependencies

**Security:** Whitelist-based command execution for safety

## Enhanced Query Processing

The `MCPClient` provides:

### Intent Analysis
Automatically detects query intent and routes to appropriate servers:
- File operations → filesystem server
- Git commands → git server  
- Code analysis → codebase server
- Development tasks → devtools server

### Query Enhancement
Adds development context to queries:
```
User: "fix the bug in auth.ts"
Enhanced: "Development Assistant Query: fix the bug in auth.ts

Available development tools:
- File Operations: read_file, write_file, edit_file...
- Git Operations: git_status, git_diff...
- Codebase Analysis: find_definition, find_references...

Instructions: Use appropriate tools to help with this development task."
```

### Multi-Server Orchestration
- Routes tool calls to correct servers automatically
- Maintains session state across multiple tools
- Provides comprehensive development assistance

## Usage Examples

### File Operations
```bash
brain "read package.json"
brain "edit src/app.js" 
brain "search for TODO in src"
brain "create directory new-feature"
```

### Git Operations
```bash
brain "git status"
brain "show diff for src/app.js"
brain "commit 'fix user authentication bug'"
brain "show last 5 commits"
```

### Code Analysis
```bash
brain "analyze this project"
brain "find definition UserService"
brain "explain the architecture"
brain "show project structure"
```

### Development Tasks
```bash
brain "run tests"
brain "lint the code"
brain "check types"
brain "format all files"
```

### Complex Development Assistance
```bash
brain "fix the authentication bug in src/auth.ts"
brain "implement OAuth2 login"
brain "refactor the user service to use async/await"
brain "optimize the database queries in models/"
```

## Troubleshooting

### Server Connection Issues
1. Check Brain server is running: `curl ws://localhost:3789`
2. Check logs in `~/.brain/brain.log`
3. Verify MCP dependencies: `pip list | grep mcp`

### MCP Server Issues
1. Check individual server: `python src/mcp_brain/servers/filesystem_server.py --debug`
2. Verify server paths in auto-connection
3. Check permissions for file operations

### CLI Issues
1. Verify global link: `which brain`
2. Check session storage: `ls ~/.brain-cli/sessions/`
3. Test with debug: `brain --help`

## Development Notes

The integration transforms the Brain system into a complete Claude Code replica by:

1. **Adding Essential Development Tools** - File operations, git, code analysis
2. **Intelligent Command Routing** - Natural language to appropriate tools
3. **Context-Aware Responses** - Development-focused assistance
4. **Session Management** - Maintaining conversation context
5. **Multi-Server Architecture** - Extensible tool ecosystem

This creates a powerful development assistant that can understand projects, navigate codebases, perform git operations, run tests, and provide comprehensive coding assistance through natural language conversation.