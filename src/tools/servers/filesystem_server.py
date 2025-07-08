#!/usr/bin/env python3

import argparse
import difflib
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Add the config path to sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

# Initialize FastMCP server
mcp = FastMCP("filesystem")

# Security: Define allowed base paths (can be configured)
ALLOWED_PATHS = [
    str(Path.home()),  # User home directory
    "/tmp",  # Temporary directory
    os.getcwd(),  # Current working directory
    "/mnt/dev_drive",  # Development drive
    "/mnt/data-lake",  # Data lake for broader access
]


def is_path_allowed(path: str) -> bool:
    """Check if a path is within allowed directories"""
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(allowed) for allowed in ALLOWED_PATHS)


def safe_path_join(*args) -> str:
    """Safely join path components and ensure it's within allowed paths"""
    path = os.path.abspath(os.path.join(*args))
    if not is_path_allowed(path):
        # Instead of immediately raising an error, provide a helpful message
        raise PermissionError(
            f"Access denied to path: {path}\n"
            f"This path is outside the allowed directories. "
            f"Allowed paths include:\n"
            + "\n".join(f"  - {allowed}" for allowed in ALLOWED_PATHS)
            + f"\n\nTo access this path, please add it to the allowed paths configuration."
        )
    return path


@mcp.tool()
def read_file(
    path: str, start_line: Optional[int] = None, end_line: Optional[int] = None
) -> str:
    """
    Read contents of a file

    Args:
        path: Path to the file to read
        start_line: Optional starting line number (1-indexed)
        end_line: Optional ending line number (1-indexed)

    Returns:
        File contents as string
    """
    try:
        safe_path = safe_path_join(path)

        if not os.path.exists(safe_path):
            return f"Error: File does not exist: {path}"

        if not os.path.isfile(safe_path):
            return f"Error: Path is not a file: {path}"

        with open(safe_path, "r", encoding="utf-8") as f:
            if start_line is None and end_line is None:
                content = f.read()
            else:
                lines = f.readlines()
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line else len(lines)
                content = "".join(lines[start:end])

        return content

    except UnicodeDecodeError:
        return f"Error: File contains binary data and cannot be read as text: {path}"
    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"


@mcp.tool()
def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """
    Write content to a file

    Args:
        path: Path to the file to write
        content: Content to write to the file
        create_dirs: Whether to create parent directories if they don't exist

    Returns:
        Success or error message
    """
    try:
        safe_path = safe_path_join(path)

        if create_dirs:
            parent_dir = os.path.dirname(safe_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to {path}"

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"


@mcp.tool()
def edit_file(path: str, old_content: str, new_content: str) -> str:
    """
    Edit a file by replacing old_content with new_content

    Args:
        path: Path to the file to edit
        old_content: Content to replace
        new_content: New content to insert

    Returns:
        Success message with changes applied
    """
    try:
        safe_path = safe_path_join(path)

        if not os.path.exists(safe_path):
            return f"Error: File does not exist: {path}"

        # Read current content
        with open(safe_path, "r", encoding="utf-8") as f:
            current_content = f.read()

        # Replace old content with new content
        if old_content not in current_content:
            return f"Error: Old content not found in file {path}"

        updated_content = current_content.replace(old_content, new_content, 1)

        # Write back the updated content
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        # Generate diff for feedback
        diff = list(
            difflib.unified_diff(
                current_content.splitlines(keepends=True),
                updated_content.splitlines(keepends=True),
                fromfile=f"{path} (before)",
                tofile=f"{path} (after)",
                lineterm="",
            )
        )

        diff_str = "".join(diff) if diff else "No differences"

        return f"Successfully edited {path}. Changes:\n{diff_str}"

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error editing file {path}: {str(e)}"


@mcp.tool()
def list_directory(
    path: str = ".", show_hidden: bool = False, recursive: bool = False
) -> str:
    """
    List contents of a directory

    Args:
        path: Path to the directory to list
        show_hidden: Whether to show hidden files (starting with .)
        recursive: Whether to list recursively

    Returns:
        Directory listing as formatted string
    """
    try:
        safe_path = safe_path_join(path)

        if not os.path.exists(safe_path):
            return f"Error: Directory does not exist: {path}"

        if not os.path.isdir(safe_path):
            return f"Error: Path is not a directory: {path}"

        items = []

        if recursive:
            for root, dirs, files in os.walk(safe_path):
                # Filter hidden directories and files if needed
                if not show_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    files = [f for f in files if not f.startswith(".")]

                level = root.replace(safe_path, "").count(os.sep)
                indent = "  " * level
                items.append(f"{indent}{os.path.basename(root)}/")

                sub_indent = "  " * (level + 1)
                for file in files:
                    items.append(f"{sub_indent}{file}")
        else:
            entries = os.listdir(safe_path)
            if not show_hidden:
                entries = [e for e in entries if not e.startswith(".")]

            entries.sort()

            for entry in entries:
                entry_path = os.path.join(safe_path, entry)
                if os.path.isdir(entry_path):
                    items.append(f"{entry}/")
                else:
                    stat = os.stat(entry_path)
                    size = stat.st_size
                    items.append(f"{entry} ({size} bytes)")

        if not items:
            return f"Directory {path} is empty"

        return f"Contents of {path}:\n" + "\n".join(items)

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error listing directory {path}: {str(e)}"


@mcp.tool()
def search_files(
    pattern: str, directory: str = ".", file_pattern: str = "*", max_results: int = 100
) -> str:
    """
    Search for text patterns in files

    Args:
        pattern: Text pattern to search for
        directory: Directory to search in
        file_pattern: File name pattern (e.g., "*.py", "*.js")
        max_results: Maximum number of results to return

    Returns:
        Search results with file paths and line numbers
    """
    try:
        safe_dir = safe_path_join(directory)

        if not os.path.exists(safe_dir):
            return f"Error: Directory does not exist: {directory}"

        if not os.path.isdir(safe_dir):
            return f"Error: Path is not a directory: {directory}"

        results = []
        file_count = 0

        for root, dirs, files in os.walk(safe_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                if fnmatch.fnmatch(file, file_pattern) and not file.startswith("."):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line_num, line in enumerate(f, 1):
                                if pattern.lower() in line.lower():
                                    rel_path = os.path.relpath(file_path, safe_dir)
                                    results.append(
                                        f"{rel_path}:{line_num}: {line.strip()}"
                                    )

                                    if len(results) >= max_results:
                                        break

                        file_count += 1
                        if len(results) >= max_results:
                            break

                    except (UnicodeDecodeError, PermissionError):
                        # Skip binary files or files we can't read
                        continue

            if len(results) >= max_results:
                break

        if not results:
            return f"No matches found for pattern '{pattern}' in {file_count} files"

        result_str = (
            f"Found {len(results)} matches for '{pattern}' in {file_count} files:\n"
        )
        result_str += "\n".join(results)

        if len(results) >= max_results:
            result_str += f"\n... (truncated to {max_results} results)"

        return result_str

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error searching files: {str(e)}"


@mcp.tool()
def get_file_info(path: str) -> str:
    """
    Get information about a file or directory

    Args:
        path: Path to the file or directory

    Returns:
        File information including size, permissions, modification time
    """
    try:
        safe_path = safe_path_join(path)

        if not os.path.exists(safe_path):
            return f"Error: Path does not exist: {path}"

        stat = os.stat(safe_path)

        info = {
            "path": path,
            "absolute_path": safe_path,
            "type": "directory" if os.path.isdir(safe_path) else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "permissions": oct(stat.st_mode)[-3:],
            "readable": os.access(safe_path, os.R_OK),
            "writable": os.access(safe_path, os.W_OK),
            "executable": os.access(safe_path, os.X_OK),
        }

        # Add line count for text files
        if os.path.isfile(safe_path):
            try:
                with open(safe_path, "r", encoding="utf-8") as f:
                    lines = sum(1 for _ in f)
                info["lines"] = lines
            except (UnicodeDecodeError, PermissionError):
                info["lines"] = "N/A (binary or unreadable)"

        return json.dumps(info, indent=2)

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error getting file info for {path}: {str(e)}"


@mcp.tool()
def create_directory(path: str, parents: bool = True) -> str:
    """
    Create a directory

    Args:
        path: Path to the directory to create
        parents: Whether to create parent directories if they don't exist

    Returns:
        Success or error message
    """
    try:
        # Expand user home directory (~) if present
        expanded_path = os.path.expanduser(path)
        safe_path = safe_path_join(expanded_path)

        if os.path.exists(safe_path):
            return f"Directory already exists: {safe_path}"

        os.makedirs(safe_path, exist_ok=parents)

        return f"Successfully created directory: {safe_path}"

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error creating directory {path}: {str(e)}"


@mcp.tool()
def delete_file(path: str) -> str:
    """
    Delete a file (use with caution)

    Args:
        path: Path to the file to delete

    Returns:
        Success or error message
    """
    try:
        safe_path = safe_path_join(path)

        if not os.path.exists(safe_path):
            return f"Error: File does not exist: {path}"

        if os.path.isdir(safe_path):
            return f"Error: Path is a directory, not a file: {path}"

        os.remove(safe_path)

        return f"Successfully deleted file: {path}"

    except PermissionError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error deleting file {path}: {str(e)}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File system MCP server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Add current working directory to allowed paths
    cwd = os.getcwd()
    if cwd not in ALLOWED_PATHS:
        ALLOWED_PATHS.append(cwd)

    # Run the server
    mcp.run()
