#!/usr/bin/env python3
"""
Local MCP Server for codebase analysis and project understanding
Provides project structure analysis, technology detection, and architectural insights
"""

import os
import sys
import asyncio
import argparse
import json
import subprocess
from typing import Dict, List, Any, Optional, Union, Set
from pathlib import Path
import fnmatch

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("codebase")

# Common patterns for different file types and technologies
TECH_PATTERNS = {
    "javascript": ["*.js", "*.jsx", "*.mjs"],
    "typescript": ["*.ts", "*.tsx"],
    "python": ["*.py"],
    "java": ["*.java"],
    "csharp": ["*.cs"],
    "go": ["*.go"],
    "rust": ["*.rs"],
    "php": ["*.php"],
    "ruby": ["*.rb"],
    "swift": ["*.swift"],
    "kotlin": ["*.kt"],
    "scala": ["*.scala"],
    "css": ["*.css", "*.scss", "*.sass", "*.less"],
    "html": ["*.html", "*.htm"],
    "sql": ["*.sql"],
    "shell": ["*.sh", "*.bash", "*.zsh"],
    "dockerfile": ["Dockerfile*", "*.dockerfile"],
    "yaml": ["*.yml", "*.yaml"],
    "json": ["*.json"],
    "xml": ["*.xml"],
    "markdown": ["*.md", "*.markdown"]
}

CONFIG_FILES = {
    "package.json": "Node.js/JavaScript",
    "requirements.txt": "Python",
    "Pipfile": "Python (Pipenv)",
    "pyproject.toml": "Python (Modern)",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
    "Package.swift": "Swift",
    "mix.exs": "Elixir",
    "deno.json": "Deno",
    "tsconfig.json": "TypeScript",
    "webpack.config.js": "Webpack",
    "vite.config.js": "Vite",
    "rollup.config.js": "Rollup",
    "tailwind.config.js": "Tailwind CSS",
    "next.config.js": "Next.js",
    "nuxt.config.js": "Nuxt.js",
    "vue.config.js": "Vue.js",
    "angular.json": "Angular",
    "svelte.config.js": "Svelte",
    "docker-compose.yml": "Docker Compose",
    "Dockerfile": "Docker",
    ".gitignore": "Git",
    "README.md": "Documentation",
    "LICENSE": "License",
    "Makefile": "Make",
    "CMakeLists.txt": "CMake",
    "meson.build": "Meson"
}

def scan_directory(path: str, max_depth: int = 3) -> Dict[str, Any]:
    """Scan directory structure and collect file information"""
    structure = {
        "directories": [],
        "files": [],
        "tech_files": {},
        "config_files": {},
        "total_files": 0,
        "total_size": 0
    }
    
    try:
        for root, dirs, files in os.walk(path):
            # Calculate depth
            depth = root.replace(path, '').count(os.sep)
            if depth > max_depth:
                dirs.clear()  # Don't go deeper
                continue
            
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') 
                      and d not in ['node_modules', '__pycache__', 'target', 'build', 'dist']]
            
            # Add directory to structure
            rel_dir = os.path.relpath(root, path)
            if rel_dir != '.':
                structure["directories"].append(rel_dir)
            
            # Process files
            for file in files:
                if file.startswith('.') and file not in CONFIG_FILES:
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, path)
                
                try:
                    stat = os.stat(file_path)
                    structure["total_files"] += 1
                    structure["total_size"] += stat.st_size
                    
                    # Check for config files
                    if file in CONFIG_FILES:
                        structure["config_files"][rel_path] = CONFIG_FILES[file]
                    
                    # Check for technology files
                    for tech, patterns in TECH_PATTERNS.items():
                        if any(fnmatch.fnmatch(file, pattern) for pattern in patterns):
                            if tech not in structure["tech_files"]:
                                structure["tech_files"][tech] = []
                            structure["tech_files"][tech].append(rel_path)
                            break
                
                except (OSError, PermissionError):
                    continue
    
    except (OSError, PermissionError):
        pass
    
    return structure

@mcp.tool()
def analyze_project(path: str = ".") -> str:
    """
    Analyze project structure and detect technologies
    
    Args:
        path: Path to the project root
    
    Returns:
        Comprehensive project analysis
    """
    try:
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(abs_path):
            return f"Error: Path does not exist: {path}"
        
        if not os.path.isdir(abs_path):
            return f"Error: Path is not a directory: {path}"
        
        structure = scan_directory(abs_path)
        
        # Determine primary technologies
        primary_tech = []
        for tech, files in structure["tech_files"].items():
            if len(files) > 5 or tech in ["javascript", "typescript", "python", "java"]:
                primary_tech.append(f"{tech} ({len(files)} files)")
        
        # Determine project type
        project_type = "Unknown"
        if "package.json" in [os.path.basename(f) for f in structure["config_files"].keys()]:
            project_type = "Node.js/JavaScript Project"
        elif any("requirements.txt" in f or "pyproject.toml" in f for f in structure["config_files"].keys()):
            project_type = "Python Project"
        elif "Cargo.toml" in [os.path.basename(f) for f in structure["config_files"].keys()]:
            project_type = "Rust Project"
        elif "go.mod" in [os.path.basename(f) for f in structure["config_files"].keys()]:
            project_type = "Go Project"
        
        # Build analysis report
        analysis = [
            f"Project Analysis for: {abs_path}",
            "=" * 50,
            f"Project Type: {project_type}",
            f"Total Files: {structure['total_files']}",
            f"Total Size: {structure['total_size'] / 1024:.1f} KB",
            f"Directories: {len(structure['directories'])}",
            ""
        ]
        
        if primary_tech:
            analysis.extend([
                "Primary Technologies:",
                *[f"  • {tech}" for tech in primary_tech],
                ""
            ])
        
        if structure["config_files"]:
            analysis.extend([
                "Configuration Files:",
                *[f"  • {file}: {tech}" for file, tech in structure["config_files"].items()],
                ""
            ])
        
        # Directory structure (top level)
        top_dirs = [d for d in structure["directories"] if '/' not in d and '\\' not in d]
        if top_dirs:
            analysis.extend([
                "Top-level Directories:",
                *[f"  • {d}/" for d in sorted(top_dirs)],
                ""
            ])
        
        return "\n".join(analysis)
    
    except Exception as e:
        return f"Error analyzing project: {str(e)}"

@mcp.tool()
def get_project_structure(path: str = ".", max_depth: int = 2) -> str:
    """
    Get hierarchical project structure
    
    Args:
        path: Path to the project root
        max_depth: Maximum depth to traverse
    
    Returns:
        Tree-like project structure
    """
    try:
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(abs_path):
            return f"Error: Path does not exist: {path}"
        
        structure_lines = [f"Project Structure: {os.path.basename(abs_path)}/"]
        
        def build_tree(current_path: str, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return
            
            try:
                entries = sorted(os.listdir(current_path))
                # Filter out hidden files and common ignore patterns
                entries = [e for e in entries if not e.startswith('.') 
                          and e not in ['node_modules', '__pycache__', 'target', 'build', 'dist']]
                
                dirs = [e for e in entries if os.path.isdir(os.path.join(current_path, e))]
                files = [e for e in entries if os.path.isfile(os.path.join(current_path, e))]
                
                # Add directories first
                for i, dir_name in enumerate(dirs):
                    is_last_dir = i == len(dirs) - 1 and len(files) == 0
                    connector = "└── " if is_last_dir else "├── "
                    structure_lines.append(f"{prefix}{connector}{dir_name}/")
                    
                    next_prefix = prefix + ("    " if is_last_dir else "│   ")
                    build_tree(os.path.join(current_path, dir_name), next_prefix, depth + 1)
                
                # Add files
                for i, file_name in enumerate(files):
                    is_last = i == len(files) - 1
                    connector = "└── " if is_last else "├── "
                    structure_lines.append(f"{prefix}{connector}{file_name}")
            
            except (OSError, PermissionError):
                pass
        
        build_tree(abs_path)
        return "\n".join(structure_lines)
    
    except Exception as e:
        return f"Error getting project structure: {str(e)}"

@mcp.tool()
def find_definition(symbol: str, file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Find definition of a symbol (function, class, variable)
    
    Args:
        symbol: Symbol to search for
        file_path: Specific file to search in (optional)
        path: Project root path
    
    Returns:
        Locations where the symbol is defined
    """
    try:
        abs_path = os.path.abspath(path)
        results = []
        
        # Define patterns for different languages
        definition_patterns = [
            f"def {symbol}",           # Python function
            f"class {symbol}",         # Python/JS class
            f"function {symbol}",      # JavaScript function
            f"const {symbol}",         # JavaScript const
            f"let {symbol}",           # JavaScript let
            f"var {symbol}",           # JavaScript var
            f"interface {symbol}",     # TypeScript interface
            f"type {symbol}",          # TypeScript type
            f"enum {symbol}",          # TypeScript enum
            f"public class {symbol}",  # Java class
            f"struct {symbol}",        # Go/Rust struct
            f"fn {symbol}",            # Rust function
        ]
        
        search_paths = []
        if file_path:
            if os.path.exists(os.path.join(abs_path, file_path)):
                search_paths = [os.path.join(abs_path, file_path)]
        else:
            # Search in all relevant files
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') 
                          and d not in ['node_modules', '__pycache__', 'target', 'build', 'dist']]
                
                for file in files:
                    if any(file.endswith(ext) for ext in ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs']):
                        search_paths.append(os.path.join(root, file))
        
        for file_path in search_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    for pattern in definition_patterns:
                        if pattern in line:
                            rel_path = os.path.relpath(file_path, abs_path)
                            results.append(f"{rel_path}:{line_num}: {line.strip()}")
                            break
            
            except (UnicodeDecodeError, PermissionError):
                continue
        
        if not results:
            return f"No definitions found for symbol '{symbol}'"
        
        return f"Definitions for '{symbol}':\n" + "\n".join(results)
    
    except Exception as e:
        return f"Error finding definition: {str(e)}"

@mcp.tool()
def find_references(symbol: str, file_path: Optional[str] = None, path: str = ".") -> str:
    """
    Find all references to a symbol
    
    Args:
        symbol: Symbol to search for
        file_path: Specific file to search in (optional)
        path: Project root path
    
    Returns:
        Locations where the symbol is referenced
    """
    try:
        abs_path = os.path.abspath(path)
        results = []
        
        search_paths = []
        if file_path:
            if os.path.exists(os.path.join(abs_path, file_path)):
                search_paths = [os.path.join(abs_path, file_path)]
        else:
            # Search in all relevant files
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') 
                          and d not in ['node_modules', '__pycache__', 'target', 'build', 'dist']]
                
                for file in files:
                    if any(file.endswith(ext) for ext in ['.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs']):
                        search_paths.append(os.path.join(root, file))
        
        for file_path in search_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    if symbol in line:
                        rel_path = os.path.relpath(file_path, abs_path)
                        results.append(f"{rel_path}:{line_num}: {line.strip()}")
            
            except (UnicodeDecodeError, PermissionError):
                continue
        
        if not results:
            return f"No references found for symbol '{symbol}'"
        
        # Limit results to prevent overwhelming output
        if len(results) > 50:
            results = results[:50]
            results.append(f"... (showing first 50 of {len(results)} results)")
        
        return f"References for '{symbol}':\n" + "\n".join(results)
    
    except Exception as e:
        return f"Error finding references: {str(e)}"

@mcp.tool()
def explain_codebase(path: str = ".") -> str:
    """
    Generate a high-level explanation of the codebase architecture
    
    Args:
        path: Path to the project root
    
    Returns:
        Architectural explanation of the codebase
    """
    try:
        abs_path = os.path.abspath(path)
        structure = scan_directory(abs_path, max_depth=2)
        
        explanation = [
            f"Codebase Architecture Analysis: {os.path.basename(abs_path)}",
            "=" * 60
        ]
        
        # Project overview
        total_lines = 0
        for tech, files in structure["tech_files"].items():
            for file_path in files:
                try:
                    full_path = os.path.join(abs_path, file_path)
                    with open(full_path, 'r', encoding='utf-8') as f:
                        total_lines += sum(1 for _ in f)
                except:
                    continue
        
        explanation.extend([
            f"Scale: {structure['total_files']} files, ~{total_lines} lines of code",
            f"Size: {structure['total_size'] / 1024:.1f} KB",
            ""
        ])
        
        # Architecture patterns
        patterns = []
        if any("src" in d for d in structure["directories"]):
            patterns.append("Source code organized in src/ directory")
        if any("test" in d or "spec" in d for d in structure["directories"]):
            patterns.append("Dedicated testing directory structure")
        if any("lib" in d for d in structure["directories"]):
            patterns.append("Library code separation")
        if any("api" in d for d in structure["directories"]):
            patterns.append("API layer organization")
        if any("component" in d.lower() for d in structure["directories"]):
            patterns.append("Component-based architecture")
        
        if patterns:
            explanation.extend([
                "Architectural Patterns:",
                *[f"  • {pattern}" for pattern in patterns],
                ""
            ])
        
        # Technology stack
        tech_stack = []
        for tech, files in structure["tech_files"].items():
            if len(files) > 3:  # Only mention technologies with significant presence
                tech_stack.append(f"{tech.title()}: {len(files)} files")
        
        if tech_stack:
            explanation.extend([
                "Technology Stack:",
                *[f"  • {tech}" for tech in tech_stack],
                ""
            ])
        
        # Key directories and their purpose
        key_dirs = {}
        for dir_path in structure["directories"]:
            dir_name = dir_path.split(os.sep)[0] if os.sep in dir_path else dir_path
            
            if dir_name in ["src", "source"]:
                key_dirs[dir_name] = "Main source code"
            elif dir_name in ["test", "tests", "spec", "__tests__"]:
                key_dirs[dir_name] = "Test files"
            elif dir_name in ["lib", "library"]:
                key_dirs[dir_name] = "Library/utility code"
            elif dir_name in ["api", "routes"]:
                key_dirs[dir_name] = "API endpoints/routing"
            elif dir_name in ["components", "ui"]:
                key_dirs[dir_name] = "UI components"
            elif dir_name in ["utils", "utilities", "helpers"]:
                key_dirs[dir_name] = "Utility functions"
            elif dir_name in ["config", "configuration"]:
                key_dirs[dir_name] = "Configuration files"
            elif dir_name in ["docs", "documentation"]:
                key_dirs[dir_name] = "Documentation"
        
        if key_dirs:
            explanation.extend([
                "Directory Structure:",
                *[f"  • {dir_name}/: {purpose}" for dir_name, purpose in key_dirs.items()],
                ""
            ])
        
        return "\n".join(explanation)
    
    except Exception as e:
        return f"Error explaining codebase: {str(e)}"

@mcp.tool()
def get_project_context(path: str = ".") -> str:
    """
    Get essential project context for AI assistance
    
    Args:
        path: Path to the project root
    
    Returns:
        Concise project context for AI understanding
    """
    try:
        abs_path = os.path.abspath(path)
        structure = scan_directory(abs_path, max_depth=1)
        
        context = {
            "project_name": os.path.basename(abs_path),
            "project_type": "Unknown",
            "primary_language": "Unknown",
            "key_files": [],
            "main_directories": []
        }
        
        # Determine project type and language
        if "package.json" in [os.path.basename(f) for f in structure["config_files"].keys()]:
            context["project_type"] = "Node.js/JavaScript"
            if "typescript" in structure["tech_files"]:
                context["primary_language"] = "TypeScript"
            else:
                context["primary_language"] = "JavaScript"
        elif any(f.endswith(("requirements.txt", "pyproject.toml")) for f in structure["config_files"].keys()):
            context["project_type"] = "Python"
            context["primary_language"] = "Python"
        elif "Cargo.toml" in [os.path.basename(f) for f in structure["config_files"].keys()]:
            context["project_type"] = "Rust"
            context["primary_language"] = "Rust"
        
        # Key files
        important_files = ["README.md", "package.json", "requirements.txt", "Cargo.toml", "go.mod"]
        context["key_files"] = [f for f in structure["config_files"].keys() 
                              if any(important in f for important in important_files)]
        
        # Main directories (top-level only)
        context["main_directories"] = [d for d in structure["directories"] 
                                     if '/' not in d and '\\' not in d][:10]  # Limit to 10
        
        return json.dumps(context, indent=2)
    
    except Exception as e:
        return f"Error getting project context: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Codebase analysis MCP server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Run the server
    mcp.run()