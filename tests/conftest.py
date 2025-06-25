#!/usr/bin/env python3
"""
Pytest configuration and fixtures for Brain MCP testing
"""

import os
import sys
import asyncio
import tempfile
import pytest
import pytest_asyncio
from pathlib import Path

# Add the src directory to the path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from mcp_brain.mcp_client import MCPClient


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mcp_client():
    """Create a fresh MCPClient instance for testing"""
    client = MCPClient()
    yield client
    # Cleanup - disconnect all servers
    if hasattr(client, '_multi_server_client') and client._multi_server_client:
        try:
            # Close any open sessions
            for server_id in list(client.servers_config.keys()):
                try:
                    # Remove server configuration
                    del client.servers_config[server_id]
                except KeyError:
                    pass
        except Exception:
            pass


@pytest.fixture
def temp_file():
    """Create a temporary file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        tmp.write("Test content for Brain MCP testing\nLine 2\nLine 3")
        tmp_path = tmp.name
    
    yield tmp_path
    
    # Cleanup
    try:
        os.unlink(tmp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file for testing"""
    python_content = '''#!/usr/bin/env python3
"""Sample Python file for testing"""

def hello_world():
    """Say hello to the world"""
    return "Hello, World!"

class TestClass:
    """A test class for demonstration"""
    
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}!"

if __name__ == "__main__":
    print(hello_world())
'''
    
    file_path = os.path.join(temp_dir, "sample.py")
    with open(file_path, 'w') as f:
        f.write(python_content)
    
    return file_path


@pytest.fixture
def sample_project_structure(temp_dir):
    """Create a sample project structure for testing"""
    # Create directory structure
    os.makedirs(os.path.join(temp_dir, "src"))
    os.makedirs(os.path.join(temp_dir, "tests"))
    os.makedirs(os.path.join(temp_dir, "docs"))
    
    # Create files
    files = {
        "README.md": "# Test Project\nThis is a test project for Brain MCP testing.",
        "requirements.txt": "pytest==7.4.0\nrequests==2.31.0",
        "src/main.py": "print('Hello from main')",
        "src/utils.py": "def helper(): return 'helper'",
        "tests/test_main.py": "def test_main(): assert True",
        "docs/api.md": "# API Documentation"
    }
    
    for file_path, content in files.items():
        full_path = os.path.join(temp_dir, file_path)
        with open(full_path, 'w') as f:
            f.write(content)
    
    return temp_dir


@pytest.fixture(scope="session")
def server_paths():
    """Get paths to all MCP servers"""
    src_path = Path(__file__).parent.parent / "src"
    servers_path = src_path / "mcp_brain" / "servers"
    
    return {
        "filesystem": str(servers_path / "filesystem_server.py"),
        "git": str(servers_path / "git_server.py"),
        "codebase": str(servers_path / "codebase_server.py"),
        "devtools": str(servers_path / "devtools_server.py"),
        "exa": str(servers_path / "exa_server.py")
    }


@pytest_asyncio.fixture
async def connected_filesystem_client(mcp_client, server_paths):
    """MCP client with filesystem server connected"""
    success = await mcp_client.connect_server("filesystem", server_paths["filesystem"])
    assert success, "Failed to connect filesystem server"
    yield mcp_client


@pytest_asyncio.fixture
async def connected_git_client(mcp_client, server_paths):
    """MCP client with git server connected"""
    success = await mcp_client.connect_server("git", server_paths["git"])
    assert success, "Failed to connect git server"
    yield mcp_client


@pytest_asyncio.fixture
async def connected_codebase_client(mcp_client, server_paths):
    """MCP client with codebase server connected"""
    success = await mcp_client.connect_server("codebase", server_paths["codebase"])
    assert success, "Failed to connect codebase server"
    yield mcp_client


@pytest_asyncio.fixture
async def connected_devtools_client(mcp_client, server_paths):
    """MCP client with devtools server connected"""
    success = await mcp_client.connect_server("devtools", server_paths["devtools"])
    assert success, "Failed to connect devtools server"
    yield mcp_client


@pytest_asyncio.fixture
async def connected_exa_client(mcp_client, server_paths):
    """MCP client with exa server connected"""
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    assert success, "Failed to connect exa server"
    yield mcp_client


@pytest_asyncio.fixture
async def all_servers_client(mcp_client):
    """MCP client with all built-in servers connected"""
    results = await mcp_client.auto_connect_builtin_servers()
    connected_count = sum(1 for success in results.values() if success)
    assert connected_count >= 4, f"Expected at least 4 servers connected, got {connected_count}"
    yield mcp_client


# Test data fixtures
@pytest.fixture
def sample_queries():
    """Sample queries for testing intent analysis"""
    return {
        "file_operations": [
            "read package.json",
            "edit src/main.py",
            "list current directory",
            "search for TODO in src",
            "create directory test"
        ],
        "git_operations": [
            "git status",
            "show git diff",
            "commit changes",
            "git log",
            "check git branches"
        ],
        "codebase_analysis": [
            "analyze this project",
            "explain the codebase",
            "find definition of MyClass",
            "show project structure",
            "where is the main function"
        ],
        "development_tasks": [
            "run tests",
            "lint the code",
            "format code",
            "check types",
            "install dependencies"
        ],
        "web_search": [
            "what's the weather in Toronto",
            "current news about AI",
            "search for Python tutorials",
            "latest updates on technology",
            "today's headlines"
        ],
        "general": [
            "what is artificial intelligence",
            "explain machine learning",
            "how does Python work",
            "help me understand this error"
        ]
    }