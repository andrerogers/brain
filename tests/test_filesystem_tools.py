#!/usr/bin/env python3
"""
Test all filesystem server tools
"""

import os
import pytest
import tempfile
from pathlib import Path


@pytest.mark.asyncio
async def test_filesystem_server_connection(connected_filesystem_client):
    """Test filesystem server connects successfully"""
    client = connected_filesystem_client
    
    # Verify server is connected
    servers = await client.get_all_servers()
    assert "filesystem" in servers
    assert servers["filesystem"]["status"] == "connected"


@pytest.mark.asyncio
async def test_list_filesystem_tools(connected_filesystem_client):
    """Test listing filesystem tools"""
    client = connected_filesystem_client
    
    tools = await client.list_tools("filesystem")
    tool_names = [tool.name for tool in tools]
    
    expected_tools = [
        "read_file", "write_file", "edit_file", "list_directory",
        "search_files", "get_file_info", "create_directory", "delete_file"
    ]
    
    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Tool {expected_tool} not found"


@pytest.mark.asyncio
async def test_read_file_tool(connected_filesystem_client, temp_file):
    """Test read_file tool"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        result = await client.call_tool("filesystem", "read_file", {"path": temp_file}, session)
        
        assert "Test content for Brain MCP testing" in str(result)
        assert "Line 2" in str(result)
        assert "Line 3" in str(result)


@pytest.mark.asyncio
async def test_write_file_tool(connected_filesystem_client, temp_dir):
    """Test write_file tool"""
    client = connected_filesystem_client
    
    test_file = os.path.join(temp_dir, "write_test.txt")
    test_content = "This is test content written by Brain MCP"
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        # Write file
        result = await client.call_tool("filesystem", "write_file", {
            "path": test_file,
            "content": test_content
        }, session)
        
        assert "success" in str(result).lower() or "written" in str(result).lower()
        
        # Verify file was written
        assert os.path.exists(test_file)
        with open(test_file, 'r') as f:
            assert f.read() == test_content


@pytest.mark.asyncio
async def test_edit_file_tool(connected_filesystem_client, temp_file):
    """Test edit_file tool"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        # Edit the file
        result = await client.call_tool("filesystem", "edit_file", {
            "path": temp_file,
            "old_content": "Line 2",
            "new_content": "Modified Line 2"
        }, session)
        
        # Check edit was successful
        assert "success" in str(result).lower() or "modified" in str(result).lower()
        
        # Verify file content changed
        with open(temp_file, 'r') as f:
            content = f.read()
            assert "Modified Line 2" in content
            assert "Line 2" not in content


@pytest.mark.asyncio
async def test_list_directory_tool(connected_filesystem_client, sample_project_structure):
    """Test list_directory tool"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        result = await client.call_tool("filesystem", "list_directory", {
            "path": sample_project_structure
        }, session)
        
        result_str = str(result)
        assert "README.md" in result_str
        assert "requirements.txt" in result_str
        assert "src" in result_str
        assert "tests" in result_str
        assert "docs" in result_str


@pytest.mark.asyncio
async def test_search_files_tool(connected_filesystem_client, sample_project_structure):
    """Test search_files tool"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        # Search for "Test" in the project
        result = await client.call_tool("filesystem", "search_files", {
            "pattern": "Test",
            "directory": sample_project_structure
        }, session)
        
        result_str = str(result)
        assert "README.md" in result_str  # Contains "Test Project"
        assert "Test" in result_str


@pytest.mark.asyncio
async def test_get_file_info_tool(connected_filesystem_client, temp_file):
    """Test get_file_info tool"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        result = await client.call_tool("filesystem", "get_file_info", {
            "path": temp_file
        }, session)
        
        result_str = str(result)
        assert "size" in result_str.lower() or "byte" in result_str.lower()
        assert temp_file in result_str


@pytest.mark.asyncio
async def test_create_directory_tool(connected_filesystem_client, temp_dir):
    """Test create_directory tool"""
    client = connected_filesystem_client
    
    new_dir = os.path.join(temp_dir, "new_test_directory")
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        result = await client.call_tool("filesystem", "create_directory", {
            "path": new_dir
        }, session)
        
        # Check directory was created
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)
        assert "success" in str(result).lower() or "created" in str(result).lower()


@pytest.mark.asyncio
async def test_delete_file_tool(connected_filesystem_client, temp_dir):
    """Test delete_file tool"""
    client = connected_filesystem_client
    
    # Create a file to delete
    test_file = os.path.join(temp_dir, "to_delete.txt")
    with open(test_file, 'w') as f:
        f.write("This file will be deleted")
    
    assert os.path.exists(test_file)
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        result = await client.call_tool("filesystem", "delete_file", {
            "path": test_file
        }, session)
        
        # Check file was deleted
        assert not os.path.exists(test_file)
        assert "success" in str(result).lower() or "deleted" in str(result).lower()


@pytest.mark.asyncio
async def test_read_file_with_line_range(connected_filesystem_client, temp_file):
    """Test read_file tool with line range"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        # Read only line 2
        result = await client.call_tool("filesystem", "read_file", {
            "path": temp_file,
            "start_line": 2,
            "end_line": 2
        }, session)
        
        result_str = str(result)
        assert "Line 2" in result_str
        assert "Line 3" not in result_str or result_str.count("Line") == 1


@pytest.mark.asyncio
async def test_search_files_with_pattern(connected_filesystem_client, sample_project_structure):
    """Test search_files tool with file pattern"""
    client = connected_filesystem_client
    
    async with client._multi_server_client.session("filesystem") as session:
        await session.initialize()
        
        # Search for Python files
        result = await client.call_tool("filesystem", "search_files", {
            "pattern": "main",
            "directory": sample_project_structure,
            "file_pattern": "*.py"
        }, session)
        
        result_str = str(result)
        assert "main.py" in result_str
        assert "Hello from main" in result_str