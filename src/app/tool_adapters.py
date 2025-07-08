"""
Unified Tool Adapter System

Provides a consistent interface for different tool types (MCP, Langchain, etc.)
to eliminate type confusion and enable extensible tool handling.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Protocol
from mcp.types import Tool as MCPTool


class UnifiedTool(Protocol):
    """Unified interface for all tool types."""
    
    name: str
    description: str
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get tool parameter schema."""
        ...
    
    def get_server_type(self) -> str:
        """Get the server type for this tool."""
        ...
    
    def get_server_id(self) -> str:
        """Get the server ID for this tool."""
        ...


class MCPToolAdapter:
    """Adapter for MCP tools to unified interface."""
    
    def __init__(self, mcp_tool: MCPTool, server_id: str, server_type: str):
        self._mcp_tool = mcp_tool
        self.name = mcp_tool.name
        self.description = mcp_tool.description or f"Tool {mcp_tool.name} from {server_type} server"
        self._server_id = server_id
        self._server_type = server_type
    
    def get_parameters(self) -> Dict[str, Any]:
        """Extract parameters from MCP tool's inputSchema."""
        try:
            # MCP tools use 'inputSchema' not 'args_schema'
            if hasattr(self._mcp_tool, 'inputSchema') and self._mcp_tool.inputSchema:
                schema = self._mcp_tool.inputSchema
                if isinstance(schema, dict):
                    return schema
                elif hasattr(schema, 'model_json_schema'):
                    return schema.model_json_schema()
                elif hasattr(schema, 'schema'):
                    return schema.schema()
            return {}
        except Exception:
            # Fallback to empty schema if extraction fails
            return {}
    
    def get_server_type(self) -> str:
        return self._server_type
    
    def get_server_id(self) -> str:
        return self._server_id


class LangchainToolAdapter:
    """Adapter for Langchain tools to unified interface."""
    
    def __init__(self, lc_tool: Any, server_id: str = "langchain", server_type: str = "langchain"):
        self._lc_tool = lc_tool
        self.name = lc_tool.name
        self.description = lc_tool.description or f"Tool {lc_tool.name} from {server_type} server"
        self._server_id = server_id
        self._server_type = server_type
    
    def get_parameters(self) -> Dict[str, Any]:
        """Extract parameters from Langchain tool's args_schema."""
        try:
            # Langchain tools use 'args_schema'
            if hasattr(self._lc_tool, 'args_schema') and self._lc_tool.args_schema:
                schema = self._lc_tool.args_schema
                if isinstance(schema, dict):
                    return schema
                elif hasattr(schema, 'model_json_schema'):
                    return schema.model_json_schema()
                elif hasattr(schema, 'schema'):
                    return schema.schema()
            return {}
        except Exception:
            # Fallback to empty schema if extraction fails
            return {}
    
    def get_server_type(self) -> str:
        return self._server_type
    
    def get_server_id(self) -> str:
        return self._server_id


class ToolAdapterFactory:
    """Factory to create appropriate tool adapters."""
    
    @staticmethod
    def create_adapter(tool: Any, server_id: str, server_type: str) -> UnifiedTool:
        """
        Create appropriate adapter for the given tool type.
        
        Args:
            tool: The tool object (MCP Tool, Langchain tool, etc.)
            server_id: ID of the server providing this tool
            server_type: Type of the server (filesystem, git, langchain, etc.)
            
        Returns:
            UnifiedTool adapter for the tool
            
        Raises:
            ValueError: If tool type is not supported
        """
        # Check if it's an MCP tool
        if isinstance(tool, MCPTool):
            return MCPToolAdapter(tool, server_id, server_type)
        
        # Check if it's a Langchain-style tool (has args_schema attribute)
        elif hasattr(tool, 'args_schema'):
            return LangchainToolAdapter(tool, server_id, server_type)
        
        # Add support for other tool types here as needed
        # elif isinstance(tool, OpenAIFunction):
        #     return OpenAIToolAdapter(tool, server_id, server_type)
        
        else:
            raise ValueError(f"Unsupported tool type: {type(tool)}. Tool must be MCP Tool or have 'args_schema' attribute.")


class ToolAdapterError(Exception):
    """Base exception for tool adapter errors."""
    pass


class UnsupportedToolTypeError(ToolAdapterError):
    """Raised when attempting to create adapter for unsupported tool type."""
    pass