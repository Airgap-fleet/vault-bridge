"""Obsidian MCP Server package."""

from .models import ObsidianConfig
from .core import ObsidianCore
from .server import create_mcp_server

__all__ = ["create_mcp_server", "ObsidianConfig", "ObsidianCore"]
__version__ = "1.0.0"