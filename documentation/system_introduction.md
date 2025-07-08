# System Capabilities and Available Tools

This document provides an overview of the system's capabilities and the tools available for use.

## Overview

The system provides a comprehensive set of tools for software development, code analysis, file management, version control, and web research. These tools are organized into different servers based on their functionality.

## Available Servers and Tools

### Filesystem Server
Tools for file and directory operations.

- **read_file**: Read contents of a file
  - Required parameters: `path`
  - Optional parameters: `start_line`, `end_line`
  - Example: `read_file(path="./src/main.py")`

- **write_file**: Write content to a file
  - Required parameters: `path`, `content`
  - Optional parameters: `create_dirs`
  - Example: `write_file(path="./notes.txt", content="Important information")`

- **edit_file**: Edit a file by replacing text
  - Required parameters: `path`, `old_content`, `new_content`
  - Example: `edit_file(path="./config.json", old_content="version: 1.0", new_content="version: 1.1")`

- **list_directory**: List contents of a directory
  - Required parameters: `path`
  - Optional parameters: `show_hidden`, `recursive`
  - Example: `list_directory(path="./src", recursive=true)`

- **search_files**: Search for text patterns in files
  - Required parameters: `pattern`, `directory`
  - Optional parameters: `file_pattern`, `max_results`
  - Example: `search_files(pattern="TODO", directory="./src", file_pattern="*.py")`

- **get_file_info**: Get information about a file or directory
  - Required parameters: `path`
  - Example: `get_file_info(path="./data.csv")`

- **create_directory**: Create a directory
  - Required parameters: `path`
  - Optional parameters: `parents`
  - Example: `create_directory(path="./output/logs", parents=true)`

- **delete_file**: Delete a file
  - Required parameters: `path`
  - Example: `delete_file(path="./temp.txt")`

### Git Server
Tools for version control operations.

- **git_status**: Get git repository status
  - Required parameters: `path`
  - Example: `git_status(path="./project")`

- **git_diff**: Show changes between commits, commit and working tree, etc.
  - Required parameters: `path`
  - Optional parameters: `file_path`, `staged`
  - Example: `git_diff(path="./project", file_path="src/main.js")`

- **git_log**: Show commit history
  - Required parameters: `path`
  - Optional parameters: `limit`, `file_path`
  - Example: `git_log(path="./project", limit=5)`

- **git_add**: Stage files for commit
  - Required parameters: `file_paths`, `path`
  - Example: `git_add(file_paths="./src/updated_file.py", path="./project")`

- **git_commit**: Create a git commit
  - Required parameters: `message`, `path`
  - Example: `git_commit(message="Fix login bug", path="./project")`

- **git_branch_info**: Get current branch and remote information
  - Required parameters: `path`
  - Example: `git_branch_info(path="./project")`

- **git_search_history**: Search git commit history
  - Required parameters: `query`, `path`
  - Optional parameters: `limit`
  - Example: `git_search_history(query="authentication", path="./project", limit=10)`

- **git_show_commit**: Show details of a specific commit
  - Required parameters: `commit_hash`, `path`
  - Example: `git_show_commit(commit_hash="abc123", path="./project")`

- **git_reset_file**: Reset a file to its last committed state
  - Required parameters: `file_path`, `path`
  - Example: `git_reset_file(file_path="./src/broken.js", path="./project")`

- **git_stash**: Stash current changes
  - Required parameters: `path`
  - Optional parameters: `message`
  - Example: `git_stash(path="./project", message="Save changes before pull")`

- **git_stash_list**: List all stashes
  - Required parameters: `path`
  - Example: `git_stash_list(path="./project")`

### Codebase Server
Tools for code analysis and project structure understanding.

- **analyze_project**: Analyze project structure and detect technologies
  - Required parameters: `path`
  - Example: `analyze_project(path="./project")`

- **get_project_structure**: Get hierarchical project structure
  - Required parameters: `path`
  - Optional parameters: `max_depth`
  - Example: `get_project_structure(path="./project", max_depth=3)`

- **find_definition**: Find definition of a symbol
  - Required parameters: `symbol`, `path`
  - Optional parameters: `file_path`
  - Example: `find_definition(symbol="UserAuthenticator", path="./project")`

- **find_references**: Find all references to a symbol
  - Required parameters: `symbol`, `path`
  - Optional parameters: `file_path`
  - Example: `find_references(symbol="authenticate", path="./project")`

- **explain_codebase**: Generate high-level explanation of codebase architecture
  - Required parameters: `path`
  - Example: `explain_codebase(path="./project")`

- **get_project_context**: Get essential project context for AI assistance
  - Required parameters: `path`
  - Example: `get_project_context(path="./project")`

### DevTools Server
Tools for development workflows, testing, and code quality.

- **run_tests**: Run tests for the project
  - Required parameters: `path`
  - Optional parameters: `pattern`, `file_path`
  - Example: `run_tests(path="./project", pattern="test_auth*")`

- **run_command_safe**: Run a safe command in the project directory
  - Required parameters: `command`, `path`
  - Optional parameters: `timeout`
  - Example: `run_command_safe(command="npm list", path="./project")`

- **lint_code**: Run code linting
  - Required parameters: `path`
  - Optional parameters: `file_path`
  - Example: `lint_code(path="./project", file_path="src/component.js")`

- **format_code**: Format code
  - Required parameters: `path`
  - Optional parameters: `file_path`
  - Example: `format_code(path="./project", file_path="src/messy.py")`

- **check_types**: Run type checking
  - Required parameters: `path`
  - Optional parameters: `file_path`
  - Example: `check_types(path="./project")`

- **install_dependencies**: Install project dependencies
  - Required parameters: `path`
  - Example: `install_dependencies(path="./project")`

### Exa Server
Tools for web search and content retrieval.

- **web_search_exa**: Search the web using Exa AI
  - Required parameters: `query`
  - Optional parameters: `num_results`
  - Example: `web_search_exa(query="latest JavaScript frameworks 2023", num_results=5)`

- **crawl_url**: Fetch and extract main content from a specific URL
  - Required parameters: `url`
  - Example: `crawl_url(url="https://docs.python.org/3/tutorial/index.html")`

### Library Documentation
Tools for accessing library documentation.

- **resolve-library-id**: Resolves a package/product name to a Context7-compatible library ID
  - Required parameters: `libraryName`
  - Example: `resolve-library-id(libraryName="react")`

- **get-library-docs**: Fetches documentation for a library
  - Required parameters: `context7CompatibleLibraryID`
  - Optional parameters: `topic`, `tokens`
  - Example: `get-library-docs(context7CompatibleLibraryID="/facebook/react", topic="hooks")`

## Using Tools Effectively

1. **Select the appropriate server** based on the type of operation you need to perform
2. **Choose the specific tool** that matches your requirement
3. **Provide all required parameters** when calling the tool
4. **Chain tools together** for complex operations, using output from one tool as input to another

## Best Practices

- Use filesystem tools for file operations rather than commands when possible
- Use git tools for version control operations for better error handling
- Use codebase analysis tools to understand unfamiliar projects
- Use web search for up-to-date information
- Combine multiple tools to create comprehensive workflows

## Examples of Combined Workflows

### Code Improvement Workflow
```
1. analyze_project to understand the codebase
2. lint_code to identify issues
3. find_references to locate usage of problematic code
4. edit_file to fix issues
5. run_tests to verify changes
6. git_add and git_commit to save changes
```

### Research and Implementation Workflow
```
1. web_search_exa to find relevant information
2. resolve-library-id and get-library-docs to access library documentation
3. write_file to create implementation
4. run_tests to verify functionality
```
