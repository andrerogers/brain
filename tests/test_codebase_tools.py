#!/usr/bin/env python3
"""
Test all codebase server tools
"""

import os
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_codebase_server_connection(connected_codebase_client):
    """Test codebase server connects successfully"""
    client = connected_codebase_client
    
    # Verify server is connected
    servers = await client.get_all_servers()
    assert "codebase" in servers
    assert servers["codebase"]["status"] == "connected"


@pytest.mark.asyncio
async def test_list_codebase_tools(connected_codebase_client):
    """Test listing codebase tools"""
    client = connected_codebase_client
    
    tools = await client.list_tools("codebase")
    tool_names = [tool.name for tool in tools]
    
    expected_tools = [
        "analyze_project", "get_project_structure", "find_definition",
        "find_references", "explain_codebase", "get_project_context"
    ]
    
    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Tool {expected_tool} not found"


@pytest.mark.asyncio
async def test_analyze_project_tool(connected_codebase_client, sample_project_structure):
    """Test analyze_project tool"""
    client = connected_codebase_client
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "analyze_project", {
            "path": sample_project_structure
        }, session)
        
        result_str = str(result)
        assert "Project Analysis" in result_str or "analysis" in result_str.lower()
        assert "python" in result_str.lower()  # Should detect Python files
        assert "requirements.txt" in result_str  # Should mention dependencies


@pytest.mark.asyncio
async def test_get_project_structure_tool(connected_codebase_client, sample_project_structure):
    """Test get_project_structure tool"""
    client = connected_codebase_client
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "get_project_structure", {
            "path": sample_project_structure,
            "max_depth": 3
        }, session)
        
        result_str = str(result)
        assert "src/" in result_str
        assert "tests/" in result_str  
        assert "docs/" in result_str
        assert "README.md" in result_str
        assert "requirements.txt" in result_str


@pytest.mark.asyncio
async def test_explain_codebase_tool(connected_codebase_client, sample_project_structure):
    """Test explain_codebase tool"""
    client = connected_codebase_client
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "explain_codebase", {
            "path": sample_project_structure
        }, session)
        
        result_str = str(result)
        assert "explanation" in result_str.lower() or "architecture" in result_str.lower()
        assert len(result_str) > 100  # Should provide substantial explanation


@pytest.mark.asyncio
async def test_get_project_context_tool(connected_codebase_client, sample_project_structure):
    """Test get_project_context tool"""
    client = connected_codebase_client
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "get_project_context", {
            "path": sample_project_structure
        }, session)
        
        result_str = str(result)
        assert "context" in result_str.lower() or "project" in result_str.lower()
        assert "Test Project" in result_str  # From README


@pytest.mark.asyncio
async def test_find_definition_tool(connected_codebase_client, sample_python_file):
    """Test find_definition tool"""
    client = connected_codebase_client
    
    # Get the directory containing the Python file
    project_path = os.path.dirname(sample_python_file)
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "find_definition", {
            "symbol": "hello_world",
            "path": project_path
        }, session)
        
        result_str = str(result)
        assert "hello_world" in result_str
        assert "sample.py" in result_str or "def hello_world" in result_str


@pytest.mark.asyncio
async def test_find_definition_class(connected_codebase_client, sample_python_file):
    """Test find_definition tool for class"""
    client = connected_codebase_client
    
    project_path = os.path.dirname(sample_python_file)
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "find_definition", {
            "symbol": "TestClass",
            "path": project_path
        }, session)
        
        result_str = str(result)
        assert "TestClass" in result_str
        assert "class TestClass" in result_str or "sample.py" in result_str


@pytest.mark.asyncio
async def test_find_references_tool(connected_codebase_client, sample_python_file):
    """Test find_references tool"""
    client = connected_codebase_client
    
    project_path = os.path.dirname(sample_python_file)
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "find_references", {
            "symbol": "hello_world",
            "path": project_path
        }, session)
        
        result_str = str(result)
        # Should find references in the same file (function call in __main__)
        assert "hello_world" in result_str


@pytest.mark.asyncio
async def test_find_definition_in_specific_file(connected_codebase_client, sample_python_file):
    """Test find_definition tool with specific file"""
    client = connected_codebase_client
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "find_definition", {
            "symbol": "greet",
            "file_path": sample_python_file,
            "path": os.path.dirname(sample_python_file)
        }, session)
        
        result_str = str(result)
        assert "greet" in result_str
        assert "def greet" in result_str or "method" in result_str.lower()


@pytest.mark.asyncio
async def test_analyze_project_with_multiple_languages(connected_codebase_client, temp_dir):
    """Test analyze_project with multiple file types"""
    client = connected_codebase_client
    
    # Create files of different types
    files = {
        "app.js": "console.log('Hello from JavaScript');",
        "style.css": "body { margin: 0; }",
        "index.html": "<html><body><h1>Hello</h1></body></html>",
        "script.py": "print('Hello from Python')",
        "config.json": '{"name": "test-project", "version": "1.0.0"}'
    }
    
    for filename, content in files.items():
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        result = await client.call_tool("codebase", "analyze_project", {
            "path": temp_dir
        }, session)
        
        result_str = str(result).lower()
        assert "javascript" in result_str or "js" in result_str
        assert "python" in result_str or "py" in result_str
        assert "html" in result_str
        assert "css" in result_str


@pytest.mark.asyncio
async def test_get_project_structure_with_depth_limit(connected_codebase_client, sample_project_structure):
    """Test get_project_structure with depth limit"""
    client = connected_codebase_client
    
    async with client._multi_server_client.session("codebase") as session:
        await session.initialize()
        
        # Test with depth 1 (should only show top level)
        result = await client.call_tool("codebase", "get_project_structure", {
            "path": sample_project_structure,
            "max_depth": 1
        }, session)
        
        result_str = str(result)
        assert "src/" in result_str
        assert "tests/" in result_str
        # Should not show files inside directories with depth 1
        assert "main.py" not in result_str or result_str.count("main.py") <= 1