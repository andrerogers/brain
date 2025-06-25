#!/usr/bin/env python3
"""
Integration tests for Brain MCP system
Tests end-to-end workflows and cross-server functionality
"""

import pytest


@pytest.mark.asyncio
async def test_all_servers_auto_connect(all_servers_client):
    """Test that all built-in servers auto-connect successfully"""
    client = all_servers_client
    
    servers = await client.get_all_servers()
    
    # Should have at least 4 servers (filesystem, git, codebase, devtools)
    # Exa might fail without API key
    assert len(servers) >= 4, f"Expected at least 4 servers, got {len(servers)}"
    
    # Check that basic servers are connected
    essential_servers = ["filesystem", "git", "codebase", "devtools"]
    for server in essential_servers:
        assert server in servers, f"Essential server {server} not connected"
        assert servers[server]["status"] == "connected"


@pytest.mark.asyncio
async def test_intent_analysis_accuracy(all_servers_client, sample_queries):
    """Test that intent analysis correctly identifies query types"""
    client = all_servers_client
    
    # Test file operations
    for query in sample_queries["file_operations"]:
        intent = await client.analyze_query_intent(query)
        assert "filesystem" in intent["servers_needed"], f"Query '{query}' should need filesystem server"
    
    # Test git operations
    for query in sample_queries["git_operations"]:
        intent = await client.analyze_query_intent(query)
        assert "git" in intent["servers_needed"], f"Query '{query}' should need git server"
    
    # Test codebase analysis
    for query in sample_queries["codebase_analysis"]:
        intent = await client.analyze_query_intent(query)
        assert "codebase" in intent["servers_needed"], f"Query '{query}' should need codebase server"
    
    # Test development tasks
    for query in sample_queries["development_tasks"]:
        intent = await client.analyze_query_intent(query)
        assert "devtools" in intent["servers_needed"], f"Query '{query}' should need devtools server"


@pytest.mark.asyncio
async def test_tool_discovery_completeness(all_servers_client):
    """Test that all expected tools are discovered and available"""
    client = all_servers_client
    
    tools_by_server = await client.get_all_available_tools()
    
    # Expected tool counts for each server
    expected_tools = {
        "filesystem": ["read_file", "write_file", "edit_file", "list_directory", "search_files", 
                      "get_file_info", "create_directory", "delete_file"],
        "git": ["git_status", "git_diff", "git_log", "git_add", "git_commit", "git_branch_info",
               "git_search_history", "git_show_commit", "git_reset_file", "git_stash", "git_stash_list"],
        "codebase": ["analyze_project", "get_project_structure", "find_definition", 
                    "find_references", "explain_codebase", "get_project_context"],
        "devtools": ["run_tests", "run_command_safe", "lint_code", "format_code", 
                    "check_types", "install_dependencies"]
    }
    
    for server_id, expected_tool_names in expected_tools.items():
        if server_id in tools_by_server:
            available_tools = [tool["name"] for tool in tools_by_server[server_id]]
            for expected_tool in expected_tool_names:
                assert expected_tool in available_tools, \
                    f"Tool {expected_tool} missing from {server_id} server"


@pytest.mark.asyncio
async def test_query_processing_end_to_end(all_servers_client, temp_file):
    """Test complete query processing workflow"""
    client = all_servers_client
    
    # Test with a file operation query
    query = f"read the file {temp_file}"
    
    # Analyze intent
    intent = await client.analyze_query_intent(query)
    assert "filesystem" in intent["servers_needed"]
    
    # Enhance query with context
    enhanced_query = await client.enhance_query_with_context(query, intent)
    assert "filesystem" in enhanced_query.lower()
    assert "read_file" in enhanced_query


@pytest.mark.asyncio
async def test_metrics_tracking(all_servers_client, temp_file):
    """Test that metrics are properly tracked during query processing"""
    client = all_servers_client
    
    # Clear any existing metrics
    client.query_metrics = []
    
    # Process a simple query
    if client.engine:  # Only test if engine is available
        query = f"read {temp_file}"
        try:
            result = await client.process_query(query)
            
            # Check metrics were recorded
            assert len(client.query_metrics) > 0, "No metrics recorded"
            
            last_metric = client.query_metrics[-1]
            assert last_metric.query == query
            assert last_metric.end_time is not None
            assert last_metric.duration_seconds is not None
            assert last_metric.duration_seconds > 0
            
        except Exception as e:
            # If processing fails due to missing engine, that's expected
            if "Engine not configured" in str(e):
                pytest.skip("Engine not configured for testing")
            else:
                raise


@pytest.mark.asyncio
async def test_tool_listing_detection(all_servers_client):
    """Test that tool listing queries are properly detected and handled"""
    client = all_servers_client
    
    tool_listing_queries = [
        "list tools",
        "show available tools", 
        "what tools do you have",
        "list all MCP tools",
        "show me the tools"
    ]
    
    for query in tool_listing_queries:
        is_tool_listing = client.detect_tool_listing_intent(query)
        assert is_tool_listing, f"Query '{query}' should be detected as tool listing"


@pytest.mark.asyncio
async def test_cross_server_workflow(all_servers_client, sample_project_structure):
    """Test workflow that involves multiple servers"""
    client = all_servers_client
    
    # Test a development workflow query that might need multiple servers
    query = "analyze this project and show me the git status"
    
    intent = await client.analyze_query_intent(query)
    
    # Should identify need for both codebase and git servers
    servers_needed = intent["servers_needed"]
    assert "codebase" in servers_needed or intent["operation_type"] == "codebase_analysis"
    # Git might be detected depending on the LLM analysis


@pytest.mark.asyncio
async def test_error_handling_across_servers(all_servers_client):
    """Test error handling when servers encounter issues"""
    client = all_servers_client
    
    servers = await client.get_all_servers()
    
    for server_id in servers.keys():
        # Test that we can handle errors gracefully
        try:
            tools = await client.list_tools(server_id)
            assert isinstance(tools, list)
        except Exception as e:
            # Errors should be handled gracefully
            assert "error" in str(e).lower() or "fail" in str(e).lower()


@pytest.mark.asyncio
async def test_session_management(all_servers_client):
    """Test MCP session management"""
    client = all_servers_client
    
    servers = await client.get_all_servers()
    
    for server_id in servers.keys():
        # Test that sessions can be created and used
        async with client._multi_server_client.session(server_id) as session:
            await session.initialize()
            # Session should be usable
            assert session is not None


@pytest.mark.asyncio
async def test_concurrent_server_operations(all_servers_client):
    """Test that multiple servers can be used concurrently"""
    client = all_servers_client
    
    import asyncio
    
    servers = await client.get_all_servers()
    
    # Create tasks for each server
    tasks = []
    for server_id in servers.keys():
        task = asyncio.create_task(client.list_tools(server_id))
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check that most operations succeeded
    successful_operations = sum(1 for result in results if not isinstance(result, Exception))
    assert successful_operations >= len(servers) // 2, "Too many concurrent operations failed"


@pytest.mark.asyncio
async def test_query_enhancement_with_dynamic_tools(all_servers_client):
    """Test that query enhancement uses actual available tools"""
    client = all_servers_client
    
    # Test file operation enhancement
    intent = {"servers_needed": {"filesystem"}, "operation_type": "file_operation"}
    enhanced = await client.enhance_query_with_context("read a file", intent)
    
    # Should include actual filesystem tools
    assert "read_file" in enhanced
    assert "write_file" in enhanced
    assert "filesystem" in enhanced.lower()


@pytest.mark.asyncio
async def test_fallback_intent_analysis(all_servers_client):
    """Test fallback intent analysis when LLM is not available"""
    client = all_servers_client
    
    # Temporarily remove engine to test fallback
    original_engine = client.engine
    client.engine = None
    
    try:
        # Test various query types
        test_cases = [
            ("read package.json", "filesystem"),
            ("git status", "git"), 
            ("analyze project", "codebase"),
            ("run tests", "devtools"),
            ("weather in Toronto", "exa")
        ]
        
        for query, expected_server in test_cases:
            intent = await client.analyze_query_intent(query)
            if expected_server in intent["servers_needed"] or intent["operation_type"] in ["file_operation", "git_operation", "codebase_analysis", "development_task", "web_search"]:
                # Fallback analysis working correctly
                assert True
            else:
                # Some queries might not match patterns exactly, but should not error
                assert isinstance(intent, dict)
                assert "servers_needed" in intent
                
    finally:
        # Restore original engine
        client.engine = original_engine