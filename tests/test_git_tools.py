#!/usr/bin/env python3
"""
Test all git server tools
"""

import os
import pytest
import subprocess
import tempfile
from pathlib import Path


@pytest.fixture
def git_repo(temp_dir):
    """Create a temporary git repository for testing"""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)
    
    # Create initial files
    test_file = os.path.join(temp_dir, "test.txt")
    with open(test_file, 'w') as f:
        f.write("Initial content\n")
    
    readme_file = os.path.join(temp_dir, "README.md")
    with open(readme_file, 'w') as f:
        f.write("# Test Repository\nThis is a test repository for Brain MCP testing.\n")
    
    # Initial commit
    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)
    
    # Create a second commit
    with open(test_file, 'a') as f:
        f.write("Second line\n")
    
    subprocess.run(["git", "add", "test.txt"], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Add second line"], cwd=temp_dir, check=True)
    
    # Make some changes for testing
    with open(test_file, 'a') as f:
        f.write("Uncommitted changes\n")
    
    return temp_dir


@pytest.mark.asyncio
async def test_git_server_connection(connected_git_client):
    """Test git server connects successfully"""
    client = connected_git_client
    
    # Verify server is connected
    servers = await client.get_all_servers()
    assert "git" in servers
    assert servers["git"]["status"] == "connected"


@pytest.mark.asyncio
async def test_list_git_tools(connected_git_client):
    """Test listing git tools"""
    client = connected_git_client
    
    tools = await client.list_tools("git")
    tool_names = [tool.name for tool in tools]
    
    expected_tools = [
        "git_status", "git_diff", "git_log", "git_add", "git_commit",
        "git_branch_info", "git_search_history", "git_show_commit",
        "git_reset_file", "git_stash", "git_stash_list"
    ]
    
    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Tool {expected_tool} not found"


@pytest.mark.asyncio
async def test_git_status_tool(connected_git_client, git_repo):
    """Test git_status tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_status", {
            "path": git_repo
        }, session)
        
        result_str = str(result)
        assert "test.txt" in result_str  # Should show modified file
        assert "modified" in result_str.lower() or "changed" in result_str.lower()


@pytest.mark.asyncio
async def test_git_diff_tool(connected_git_client, git_repo):
    """Test git_diff tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_diff", {
            "path": git_repo
        }, session)
        
        result_str = str(result)
        assert "Uncommitted changes" in result_str
        assert "+" in result_str  # Should show added lines


@pytest.mark.asyncio
async def test_git_log_tool(connected_git_client, git_repo):
    """Test git_log tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_log", {
            "path": git_repo,
            "limit": 2
        }, session)
        
        result_str = str(result)
        assert "Initial commit" in result_str
        assert "Add second line" in result_str


@pytest.mark.asyncio
async def test_git_branch_info_tool(connected_git_client, git_repo):
    """Test git_branch_info tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_branch_info", {
            "path": git_repo
        }, session)
        
        result_str = str(result)
        assert "main" in result_str or "master" in result_str  # Default branch name


@pytest.mark.asyncio
async def test_git_add_tool(connected_git_client, git_repo):
    """Test git_add tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_add", {
            "file_paths": "test.txt",
            "path": git_repo
        }, session)
        
        # Check that file was staged
        status_result = await client.call_tool("git", "git_status", {
            "path": git_repo
        }, session)
        
        status_str = str(status_result)
        assert "staged" in status_str.lower() or "index" in status_str.lower()


@pytest.mark.asyncio
async def test_git_commit_tool(connected_git_client, git_repo):
    """Test git_commit tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        # First stage the changes
        await client.call_tool("git", "git_add", {
            "file_paths": "test.txt",
            "path": git_repo
        }, session)
        
        # Then commit
        result = await client.call_tool("git", "git_commit", {
            "message": "Test commit from Brain MCP",
            "path": git_repo
        }, session)
        
        result_str = str(result)
        assert "success" in result_str.lower() or "commit" in result_str.lower()
        
        # Verify commit was created
        log_result = await client.call_tool("git", "git_log", {
            "path": git_repo,
            "limit": 1
        }, session)
        
        assert "Test commit from Brain MCP" in str(log_result)


@pytest.mark.asyncio
async def test_git_search_history_tool(connected_git_client, git_repo):
    """Test git_search_history tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_search_history", {
            "query": "Initial",
            "path": git_repo,
            "limit": 5
        }, session)
        
        result_str = str(result)
        assert "Initial commit" in result_str


@pytest.mark.asyncio
async def test_git_show_commit_tool(connected_git_client, git_repo):
    """Test git_show_commit tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        # Get the latest commit hash
        log_result = await client.call_tool("git", "git_log", {
            "path": git_repo,
            "limit": 1
        }, session)
        
        log_str = str(log_result)
        # Extract commit hash (this is a simple extraction, might need adjustment)
        import re
        hash_match = re.search(r'commit\s+([a-f0-9]{7,40})', log_str)
        
        if hash_match:
            commit_hash = hash_match.group(1)
            
            result = await client.call_tool("git", "git_show_commit", {
                "commit_hash": commit_hash,
                "path": git_repo
            }, session)
            
            result_str = str(result)
            assert commit_hash in result_str


@pytest.mark.asyncio
async def test_git_reset_file_tool(connected_git_client, git_repo):
    """Test git_reset_file tool"""
    client = connected_git_client
    
    # Make changes to a file
    test_file = os.path.join(git_repo, "test.txt")
    with open(test_file, 'a') as f:
        f.write("Changes to be reset\n")
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_reset_file", {
            "file_path": "test.txt",
            "path": git_repo
        }, session)
        
        # Check that file was reset
        with open(test_file, 'r') as f:
            content = f.read()
            assert "Changes to be reset" not in content


@pytest.mark.asyncio
async def test_git_stash_tool(connected_git_client, git_repo):
    """Test git_stash tool"""
    client = connected_git_client
    
    # Make some changes first
    test_file = os.path.join(git_repo, "test.txt")
    with open(test_file, 'a') as f:
        f.write("Changes to stash\n")
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_stash", {
            "message": "Test stash from Brain MCP",
            "path": git_repo
        }, session)
        
        result_str = str(result)
        assert "stash" in result_str.lower()
        
        # Check that working directory is clean
        status_result = await client.call_tool("git", "git_status", {
            "path": git_repo
        }, session)
        
        # Working directory should be cleaner now
        with open(test_file, 'r') as f:
            content = f.read()
            assert "Changes to stash" not in content


@pytest.mark.asyncio
async def test_git_stash_list_tool(connected_git_client, git_repo):
    """Test git_stash_list tool"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_stash_list", {
            "path": git_repo
        }, session)
        
        # May or may not have stashes, but should not error
        assert "error" not in str(result).lower() or "no stash" in str(result).lower()


@pytest.mark.asyncio
async def test_git_diff_specific_file(connected_git_client, git_repo):
    """Test git_diff tool with specific file"""
    client = connected_git_client
    
    async with client._multi_server_client.session("git") as session:
        await session.initialize()
        
        result = await client.call_tool("git", "git_diff", {
            "file_path": "test.txt",
            "path": git_repo
        }, session)
        
        result_str = str(result)
        # Should only show diff for test.txt file
        assert "test.txt" in result_str or "@@" in result_str  # Git diff markers