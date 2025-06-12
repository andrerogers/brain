#!/usr/bin/env python3
"""
Local MCP Server that uses Exa API for web search, compatible with stdio connections
using FastMCP and decorator pattern as per official MCP documentation
"""

import os
import sys
import exa_py
import asyncio
import argparse

from typing import Dict, List, Any
from mcp.server.fastmcp import FastMCP

from config import get_settings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'brain', 'src')))

parser = argparse.ArgumentParser(description="Run a local MCP server that uses Exa API")
parser.add_argument("--api-key", type=str, help="Exa API key")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
args = parser.parse_args()

settings = get_settings()

if not settings.exa_api_key:
    print("Error: Exa API key is required. Provide it with --api-key or set EXA_API_KEY environment variable.", file=sys.stderr)
    sys.exit(1)

# Initialize Exa client
exa_client = exa_py.Exa(api_key=settings.exa_api_key)

# Initialize FastMCP server
mcp = FastMCP("exa")


async def search_with_exa(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """Search the web using Exa API and return formatted results."""
    try:
        # Call Exa API for search
        search_response = exa_client.search(
            query=query,
            num_results=num_results,
            use_autoprompt=True,
            include_domains=None,
            exclude_domains=None,
            start_published_date=None,
            end_published_date=None,
        )
        # Format results
        results = []
        for result in search_response.results:
            results.append({
                "title": result.title,
                "url": result.url,
                "snippet": result.text,
                "published_date": result.published_date,
            })
        return results
    except Exception as e:
        print(f"Error searching with Exa: {str(e)}", file=sys.stderr)
        return []


async def crawl_with_exa(url: str) -> Dict[str, Any]:
    """Fetch and extract content from a URL using Exa API."""
    try:
        # Call Exa API to crawl the URL
        content_response = exa_client.get_contents(
            urls=[url],
            text={"include_html_tags": False}
        )
        # Extract content
        if len(content_response.results) > 0:
            return {
                "success": True,
                "text": content_response.results[0].text,
                "url": url
            }
        else:
            return {
                "success": False,
                "error": content_response.error,
                "url": url
            }
    except Exception as e:
        print(f"Error crawling URL with Exa: {str(e)}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


@mcp.tool()
async def web_search_exa(query: str, num_results: int = 5) -> str:
    """Search the web using Exa AI. Returns real-time search results from the internet.
    Args:
        query: The search query
        num_results: Number of results to return (default: 5)
    """
    print(f"Searching for: {query} (max results: {num_results})", file=sys.stderr)
    results = await search_with_exa(query, num_results)
    if not results:
        return "No results found or an error occurred during search."

    response_text = f"Search results for: {query}\n\n"
    for i, result in enumerate(results, 1):
        response_text += f"{i}. {result['title']}\n"
        response_text += f"   URL: {result['url']}\n"
        response_text += f"   {result['snippet']}\n\n"
    return response_text


@mcp.tool()
async def crawl_url(url: str) -> str:
    """Fetch and extract content from a specific URL using Exa AI.
    Args:
        url: The URL to crawl
    """
    print(f"Crawling URL: {url}", file=sys.stderr)
    result = await crawl_with_exa(url)
    if result["success"]:
        response_text = f"Content from: {url}\n\n{result['text']}"
    else:
        response_text = f"Failed to crawl URL: {url}. Error: {result['error']}"
    return response_text


async def main():
    """Main entry point"""
    print("Starting Exa MCP Server with stdio transport", file=sys.stderr)
    print("Available tools: web_search_exa, crawl_url", file=sys.stderr)
    # Start the server with stdio transport
    await mcp.run_stdio_async()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        sys.exit(1)
