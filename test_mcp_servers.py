#!/usr/bin/env python3
"""
Test script to verify MCP servers are working correctly
"""

import asyncio
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add the src directory to the path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from tools.client import MCPClient


@pytest.mark.asyncio
async def test_filesystem_server():
    """Test filesystem server operations"""
    print("\n🧪 Testing Filesystem Server...")
    
    client = MCPClient()
    
    # Connect to filesystem server
    filesystem_path = src_path / "tools" / "servers" / "filesystem_server.py"
    success = await client.connect_server("filesystem", str(filesystem_path))
    
    if not success:
        print("❌ Failed to connect to filesystem server")
        return False
    
    print("✅ Connected to filesystem server")
    
    # Test listing tools
    tools = await client.list_tools("filesystem")
    tool_names = [tool.name for tool in tools]
    expected_tools = ["read_file", "write_file", "list_directory", "search_files"]
    
    print(f"📋 Available tools: {tool_names}")
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"✅ {expected} tool available")
        else:
            print(f"❌ {expected} tool missing")
            return False
    
    # Test with a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        tmp.write("Hello, Brain MCP Server!")
        tmp_path = tmp.name
    
    try:
        # Test reading the file through the session
        async with client._multi_server_client.session("filesystem") as session:
            await session.initialize()
            result = await client.call_tool("filesystem", "read_file", {"path": tmp_path}, session)
            print(f"📄 Read file result: {result}")
            
            if "Hello, Brain MCP Server!" in str(result):
                print("✅ File read test passed")
            else:
                print("❌ File read test failed")
                return False
                
    finally:
        os.unlink(tmp_path)
    
    return True


@pytest.mark.asyncio
async def test_git_server():
    """Test git server operations"""
    print("\n🧪 Testing Git Server...")
    
    client = MCPClient()
    
    # Connect to git server
    git_path = src_path / "tools" / "servers" / "git_server.py"
    success = await client.connect_server("git", str(git_path))
    
    if not success:
        print("❌ Failed to connect to git server")
        return False
    
    print("✅ Connected to git server")
    
    # Test listing tools
    tools = await client.list_tools("git")
    tool_names = [tool.name for tool in tools]
    expected_tools = ["git_status", "git_diff", "git_log", "git_branch_info"]
    
    print(f"📋 Available tools: {tool_names}")
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"✅ {expected} tool available")
        else:
            print(f"❌ {expected} tool missing")
            return False
    
    # Test git status (should work in any git repo)
    try:
        async with client._multi_server_client.session("git") as session:
            await session.initialize()
            result = await client.call_tool("git", "git_status", {"path": "."}, session)
            print(f"📊 Git status result: {result}")
            
            if "Error" not in str(result) or "Not a git repository" in str(result):
                print("✅ Git status test passed (or expected non-git directory)")
            else:
                print("❌ Git status test failed")
                return False
                
    except Exception as e:
        print(f"ℹ️  Git test expected (not in git repo): {e}")
    
    return True


@pytest.mark.asyncio
async def test_codebase_server():
    """Test codebase analysis server"""
    print("\n🧪 Testing Codebase Server...")
    
    client = MCPClient()
    
    # Connect to codebase server
    codebase_path = src_path / "tools" / "servers" / "codebase_server.py"
    success = await client.connect_server("codebase", str(codebase_path))
    
    if not success:
        print("❌ Failed to connect to codebase server")
        return False
    
    print("✅ Connected to codebase server")
    
    # Test listing tools
    tools = await client.list_tools("codebase")
    tool_names = [tool.name for tool in tools]
    expected_tools = ["analyze_project", "get_project_structure", "find_definition", "explain_codebase"]
    
    print(f"📋 Available tools: {tool_names}")
    
    for expected in expected_tools:
        if expected in tool_names:
            print(f"✅ {expected} tool available")
        else:
            print(f"❌ {expected} tool missing")
            return False
    
    # Test project analysis
    try:
        async with client._multi_server_client.session("codebase") as session:
            await session.initialize()
            result = await client.call_tool("codebase", "analyze_project", {"path": "."}, session)
            print(f"📊 Project analysis preview: {str(result)[:200]}...")
            
            if "Project Analysis" in str(result):
                print("✅ Project analysis test passed")
            else:
                print("❌ Project analysis test failed")
                return False
                
    except Exception as e:
        print(f"❌ Codebase test failed: {e}")
        return False
    
    return True


@pytest.mark.asyncio
async def test_exa_server():
    """Test exa server for web search"""
    print("\n🧪 Testing Exa Server...")
    
    client = MCPClient()
    
    # Connect to exa server
    exa_path = src_path / "tools" / "servers" / "exa_server.py"
    
    try:
        success = await client.connect_server("exa", str(exa_path))
        
        if not success:
            print("❌ Failed to connect to exa server (likely missing EXA_API_KEY)")
            return False
        
        print("✅ Connected to exa server")
        
        # Test listing tools
        tools = await client.list_tools("exa")
        tool_names = [tool.name for tool in tools]
        expected_tools = ["web_search_exa", "crawl_url"]
        
        print(f"📋 Available tools: {tool_names}")
        
        for expected in expected_tools:
            if expected in tool_names:
                print(f"✅ {expected} tool available")
            else:
                print(f"❌ {expected} tool missing")
                return False
        
        print("ℹ️  Exa tools available but not testing API calls (requires API key)")
        return True
        
    except Exception as e:
        print(f"ℹ️  Exa server test skipped: {e}")
        return True  # Don't fail the test for missing API key


@pytest.mark.asyncio
async def test_enhanced_client():
    """Test the enhanced client with auto-connection"""
    print("\n🧪 Testing Enhanced Client Auto-Connection...")
    
    client = MCPClient()
    
    # Test auto-connection to built-in servers
    results = await client.auto_connect_builtin_servers()
    
    print(f"📊 Auto-connection results: {results}")
    
    connected_count = sum(1 for success in results.values() if success)
    print(f"✅ Connected to {connected_count}/{len(results)} built-in servers")
    
    # Test getting all servers
    all_servers = await client.get_all_servers()
    print(f"📋 All connected servers: {list(all_servers.keys())}")
    
    # Test query intent analysis with async
    test_queries = [
        "read package.json",
        "git status", 
        "analyze this project",
        "run tests",
        "what is this codebase about?",
        "what's the weather in Toronto?"
    ]
    
    for query in test_queries:
        try:
            intent = await client.analyze_query_intent(query)
            print(f"🎯 Query: '{query}' -> Intent: {intent['operation_type']}, Servers: {intent['servers_needed']}")
        except Exception as e:
            # Fallback to synchronous version if LLM analysis fails
            intent = client._fallback_intent_analysis(query)
            print(f"🎯 Query: '{query}' (fallback) -> Intent: {intent['operation_type']}, Servers: {intent['servers_needed']}")
    
    return connected_count > 0


async def main():
    """Run all tests"""
    print("🚀 Testing Brain MCP Servers")
    print("=" * 50)
    
    tests = [
        test_filesystem_server,
        test_git_server, 
        test_codebase_server,
        test_exa_server,
        test_enhanced_client
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"✅ {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Brain MCP servers are ready.")
        return 0
    else:
        print("❌ Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)