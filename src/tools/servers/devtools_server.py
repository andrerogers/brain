#!/usr/bin/env python3
"""
Local MCP Server for development tools and task automation
Provides test running, command execution, linting, and other development utilities
"""

import os
import sys
import asyncio
import argparse
import json
import subprocess
import tempfile
import shlex
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("devtools")

# Safe command patterns (whitelist approach for security)
SAFE_COMMANDS = {
    "npm": ["npm", "npx"],
    "python": ["python", "python3", "pip", "pip3", "pytest", "black", "isort", "mypy", "ruff"],
    "node": ["node", "npm", "npx", "yarn", "pnpm"],
    "git": ["git"],
    "docker": ["docker", "docker-compose"],
    "make": ["make"],
    "cargo": ["cargo"],
    "go": ["go"],
    "mvn": ["mvn", "gradle"],
    "test_runners": ["pytest", "jest", "mocha", "phpunit", "cargo test", "go test"],
    "linters": ["eslint", "pylint", "flake8", "black", "prettier", "rustfmt"],
    "formatters": ["black", "isort", "prettier", "rustfmt", "gofmt"],
    "shell_utils": ["echo", "ls", "pwd", "cat", "head", "tail", "wc", "grep", "find", "which", "whoami", "date", "uname"],
    "file_utils": ["mkdir", "rmdir", "touch", "cp", "mv", "chmod", "stat", "file", "basename", "dirname"],
    "system_info": ["ps", "top", "df", "du", "free", "uptime", "env", "printenv"],
    "text_processing": ["sort", "uniq", "cut", "awk", "sed", "tr", "diff"],
    "archive_utils": ["tar", "gzip", "gunzip", "zip", "unzip"]
}

def is_command_safe(command: str) -> bool:
    """Check if a command is in the safe list"""
    cmd_parts = shlex.split(command)
    if not cmd_parts:
        return False
    
    base_cmd = cmd_parts[0]
    
    # Check against safe command patterns
    for category, commands in SAFE_COMMANDS.items():
        if base_cmd in commands:
            return True
    
    return False

def run_command(command: str, cwd: str = None, timeout: int = 60) -> Dict[str, Any]:
    """
    Run a command safely with timeout
    
    Args:
        command: Command to run
        cwd: Working directory
        timeout: Timeout in seconds
    
    Returns:
        Dictionary with command result
    """
    try:
        if not is_command_safe(command):
            return {
                "success": False,
                "error": f"Command not allowed for security reasons: {command}",
                "stdout": "",
                "stderr": ""
            }
        
        if cwd is None:
            cwd = os.getcwd()
        
        # Parse command
        cmd_parts = shlex.split(command)
        
        # Run the command
        result = subprocess.run(
            cmd_parts,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command
        }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "stdout": "",
            "stderr": "",
            "command": command
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "command": command
        }

@mcp.tool()
def run_tests(pattern: Optional[str] = None, file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Run tests for the project
    
    Args:
        pattern: Test pattern to match (optional)
        file_path: Specific test file to run (optional)
        path: Project root path
    
    Returns:
        Test execution results
    """
    abs_path = os.path.abspath(path)
    
    # Detect test framework and build command
    test_commands = []
    
    # Check for package.json (Node.js)
    package_json = os.path.join(abs_path, "package.json")
    if os.path.exists(package_json):
        try:
            with open(package_json, 'r') as f:
                package_data = json.load(f)
                scripts = package_data.get("scripts", {})
                
                if "test" in scripts:
                    cmd = "npm test"
                    if pattern:
                        cmd += f" -- --grep \"{pattern}\""
                    elif file_path:
                        cmd += f" {file_path}"
                    test_commands.append(cmd)
                
                # Check for Jest
                deps = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                if "jest" in deps:
                    cmd = "npx jest"
                    if pattern:
                        cmd += f" --testNamePattern=\"{pattern}\""
                    elif file_path:
                        cmd += f" {file_path}"
                    test_commands.append(cmd)
        except:
            pass
    
    # Check for Python tests
    if os.path.exists(os.path.join(abs_path, "requirements.txt")) or \
       os.path.exists(os.path.join(abs_path, "pyproject.toml")) or \
       any(f.endswith(".py") for f in os.listdir(abs_path)):
        
        # Try pytest first
        cmd = "pytest"
        if pattern:
            cmd += f" -k \"{pattern}\""
        elif file_path:
            cmd += f" {file_path}"
        test_commands.append(cmd)
        
        # Fallback to unittest
        if file_path and file_path.endswith(".py"):
            module_name = file_path.replace("/", ".").replace("\\", ".").replace(".py", "")
            test_commands.append(f"python -m unittest {module_name}")
    
    # Check for Rust
    if os.path.exists(os.path.join(abs_path, "Cargo.toml")):
        cmd = "cargo test"
        if pattern:
            cmd += f" {pattern}"
        test_commands.append(cmd)
    
    # Check for Go
    if os.path.exists(os.path.join(abs_path, "go.mod")):
        cmd = "go test ./..."
        if pattern:
            cmd += f" -run {pattern}"
        test_commands.append(cmd)
    
    if not test_commands:
        return "No test framework detected in this project"
    
    # Run the first available test command
    for cmd in test_commands:
        result = run_command(cmd, cwd=abs_path, timeout=120)
        
        if result["success"]:
            output = [f"✅ Tests passed using: {cmd}"]
            if result["stdout"]:
                output.append("\nOutput:")
                output.append(result["stdout"])
            return "\n".join(output)
        else:
            # If command exists but failed, show the error
            if "not found" not in result.get("error", "") and "command not found" not in result.get("stderr", ""):
                output = [f"❌ Tests failed using: {cmd}"]
                if result["stderr"]:
                    output.append("\nErrors:")
                    output.append(result["stderr"])
                if result["stdout"]:
                    output.append("\nOutput:")
                    output.append(result["stdout"])
                return "\n".join(output)
    
    return "Could not run tests - no working test framework found"

@mcp.tool()
def run_command_safe(command: str, path: str = ".", timeout: int = 60) -> str:
    """
    Run a safe command in the project directory
    
    Args:
        command: Command to execute
        path: Working directory
        timeout: Command timeout in seconds
    
    Returns:
        Command execution results
    """
    abs_path = os.path.abspath(path)
    result = run_command(command, cwd=abs_path, timeout=timeout)
    
    if not result["success"]:
        error_msg = result.get("error", result.get("stderr", "Unknown error"))
        return f"❌ Command failed: {command}\nError: {error_msg}"
    
    output = [f"✅ Command executed: {command}"]
    
    if result["stdout"]:
        output.append("\nOutput:")
        output.append(result["stdout"])
    
    if result["stderr"]:
        output.append("\nWarnings/Info:")
        output.append(result["stderr"])
    
    return "\n".join(output)

@mcp.tool()
def lint_code(file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Run code linting on the project or specific file
    
    Args:
        file_path: Specific file to lint (optional)
        path: Project root path
    
    Returns:
        Linting results
    """
    abs_path = os.path.abspath(path)
    lint_commands = []
    
    # Detect project type and available linters
    
    # JavaScript/TypeScript
    if os.path.exists(os.path.join(abs_path, "package.json")):
        # Check for ESLint
        eslint_config = any(os.path.exists(os.path.join(abs_path, f)) 
                           for f in [".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", "eslint.config.js"])
        if eslint_config:
            cmd = "npx eslint"
            if file_path:
                cmd += f" {file_path}"
            else:
                cmd += " ."
            lint_commands.append(cmd)
    
    # Python
    python_files = any(f.endswith(".py") for f in os.listdir(abs_path))
    if python_files:
        # Try different Python linters
        for linter in ["ruff", "flake8", "pylint"]:
            cmd = linter
            if file_path:
                cmd += f" {file_path}"
            else:
                cmd += " ."
            lint_commands.append(cmd)
    
    # Rust
    if os.path.exists(os.path.join(abs_path, "Cargo.toml")):
        lint_commands.append("cargo clippy")
    
    # Go
    if os.path.exists(os.path.join(abs_path, "go.mod")):
        lint_commands.append("go vet ./...")
        lint_commands.append("golint ./...")
    
    if not lint_commands:
        return "No linters detected for this project type"
    
    results = []
    
    for cmd in lint_commands:
        result = run_command(cmd, cwd=abs_path, timeout=60)
        
        if result["success"]:
            if result["stdout"].strip():
                results.append(f"✅ {cmd}:\n{result['stdout']}")
            else:
                results.append(f"✅ {cmd}: No issues found")
        else:
            # Check if command exists
            if "not found" in result.get("error", "") or "command not found" in result.get("stderr", ""):
                continue  # Skip unavailable linters
            
            results.append(f"❌ {cmd}:\n{result.get('stderr', result.get('error', 'Unknown error'))}")
    
    if not results:
        return "No working linters found"
    
    return "\n\n".join(results)

@mcp.tool()
def format_code(file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Format code in the project or specific file
    
    Args:
        file_path: Specific file to format (optional)
        path: Project root path
    
    Returns:
        Formatting results
    """
    abs_path = os.path.abspath(path)
    format_commands = []
    
    # Detect project type and available formatters
    
    # JavaScript/TypeScript
    if os.path.exists(os.path.join(abs_path, "package.json")):
        prettier_config = any(os.path.exists(os.path.join(abs_path, f)) 
                             for f in [".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js"])
        if prettier_config:
            cmd = "npx prettier --write"
            if file_path:
                cmd += f" {file_path}"
            else:
                cmd += " ."
            format_commands.append(cmd)
    
    # Python
    python_files = any(f.endswith(".py") for f in os.listdir(abs_path))
    if python_files:
        # Black formatter
        cmd = "black"
        if file_path:
            cmd += f" {file_path}"
        else:
            cmd += " ."
        format_commands.append(cmd)
        
        # isort for imports
        cmd = "isort"
        if file_path:
            cmd += f" {file_path}"
        else:
            cmd += " ."
        format_commands.append(cmd)
    
    # Rust
    if os.path.exists(os.path.join(abs_path, "Cargo.toml")):
        format_commands.append("cargo fmt")
    
    # Go
    if os.path.exists(os.path.join(abs_path, "go.mod")):
        if file_path:
            format_commands.append(f"gofmt -w {file_path}")
        else:
            format_commands.append("gofmt -w .")
    
    if not format_commands:
        return "No formatters detected for this project type"
    
    results = []
    
    for cmd in format_commands:
        result = run_command(cmd, cwd=abs_path, timeout=60)
        
        if result["success"]:
            results.append(f"✅ {cmd}: Formatting completed")
            if result["stdout"]:
                results.append(result["stdout"])
        else:
            # Check if command exists
            if "not found" in result.get("error", "") or "command not found" in result.get("stderr", ""):
                continue  # Skip unavailable formatters
            
            results.append(f"❌ {cmd}: {result.get('stderr', result.get('error', 'Unknown error'))}")
    
    if not results:
        return "No working formatters found"
    
    return "\n".join(results)

@mcp.tool()
def check_types(file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Run type checking on the project or specific file
    
    Args:
        file_path: Specific file to type check (optional)
        path: Project root path
    
    Returns:
        Type checking results
    """
    abs_path = os.path.abspath(path)
    type_commands = []
    
    # TypeScript
    if os.path.exists(os.path.join(abs_path, "tsconfig.json")):
        cmd = "npx tsc --noEmit"
        if file_path:
            cmd += f" {file_path}"
        type_commands.append(cmd)
    
    # Python with mypy
    python_files = any(f.endswith(".py") for f in os.listdir(abs_path))
    if python_files:
        cmd = "mypy"
        if file_path:
            cmd += f" {file_path}"
        else:
            cmd += " ."
        type_commands.append(cmd)
    
    if not type_commands:
        return "No type checkers detected for this project"
    
    results = []
    
    for cmd in type_commands:
        result = run_command(cmd, cwd=abs_path, timeout=120)
        
        if result["success"]:
            results.append(f"✅ {cmd}: No type errors found")
            if result["stdout"]:
                results.append(result["stdout"])
        else:
            # Check if command exists
            if "not found" in result.get("error", "") or "command not found" in result.get("stderr", ""):
                continue  # Skip unavailable type checkers
            
            results.append(f"❌ {cmd}: Type errors found")
            if result["stderr"]:
                results.append(result["stderr"])
            if result["stdout"]:
                results.append(result["stdout"])
    
    if not results:
        return "No working type checkers found"
    
    return "\n\n".join(results)

@mcp.tool()
def install_dependencies(path: str = ".") -> str:
    """
    Install project dependencies
    
    Args:
        path: Project root path
    
    Returns:
        Installation results
    """
    abs_path = os.path.abspath(path)
    
    # Node.js
    if os.path.exists(os.path.join(abs_path, "package.json")):
        # Try different package managers
        for pm in ["npm install", "yarn install", "pnpm install"]:
            result = run_command(pm, cwd=abs_path, timeout=300)
            if result["success"]:
                return f"✅ Dependencies installed using {pm.split()[0]}"
            elif "not found" not in result.get("error", ""):
                return f"❌ Failed to install dependencies: {result.get('stderr', result.get('error'))}"
    
    # Python
    if os.path.exists(os.path.join(abs_path, "requirements.txt")):
        result = run_command("pip install -r requirements.txt", cwd=abs_path, timeout=300)
        if result["success"]:
            return "✅ Python dependencies installed"
        else:
            return f"❌ Failed to install Python dependencies: {result.get('stderr', result.get('error'))}"
    
    if os.path.exists(os.path.join(abs_path, "pyproject.toml")):
        result = run_command("pip install -e .", cwd=abs_path, timeout=300)
        if result["success"]:
            return "✅ Python project installed in development mode"
        else:
            return f"❌ Failed to install Python project: {result.get('stderr', result.get('error'))}"
    
    # Rust
    if os.path.exists(os.path.join(abs_path, "Cargo.toml")):
        result = run_command("cargo build", cwd=abs_path, timeout=300)
        if result["success"]:
            return "✅ Rust dependencies built"
        else:
            return f"❌ Failed to build Rust dependencies: {result.get('stderr', result.get('error'))}"
    
    # Go
    if os.path.exists(os.path.join(abs_path, "go.mod")):
        result = run_command("go mod download", cwd=abs_path, timeout=300)
        if result["success"]:
            return "✅ Go dependencies downloaded"
        else:
            return f"❌ Failed to download Go dependencies: {result.get('stderr', result.get('error'))}"
    
    return "No recognized dependency files found (package.json, requirements.txt, Cargo.toml, go.mod)"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Development tools MCP server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Run the server
    mcp.run()