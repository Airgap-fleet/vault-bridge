"""Auto-configure CLI for vault-bridge — one-command setup like natestrong."""

import json
import sys
from pathlib import Path
from typing import Any, TypedDict

import click

from .logging import get_logger

logger = get_logger(__name__)


class ClientConfig(TypedDict):
    config_path: Path
    server_key: str
    template: dict[str, Any]


CLIENT_CONFIGS: dict[str, ClientConfig] = {
    "claude_desktop": {
        "config_path": Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        "server_key": "vault-bridge",
        "template": {
            "mcpServers": {
                "vault-bridge": {
                    "command": "uvx",
                    "args": ["vault-bridge", "{vault_path}"],
                }
            }
        },
    },
    "cursor": {
        "config_path": Path.home() / ".cursor" / "mcp.json",
        "server_key": "vault-bridge",
        "template": {
            "mcpServers": {
                "vault-bridge": {
                    "command": "uvx",
                    "args": ["vault-bridge", "{vault_path}"],
                }
            }
        },
    },
    "windsurf": {
        "config_path": Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
        "server_key": "vault-bridge",
        "template": {
            "mcpServers": {
                "vault-bridge": {
                    "command": "uvx",
                    "args": ["vault-bridge", "{vault_path}"],
                }
            }
        },
    },
}


def load_existing_config(config_path: Path) -> dict[str, Any]:
    """Load existing JSON config or return empty."""
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(config_path: Path, config: dict[str, Any]) -> None:
    """Save JSON config with pretty formatting."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def update_config_for_client(config: dict[str, Any], server_key: str, vault_path: str) -> dict[str, Any]:
    """Update config with vault-bridge server entry."""
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][server_key] = {
        "command": "uvx",
        "args": ["vault-bridge", vault_path],
    }
    return config


@click.command()
@click.option(
    "--vault-path",
    "-v",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the Obsidian vault root directory.",
)
@click.option(
    "--client",
    "-c",
    type=click.Choice(list(CLIENT_CONFIGS.keys())),
    default="claude_desktop",
    help="Target client to configure.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing vault-bridge configuration.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without writing.",
)
def main(vault_path: Path, client: str, force: bool, dry_run: bool) -> int:
    """Auto-configure vault-bridge for your AI client.
    
    Example:
        vault-bridge-configure -v "/path/to/vault" -c claude_desktop
    """
    vault_path = vault_path.resolve()

    # Validate vault
    if not (vault_path / ".obsidian").exists() and not any(vault_path.glob("*.md")):
        logger.warning("configure.not_vault", path=str(vault_path))
        click.echo(f"Warning: {vault_path} doesn't appear to be an Obsidian vault (.obsidian folder missing, no .md files)", err=True)
        if not force:
            return 1

    client_config = CLIENT_CONFIGS[client]
    config_path = client_config["config_path"]
    server_key = client_config["server_key"]

    logger.info("configure.start", vault_path=str(vault_path), client=client)

    # Load existing config
    existing: dict[str, Any] = load_existing_config(config_path)

    # Check for existing entry
    if server_key in existing.get("mcpServers", {}) and not force:
        logger.warning("configure.exists", config_path=str(config_path))
        click.echo(f"vault-bridge already configured in {config_path}. Use --force to overwrite.", err=True)
        return 1

    # Update config
    updated: dict[str, Any] = update_config_for_client(existing, server_key, str(vault_path))

    if dry_run:
        click.echo(f"Would update {config_path}:")
        click.echo(json.dumps(updated, indent=2))
        return 0

    # Save
    save_config(config_path, updated)

    logger.info("configure.success", config_path=str(config_path))
    click.echo(f"✓ Configured vault-bridge for {client}")
    click.echo(f"  Config: {config_path}")
    click.echo(f"  Vault:  {vault_path}")
    click.echo(f"  Restart {client} to apply changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
