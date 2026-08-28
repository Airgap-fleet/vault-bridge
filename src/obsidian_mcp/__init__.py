"""Obsidian MCP Server package."""

from .core import ObsidianCore
from .models import ObsidianConfig
from .server import create_mcp_server

__all__ = ["ObsidianConfig", "ObsidianCore", "create_mcp_server"]
__version__ = "1.0.0"