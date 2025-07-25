#!/usr/bin/env python3

import argparse
import os
import subprocess
from typing import Any, Dict, List, Optional, Union

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("git")


def run_git_command(command: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a git command and return the result

    Args:
        command: Git command as list of strings
        cwd: Working directory to run command in

    Returns:
        Dictionary with stdout, stderr, and return code
    """
    try:
        if cwd is None:
            cwd = os.getcwd()

        # Ensure we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"], cwd=cwd, capture_output=True, text=True
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Not a git repository: {cwd}",
                "stdout": "",
                "stderr": result.stderr,
            }

        # Run the actual git command
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": ""}


@mcp.tool()
def git_status(path: str = ".") -> str:
    """
    Get git status for the repository

    Args:
        path: Path to the git repository

    Returns:
        Git status output
    """
    result = run_git_command(["git", "status", "--porcelain"], cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    if not result["stdout"].strip():
        return "Working tree clean - no changes to commit"

    # Parse porcelain output for better formatting
    lines = result["stdout"].strip().split("\n")
    changes = {"staged": [], "modified": [], "untracked": [], "deleted": []}

    for line in lines:
        if len(line) < 3:
            continue

        status = line[:2]
        filename = line[3:]

        if status[0] in "AM":
            changes["staged"].append(filename)
        elif status[1] == "M":
            changes["modified"].append(filename)
        elif status[1] == "D":
            changes["deleted"].append(filename)
        elif status == "??":
            changes["untracked"].append(filename)

    output = []

    if changes["staged"]:
        output.append("Staged for commit:")
        for file in changes["staged"]:
            output.append(f"  + {file}")

    if changes["modified"]:
        output.append("Modified files:")
        for file in changes["modified"]:
            output.append(f"  M {file}")

    if changes["deleted"]:
        output.append("Deleted files:")
        for file in changes["deleted"]:
            output.append(f"  D {file}")

    if changes["untracked"]:
        output.append("Untracked files:")
        for file in changes["untracked"]:
            output.append(f"  ? {file}")

    return "\n".join(output)


@mcp.tool()
def git_diff(
    file_path: Optional[str] = None, staged: bool = False, path: str = "."
) -> str:
    """
    Show git diff for files

    Args:
        file_path: Specific file to show diff for (optional)
        staged: Show staged changes instead of working directory changes
        path: Path to the git repository

    Returns:
        Git diff output
    """
    command = ["git", "diff"]

    if staged:
        command.append("--staged")

    if file_path:
        command.append(file_path)

    result = run_git_command(command, cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    if not result["stdout"].strip():
        return "No differences found"

    return result["stdout"]


@mcp.tool()
def git_log(limit: int = 10, file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Show git commit history

    Args:
        limit: Number of commits to show
        file_path: Show log for specific file (optional)
        path: Path to the git repository

    Returns:
        Git log output
    """
    command = ["git", "log", f"-{limit}", "--oneline", "--decorate", "--graph"]

    if file_path:
        command.extend(["--", file_path])

    result = run_git_command(command, cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    if not result["stdout"].strip():
        return "No commit history found"

    return result["stdout"]


@mcp.tool()
def git_add(file_paths: Union[str, List[str]], path: str = ".") -> str:
    """
    Stage files for commit

    Args:
        file_paths: File path(s) to stage (string or list of strings)
        path: Path to the git repository

    Returns:
        Success or error message
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    command = ["git", "add"] + file_paths
    result = run_git_command(command, cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    return f"Successfully staged {len(file_paths)} file(s): {', '.join(file_paths)}"


@mcp.tool()
def git_commit(message: str, path: str = ".") -> str:
    """
    Create a git commit

    Args:
        message: Commit message
        path: Path to the git repository

    Returns:
        Success or error message with commit info
    """
    command = ["git", "commit", "-m", message]
    result = run_git_command(command, cwd=path)

    if not result["success"]:
        error_msg = result.get("error", result.get("stderr", "Unknown error"))
        if "nothing to commit" in error_msg:
            return "Nothing to commit - working tree clean"
        return f"Error: {error_msg}"

    # Get the commit hash
    hash_result = run_git_command(["git", "rev-parse", "HEAD"], cwd=path)
    commit_hash = (
        hash_result["stdout"].strip()[:8] if hash_result["success"] else "unknown"
    )

    return f"Successfully created commit {commit_hash}: {message}"


@mcp.tool()
def git_branch_info(path: str = ".") -> str:
    """
    Get current branch and remote information

    Args:
        path: Path to the git repository

    Returns:
        Branch and remote information
    """
    # Get current branch
    branch_result = run_git_command(["git", "branch", "--show-current"], cwd=path)
    if not branch_result["success"]:
        return f"Error: {branch_result.get('error', branch_result.get('stderr', 'Unknown error'))}"

    current_branch = branch_result["stdout"].strip()

    # Get remote information
    remote_result = run_git_command(["git", "remote", "-v"], cwd=path)
    remotes = (
        remote_result["stdout"].strip()
        if remote_result["success"]
        else "No remotes configured"
    )

    # Get ahead/behind information
    ahead_behind_result = run_git_command(
        [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            f"HEAD...origin/{current_branch}",
        ],
        cwd=path,
    )

    output = [f"Current branch: {current_branch}"]

    if ahead_behind_result["success"]:
        counts = ahead_behind_result["stdout"].strip().split()
        if len(counts) == 2:
            ahead, behind = counts
            if ahead != "0" or behind != "0":
                output.append(
                    f"Branch status: {ahead} ahead, {behind} behind origin/{current_branch}"
                )
            else:
                output.append("Branch is up to date with origin")

    if remotes and remotes != "No remotes configured":
        output.append(f"Remotes:\n{remotes}")
    else:
        output.append("No remotes configured")

    return "\n".join(output)


@mcp.tool()
def git_search_history(query: str, limit: int = 20, path: str = ".") -> str:
    """
    Search git commit history for a query

    Args:
        query: Search query for commit messages and diffs
        limit: Maximum number of results
        path: Path to the git repository

    Returns:
        Search results from git history
    """
    # Search in commit messages
    message_result = run_git_command(
        ["git", "log", "--grep", query, f"-{limit}", "--oneline", "--decorate"],
        cwd=path,
    )

    # Search in code changes
    code_result = run_git_command(
        ["git", "log", "-S", query, f"-{limit}", "--oneline", "--decorate"], cwd=path
    )

    output = []

    if message_result["success"] and message_result["stdout"].strip():
        output.append(f"Commits with '{query}' in message:")
        output.append(message_result["stdout"].strip())

    if code_result["success"] and code_result["stdout"].strip():
        if output:
            output.append("")  # Add spacing
        output.append(f"Commits that changed code containing '{query}':")
        output.append(code_result["stdout"].strip())

    if not output:
        return f"No results found for '{query}' in git history"

    return "\n".join(output)


@mcp.tool()
def git_show_commit(commit_hash: str, path: str = ".") -> str:
    """
    Show details of a specific commit

    Args:
        commit_hash: Hash of the commit to show
        path: Path to the git repository

    Returns:
        Commit details including diff
    """
    command = ["git", "show", commit_hash]
    result = run_git_command(command, cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    return result["stdout"]


@mcp.tool()
def git_reset_file(file_path: str, path: str = ".") -> str:
    """
    Reset a file to its last committed state

    Args:
        file_path: Path to the file to reset
        path: Path to the git repository

    Returns:
        Success or error message
    """
    command = ["git", "checkout", "HEAD", "--", file_path]
    result = run_git_command(command, cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    return f"Successfully reset {file_path} to last committed state"


@mcp.tool()
def git_stash(message: Optional[str] = None, path: str = ".") -> str:
    """
    Stash current changes

    Args:
        message: Optional stash message
        path: Path to the git repository

    Returns:
        Success or error message
    """
    command = ["git", "stash"]

    if message:
        command.extend(["push", "-m", message])

    result = run_git_command(command, cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    return f"Successfully stashed changes: {result['stdout'].strip()}"


@mcp.tool()
def git_stash_list(path: str = ".") -> str:
    """
    List all stashes

    Args:
        path: Path to the git repository

    Returns:
        List of stashes
    """
    result = run_git_command(["git", "stash", "list"], cwd=path)

    if not result["success"]:
        return f"Error: {result.get('error', result.get('stderr', 'Unknown error'))}"

    if not result["stdout"].strip():
        return "No stashes found"

    return result["stdout"].strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Git operations MCP server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Run the server
    mcp.run()
