#!/usr/bin/env python3

import argparse
import asyncio
import re
import sys
from typing import Any, Dict, List, Optional

import exa_py
from mcp.server.fastmcp import FastMCP

from config import get_settings


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a local MCP server that uses Exa API"
    )
    parser.add_argument(
        "--api-key", type=str, help="Exa API key (overrides environment variable)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


def setup_configuration(args) -> Dict[str, Any]:
    """Setup configuration from arguments and environment."""
    settings = get_settings()

    # Command line arguments override environment variables
    config = {
        "exa_api_key": args.api_key if args.api_key else settings.exa_api_key,
        "debug": args.debug or settings.debug,
    }

    return config


def validate_configuration(config: Dict[str, Any]) -> bool:
    """Validate that required configuration is present."""
    if not config.get("exa_api_key"):
        print(
            "Error: Exa API key is required. "
            "Provide it with --api-key or set EXA_API_KEY environment variable.",
            file=sys.stderr,
        )
        return False
    return True


# Global variables
exa_client: Optional[exa_py.Exa] = None
debug_mode: bool = False


def log_debug(message: str):
    """Log debug message if debug mode is enabled."""
    if debug_mode:
        print(f"DEBUG: {message}", file=sys.stderr)


async def search_with_exa(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """Search the web using Exa API and return formatted results."""
    if not exa_client:
        raise ValueError("Exa client not initialized")

    try:
        log_debug(f"Searching with query: {query}, num_results: {num_results}")

        # Call Exa API for search with better error handling
        search_response = exa_client.search_and_contents(
            query=query,
            num_results=min(num_results, 10),  # Limit to reasonable number
            use_autoprompt=True,
            include_domains=None,
            exclude_domains=None,
            start_published_date=None,
            end_published_date=None,
            text=True  # Include text content in search results
        )

        # Enhanced debugging for response structure
        log_debug(f"Search response type: {type(search_response)}")
        log_debug(f"Search response: {search_response}")
        
        # Format results with better error handling
        results = []
        if search_response is None:
            log_debug("Search response is None - possible API quota exceeded or network issue")
            return []
            
        if not hasattr(search_response, 'results'):
            log_debug(f"Search response missing 'results' attribute. Available attributes: {dir(search_response)}")
            return []
            
        if search_response.results is None:
            log_debug("Search response.results is None")
            return []
            
        if len(search_response.results) == 0:
            log_debug("Search response.results is empty")
            return []

        log_debug(f"Processing {len(search_response.results)} search results")
        for i, result in enumerate(search_response.results):
            try:
                log_debug(f"Processing result {i}: {type(result)}")
                formatted_result = {
                    "title": getattr(result, "title", "No title"),
                    "url": getattr(result, "url", ""),
                    "snippet": getattr(result, "text", "No content available")[:500],
                    "published_date": getattr(result, "published_date", None),
                }
                results.append(formatted_result)
            except Exception as result_error:
                log_debug(f"Error processing result {i}: {result_error}")
                continue

        log_debug(f"Successfully retrieved {len(results)} search results")
        return results

    except Exception as e:
        error_msg = f"Error searching with Exa: {str(e)}"
        print(error_msg, file=sys.stderr)
        log_debug(f"Search error details: {type(e).__name__}: {str(e)}")
        log_debug(f"Full error traceback: {repr(e)}")
        return []


def clean_content(text: str) -> str:
    """Clean extracted content by removing common non-content elements."""
    if not text:
        return ""

    lines = text.split("\n")
    cleaned_lines = []

    # Refined patterns to filter out - less aggressive
    skip_patterns = [
        # Navigation and menu items (more specific)
        "main menu",
        "navigation menu",
        "skip to main content",
        "breadcrumb",
        # Footer content (more specific)
        "footer",
        "© 2024",
        "© 2023",
        "all rights reserved",
        "terms of service",
        "privacy policy",
        # Social media (more specific)
        "follow us on",
        "share on facebook",
        "share on twitter",
        # Ads (more specific)
        "advertisement",
        "sponsored content",
        # Cookie notices (more specific)
        "we use cookies",
        "cookie policy",
        "accept cookies",
    ]

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip very short lines that are likely UI elements
        if len(line) < 5:
            continue

        # Skip lines that match common non-content patterns (case insensitive)
        line_lower = line.lower()
        if any(pattern in line_lower for pattern in skip_patterns):
            continue

        # Skip lines that are mostly punctuation or special characters
        alphanumeric_chars = sum(1 for c in line if c.isalnum())
        if len(line) > 10 and alphanumeric_chars < len(line) * 0.3:
            continue

        cleaned_lines.append(line)

    # Join lines and remove excessive whitespace
    cleaned_text = "\n".join(cleaned_lines)

    # Remove multiple consecutive newlines (but keep paragraph breaks)
    cleaned_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned_text)

    return cleaned_text.strip()


async def crawl_with_exa(url: str) -> Dict[str, Any]:
    """Fetch and extract main content from a URL using Exa API."""
    if not exa_client:
        return {"success": False, "error": "Exa client not initialized", "url": url}

    try:
        log_debug(f"Crawling URL: {url}")

        # Call Exa API to crawl the URL - using True for text parameter
        # which should enable text extraction with default settings
        content_response = exa_client.get_contents(
            urls=[url], text=True  # Fixed: Use True instead of dict for proper typing
        )

        # Enhanced debugging for response structure
        log_debug(f"Content response type: {type(content_response)}")
        log_debug(f"Content response: {content_response}")

        # Extract and clean content with improved error handling
        if content_response is None:
            log_debug("Content response is None - possible API quota exceeded or network issue")
            return {
                "success": False,
                "error": "No content returned from Exa API - possible quota exceeded",
                "url": url,
            }
            
        if not hasattr(content_response, 'results'):
            log_debug(f"Content response missing 'results' attribute. Available attributes: {dir(content_response)}")
            return {
                "success": False,
                "error": "Invalid response structure from Exa API",
                "url": url,
            }
            
        if content_response.results is None:
            log_debug("Content response.results is None")
            return {
                "success": False,
                "error": "No results returned from Exa API",
                "url": url,
            }
            
        if len(content_response.results) == 0:
            log_debug("Content response.results is empty")
            return {
                "success": False,
                "error": "No content results returned from Exa API",
                "url": url,
            }

        result = content_response.results[0]
        log_debug(f"First result type: {type(result)}")
        
        if not hasattr(result, 'text'):
            log_debug(f"Result missing 'text' attribute. Available attributes: {dir(result)}")
            return {
                "success": False,
                "error": "Result missing text content",
                "url": url,
            }

        raw_text = result.text
        if not raw_text:
            return {
                "success": False,
                "error": "No content returned from URL",
                "url": url,
            }

        cleaned_text = clean_content(raw_text)

        if not cleaned_text:
            return {
                "success": False,
                "error": "No meaningful content extracted after cleaning",
                "url": url,
            }

        log_debug(f"Successfully crawled {len(cleaned_text)} characters from {url}")
        return {"success": True, "text": cleaned_text, "url": url}
        
    except Exception as e:
        error_msg = f"Error crawling URL with Exa: {str(e)}"
        print(error_msg, file=sys.stderr)
        log_debug(f"Crawl error details: {type(e).__name__}: {str(e)}")
        log_debug(f"Full error traceback: {repr(e)}")
        return {"success": False, "error": str(e), "url": url}


# Initialize FastMCP server
mcp = FastMCP("exa")


@mcp.tool()
async def web_search_exa(query: str, num_results: int = 5) -> str:
    """Search the web using Exa AI.

    Returns real-time search results from the internet.

    Args:
        query: The search query
        num_results: Number of results to return (default: 5, max: 10)
    """
    if not query.strip():
        return "Error: Search query cannot be empty."

    # Validate and limit num_results
    num_results = max(1, min(num_results, 10))

    log_debug(f"Web search request: query='{query}', num_results={num_results}")

    results = await search_with_exa(query, num_results)
    if not results:
        error_msg = (
            f"No results found for query: '{query}'. "
            "This could be due to:\n"
            "- API quota exceeded\n"
            "- Network connectivity issues\n"
            "- Exa service temporarily unavailable\n"
            "- Query terms too specific or unusual\n\n"
            "Please try:\n"
            "- Simplifying your search terms\n"
            "- Trying again in a few minutes\n"
            "- Using alternative search terms"
        )
        log_debug(f"Search failed for query: {query}")
        return error_msg

    response_text = f"Search results for: {query}\n\n"
    for i, result in enumerate(results, 1):
        response_text += f"{i}. {result['title']}\n"
        response_text += f"   URL: {result['url']}\n"
        if result["snippet"]:
            snippet = result["snippet"][:300]
            if len(result["snippet"]) > 300:
                snippet += "..."
            response_text += f"   {snippet}\n"
        if result["published_date"]:
            response_text += f"   Published: {result['published_date']}\n"
        response_text += "\n"

    return response_text


@mcp.tool()
async def crawl_url(url: str) -> str:
    """Fetch and extract main content from a specific URL using Exa AI.

    This tool filters out navigation menus, footers, ads, and other
    non-content elements.

    Args:
        url: The URL to crawl
    """
    if not url.strip():
        return "Error: URL cannot be empty."

    # Basic URL validation
    if not (url.startswith("http://") or url.startswith("https://")):
        return "Error: URL must start with http:// or https://"

    log_debug(f"URL crawl request: {url}")

    result = await crawl_with_exa(url)
    if result["success"]:
        content_length = len(result["text"])
        log_debug(
            f"Successfully extracted {content_length} characters of cleaned content"
        )

        # Limit response length for better handling
        content = result["text"]
        if len(content) > 8000:
            content = content[:8000] + "\n\n[Content truncated - original was longer]"

        response_text = f"Main content from: {url}\n\n{content}"
    else:
        response_text = f"Failed to crawl URL: {url}\nError: {result['error']}"

    return response_text


async def main():
    """Main entry point"""
    try:
        # Parse arguments
        args = parse_arguments()

        # Setup configuration
        config = setup_configuration(args)

        # Validate configuration
        if not validate_configuration(config):
            sys.exit(1)

        # Set global variables
        global exa_client, debug_mode
        debug_mode = config["debug"]

        # Initialize Exa client
        exa_client = exa_py.Exa(api_key=config["exa_api_key"])

        print("Starting Exa MCP Server with stdio transport", file=sys.stderr)
        print("Available tools: web_search_exa, crawl_url", file=sys.stderr)
        if debug_mode:
            print("Debug mode enabled", file=sys.stderr)

        # Start the server with stdio transport
        await mcp.run_stdio_async()

    except Exception as e:
        print(f"Error during server initialization: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        sys.exit(1)
