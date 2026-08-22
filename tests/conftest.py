"""Pytest configuration and fixtures for Obsidian MCP tests."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from obsidian_mcp.models import ObsidianConfig


@pytest.fixture
def temp_vault():
    """Create a temporary vault directory with sample notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        
        # Create sample notes
        (vault / "note1.md").write_text("---\ntitle: Test Note 1\ntags: [test, example]\n---\n\n# Test Note 1\n\nThis is a test note.", encoding="utf-8")
        
        (vault / "note2.md").write_text("---\ntitle: Test Note 2\ntags: [test]\nstatus: draft\n---\n\n# Test Note 2\n\nAnother test note with different frontmatter.", encoding="utf-8")
        
        (vault / "no-frontmatter.md").write_text("# No Frontmatter\n\nThis note has no YAML frontmatter.", encoding="utf-8")
        
        # Create subdirectory
        subdir = vault / "subdir"
        subdir.mkdir()
        (subdir / "note3.md").write_text("---\ntitle: Sub Note\ncategory: nested\n---\n\n# Sub Note\n\nNested note.", encoding="utf-8")
        
        # Create daily notes folder
        daily = vault / "Daily Notes"
        daily.mkdir()
        (daily / "2026-01-15.md").write_text("---\ndate: 2026-01-15\n---\n\n# Daily Note\n\nToday I did things.", encoding="utf-8")
        
        yield vault


@pytest.fixture
def config(temp_vault):
    """Create ObsidianConfig pointing to temp vault."""
    return ObsidianConfig(vault_path=temp_vault)


@pytest.fixture
def core(config):
    """Create ObsidianCore instance with test config."""
    from obsidian_mcp.core import ObsidianCore
    return ObsidianCore(config)