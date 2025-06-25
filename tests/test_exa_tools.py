#!/usr/bin/env python3
"""
Test all exa server tools
"""

import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_exa_responses():
    """Mock responses for Exa API calls"""
    return {
        "search_response": MagicMock(
            results=[
                MagicMock(
                    title="Toronto Weather - Current Conditions",
                    url="https://weather.example.com/toronto",
                    text="Current weather in Toronto: 15°C, partly cloudy with light winds.",
                    published_date="2024-01-15"
                ),
                MagicMock(
                    title="Weather Network Toronto",
                    url="https://weathernetwork.example.com/toronto",
                    text="Toronto weather forecast shows mild temperatures continuing through the week.",
                    published_date="2024-01-15"
                )
            ]
        ),
        "content_response": MagicMock(
            results=[
                MagicMock(
                    text="# Weather Report\n\nCurrent conditions in Toronto:\n- Temperature: 15°C\n- Conditions: Partly cloudy\n- Wind: 10 km/h SW\n- Humidity: 65%\n\nForecast:\nToday: Partly cloudy, high 18°C\nTomorrow: Sunny, high 20°C"
                )
            ]
        )
    }


@pytest.mark.asyncio
async def test_exa_server_connection(connected_exa_client):
    """Test exa server connects successfully"""
    client = connected_exa_client
    
    # Note: This test might fail if EXA_API_KEY is not set or invalid
    # In a real environment, we'd want to mock the Exa client
    servers = await client.get_all_servers()
    
    # Check if exa server is in the list (it might fail to connect without valid API key)
    if "exa" in servers:
        assert servers["exa"]["status"] == "connected"
    else:
        pytest.skip("Exa server not connected (likely missing API key)")


@pytest.mark.asyncio
async def test_list_exa_tools(mcp_client, server_paths):
    """Test listing exa tools"""
    # Try to connect to exa server
    try:
        success = await mcp_client.connect_server("exa", server_paths["exa"])
        if not success:
            pytest.skip("Exa server connection failed (likely missing API key)")
    except Exception:
        pytest.skip("Exa server connection failed (likely missing API key)")
    
    tools = await mcp_client.list_tools("exa")
    tool_names = [tool.name for tool in tools]
    
    expected_tools = ["web_search_exa", "crawl_url"]
    
    for expected_tool in expected_tools:
        assert expected_tool in tool_names, f"Tool {expected_tool} not found"


@pytest.mark.asyncio
@patch('exa_py.Exa')
async def test_web_search_exa_tool(mock_exa_class, mcp_client, server_paths, mock_exa_responses):
    """Test web_search_exa tool with mocked Exa API"""
    # Setup mock
    mock_exa_instance = MagicMock()
    mock_exa_instance.search.return_value = mock_exa_responses["search_response"]
    mock_exa_class.return_value = mock_exa_instance
    
    # Connect to exa server
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    if not success:
        pytest.skip("Exa server connection failed")
    
    async with mcp_client._multi_server_client.session("exa") as session:
        await session.initialize()
        
        result = await mcp_client.call_tool("exa", "web_search_exa", {
            "query": "weather in Toronto",
            "num_results": 2
        }, session)
        
        result_str = str(result)
        assert "Toronto Weather" in result_str
        assert "weather.example.com" in result_str
        assert "15°C" in result_str
        assert "partly cloudy" in result_str


@pytest.mark.asyncio
@patch('exa_py.Exa')
async def test_crawl_url_tool(mock_exa_class, mcp_client, server_paths, mock_exa_responses):
    """Test crawl_url tool with mocked Exa API"""
    # Setup mock
    mock_exa_instance = MagicMock()
    mock_exa_instance.get_contents.return_value = mock_exa_responses["content_response"]
    mock_exa_class.return_value = mock_exa_instance
    
    # Connect to exa server
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    if not success:
        pytest.skip("Exa server connection failed")
    
    async with mcp_client._multi_server_client.session("exa") as session:
        await session.initialize()
        
        result = await mcp_client.call_tool("exa", "crawl_url", {
            "url": "https://weather.example.com/toronto"
        }, session)
        
        result_str = str(result)
        assert "Weather Report" in result_str
        assert "15°C" in result_str
        assert "Partly cloudy" in result_str
        assert "Forecast" in result_str


@pytest.mark.asyncio
@patch('exa_py.Exa')
async def test_web_search_with_different_num_results(mock_exa_class, mcp_client, server_paths, mock_exa_responses):
    """Test web_search_exa with different number of results"""
    # Setup mock
    mock_exa_instance = MagicMock()
    mock_exa_instance.search.return_value = mock_exa_responses["search_response"]
    mock_exa_class.return_value = mock_exa_instance
    
    # Connect to exa server
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    if not success:
        pytest.skip("Exa server connection failed")
    
    async with mcp_client._multi_server_client.session("exa") as session:
        await session.initialize()
        
        result = await mcp_client.call_tool("exa", "web_search_exa", {
            "query": "Python programming tutorials",
            "num_results": 10
        }, session)
        
        # Verify the search was called with correct parameters
        mock_exa_instance.search.assert_called_with(
            query="Python programming tutorials",
            num_results=10,
            use_autoprompt=True,
            include_domains=None,
            exclude_domains=None,
            start_published_date=None,
            end_published_date=None
        )


@pytest.mark.asyncio
@patch('exa_py.Exa')
async def test_web_search_error_handling(mock_exa_class, mcp_client, server_paths):
    """Test web_search_exa error handling"""
    # Setup mock to raise exception
    mock_exa_instance = MagicMock()
    mock_exa_instance.search.side_effect = Exception("API Error")
    mock_exa_class.return_value = mock_exa_instance
    
    # Connect to exa server
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    if not success:
        pytest.skip("Exa server connection failed")
    
    async with mcp_client._multi_server_client.session("exa") as session:
        await session.initialize()
        
        result = await mcp_client.call_tool("exa", "web_search_exa", {
            "query": "test query"
        }, session)
        
        result_str = str(result)
        assert "No results found" in result_str or "error occurred" in result_str


@pytest.mark.asyncio
@patch('exa_py.Exa')
async def test_crawl_url_error_handling(mock_exa_class, mcp_client, server_paths):
    """Test crawl_url error handling"""
    # Setup mock to raise exception
    mock_exa_instance = MagicMock()
    mock_exa_instance.get_contents.side_effect = Exception("API Error")
    mock_exa_class.return_value = mock_exa_instance
    
    # Connect to exa server
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    if not success:
        pytest.skip("Exa server connection failed")
    
    async with mcp_client._multi_server_client.session("exa") as session:
        await session.initialize()
        
        result = await mcp_client.call_tool("exa", "crawl_url", {
            "url": "https://example.com"
        }, session)
        
        result_str = str(result)
        assert "Failed to crawl" in result_str or "Error:" in result_str


@pytest.mark.asyncio
@patch('exa_py.Exa')
async def test_crawl_url_content_cleaning(mock_exa_class, mcp_client, server_paths):
    """Test crawl_url content cleaning functionality"""
    # Setup mock with content that should be cleaned
    mock_response = MagicMock(
        results=[
            MagicMock(
                text="""
                Menu
                Navigation
                
                Main content here with useful information.
                This is the actual content we want to extract.
                
                Footer
                Copyright © 2024
                Privacy Policy
                Cookie Notice
                """
            )
        ]
    )
    
    mock_exa_instance = MagicMock()
    mock_exa_instance.get_contents.return_value = mock_response
    mock_exa_class.return_value = mock_exa_instance
    
    # Connect to exa server
    success = await mcp_client.connect_server("exa", server_paths["exa"])
    if not success:
        pytest.skip("Exa server connection failed")
    
    async with mcp_client._multi_server_client.session("exa") as session:
        await session.initialize()
        
        result = await mcp_client.call_tool("exa", "crawl_url", {
            "url": "https://example.com"
        }, session)
        
        result_str = str(result)
        # Main content should be preserved
        assert "Main content here" in result_str
        assert "useful information" in result_str
        
        # Navigation and footer elements should be filtered out
        assert "Menu" not in result_str
        assert "Navigation" not in result_str
        assert "Footer" not in result_str
        assert "Copyright" not in result_str


# Integration tests that can run without API key but skip if connection fails
@pytest.mark.asyncio
async def test_exa_tools_integration_weather_query(all_servers_client, sample_queries):
    """Integration test for weather query intent detection"""
    client = all_servers_client
    
    # Test that weather queries are detected as web search intent
    for query in sample_queries["web_search"]:
        if "weather" in query.lower():
            intent = await client.analyze_query_intent(query)
            
            # Should detect web search intent
            assert intent["operation_type"] == "web_search" or "exa" in intent["servers_needed"], \
                f"Query '{query}' should be detected as web search"


@pytest.mark.asyncio
async def test_exa_tools_integration_current_events(all_servers_client, sample_queries):
    """Integration test for current events query intent detection"""
    client = all_servers_client
    
    # Test current events queries
    current_event_queries = [q for q in sample_queries["web_search"] if any(word in q.lower() for word in ["current", "latest", "news", "today"])]
    
    for query in current_event_queries:
        intent = await client.analyze_query_intent(query)
        
        # Should detect web search intent
        assert intent["operation_type"] == "web_search" or "exa" in intent["servers_needed"], \
            f"Query '{query}' should be detected as web search"