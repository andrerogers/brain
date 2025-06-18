#!/usr/bin/env python3
"""
Local MCP Server that uses Exa API for web search, compatible with stdio connections
using FastMCP and decorator pattern as per official MCP documentation
"""

import os
import sys
import re
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


def clean_content(text: str) -> str:
    """Clean extracted content by removing common non-content elements."""
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    # Common patterns to filter out
    skip_patterns = [
        # Navigation and menu items
        'menu', 'navigation', 'nav', 'breadcrumb',
        # Footer content
        'footer', 'copyright', '©', 'all rights reserved',
        # Social media and sharing
        'share', 'tweet', 'facebook', 'instagram', 'linkedin', 'follow us',
        # Ads and promotional
        'advertisement', 'sponsored', 'promo', 'sale', 'discount',
        # Cookie and privacy notices
        'cookie', 'privacy policy', 'terms of service', 'gdpr',
        # Common UI elements
        'skip to content', 'back to top', 'scroll',
        # Empty or very short lines that are likely UI elements
    ]
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Skip very short lines (likely UI elements)
        if len(line) < 10:
            continue
            
        # Skip lines that match common non-content patterns
        line_lower = line.lower()
        if any(pattern in line_lower for pattern in skip_patterns):
            continue
            
        # Skip lines that are mostly punctuation or numbers (likely formatting)
        if len([c for c in line if c.isalnum()]) < len(line) * 0.5:
            continue
            
        cleaned_lines.append(line)
    
    # Join lines and remove excessive whitespace
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Remove multiple consecutive newlines
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
    
    return cleaned_text.strip()


async def crawl_with_exa(url: str) -> Dict[str, Any]:
    """Fetch and extract main content from a URL using Exa API with content cleaning."""
    try:
        # Call Exa API to crawl the URL with optimized settings for main content
        content_response = exa_client.get_contents(
            urls=[url],
            text={
                "include_html_tags": False,
                "max_characters": 10000,  # Limit content length
                "include_links": False    # Exclude link URLs to reduce noise
            }
        )
        
        # Extract and clean content
        if len(content_response.results) > 0:
            raw_text = content_response.results[0].text
            cleaned_text = clean_content(raw_text)
            
            if not cleaned_text:
                return {
                    "success": False,
                    "error": "No meaningful content extracted after cleaning",
                    "url": url
                }
            
            return {
                "success": True,
                "text": cleaned_text,
                "url": url
            }
        else:
            return {
                "success": False,
                "error": getattr(content_response, 'error', 'No content returned'),
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
    """Fetch and extract main content from a specific URL using Exa AI with content cleaning.
    This tool filters out navigation menus, footers, ads, and other non-content elements.
    Args:
        url: The URL to crawl
    """
    print(f"Crawling URL: {url}", file=sys.stderr)
    result = await crawl_with_exa(url)
    if result["success"]:
        content_length = len(result['text'])
        print(f"Successfully extracted {content_length} characters of cleaned content", file=sys.stderr)
        response_text = f"Main content from: {url}\n\n{result['text']}"
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
