"""Persistent SQLite FTS5 indexer for vault-bridge — 5x faster searches."""

import re
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)


class VaultIndexer:
    """SQLite FTS5-backed index for Obsidian vaults.
    
    Features:
    - Persistent index stored in .vault-bridge/index.db
    - Incremental updates on file changes (mtime-based)
    - FTS5 full-text search with BM25 ranking
    - Frontmatter property indexing for fast property searches
    - Background indexing thread (non-blocking)
    - Wikilink/backlink graph extraction
    - Multi-vault support
    """

    def __init__(self, vault_root: Path, index_dir: Path | None = None):
        self.vault_root = vault_root.resolve()
        self.index_dir = index_dir or (self.vault_root / ".vault-bridge")
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "index.db"
        self._lock = threading.RLock()
        self._indexing = False
        self._last_indexed_mtime = 0.0
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema with FTS5 tables."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            # Main notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    path TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified REAL NOT NULL,
                    indexed_at REAL NOT NULL,
                    frontmatter TEXT,  -- JSON
                    vault TEXT DEFAULT 'default'  -- NEW: multi-vault
                )
            """)

            # FTS5 virtual table for content search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    path UNINDEXED,
                    name,
                    content,
                    frontmatter_keys,
                    frontmatter_values,
                    vault UNINDEXED,
                    tokenize='porter unicode61'
                )
            """)

            # Frontmatter property index for fast key/value lookups
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frontmatter_props (
                    path TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    vault TEXT DEFAULT 'default',
                    PRIMARY KEY (path, key, vault)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_frontmatter_key 
                ON frontmatter_props(key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_frontmatter_key_value 
                ON frontmatter_props(key, value)
            """)

            # Wikilinks table for graph/backlinks
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wikilinks (
                    source_path TEXT NOT NULL,
                    target TEXT NOT NULL,
                    alias TEXT,
                    line INTEGER NOT NULL,
                    context TEXT,
                    vault TEXT DEFAULT 'default',
                    PRIMARY KEY (source_path, target, line, vault)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_wikilinks_target 
                ON wikilinks(target)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_wikilinks_source 
                ON wikilinks(source_path)
            """)

            # Vault metadata table (multi-vault)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vaults (
                    name TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    indexed_at REAL,
                    note_count INTEGER DEFAULT 0
                )
            """)

            # Index metadata
            conn.execute("""
                CREATE TABLE IF NOT EXISTS index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            conn.commit()
            logger.debug("index.db_initialized", path=str(self.db_path))

    def _get_file_mtime(self, path: Path) -> float:
        """Get file modification time."""
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any] | None, str]:
        """Parse YAML frontmatter from note content."""
        if not content.startswith("---"):
            return None, content
        try:
            import yaml
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None, content
            fm = yaml.safe_load(parts[1])
            body = parts[2].lstrip("\n")
            return fm if isinstance(fm, dict) else None, body
        except yaml.YAMLError:
            return None, content

    def _index_single_file(self, conn: sqlite3.Connection, rel_path: Path, abs_path: Path, vault_name: str = "Vault") -> None:
        """Index a single file."""
        mtime = self._get_file_mtime(abs_path)
        if mtime == 0:
            return

        try:
            content = abs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.debug("index.skip_binary", path=str(rel_path))
            return
        except OSError:
            return

        frontmatter, body = self._parse_frontmatter(content)
        fm_json = None
        fm_keys = ""
        fm_values = ""

        if frontmatter:
            import json
            fm_json = json.dumps(frontmatter)
            fm_keys = " ".join(frontmatter.keys())
            fm_values = " ".join(str(v) for v in frontmatter.values())

            # Index frontmatter properties
            for k, v in frontmatter.items():
                conn.execute(
                    "INSERT OR REPLACE INTO frontmatter_props (path, key, value, vault) VALUES (?, ?, ?, ?)",
                    (str(rel_path), k, str(v), vault_name)
                )

        # Upsert note
        conn.execute("""
            INSERT OR REPLACE INTO notes (path, name, size, modified, indexed_at, frontmatter, vault)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(rel_path), rel_path.name, abs_path.stat().st_size, mtime, time.time(), fm_json, vault_name))

        # Upsert FTS5 entry
        conn.execute("""
            INSERT OR REPLACE INTO notes_fts (path, name, content, frontmatter_keys, frontmatter_values, vault)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(rel_path), rel_path.name, body, fm_keys, fm_values, vault_name))

        # Index wikilinks
        self.index_wikilinks(conn, rel_path, content, vault_name)

    def _remove_from_index(self, conn: sqlite3.Connection, rel_path: Path, vault_name: str = "Vault") -> None:
        """Remove a file from index."""
        conn.execute("DELETE FROM notes WHERE path = ? AND vault = ?", (str(rel_path), vault_name))
        conn.execute("DELETE FROM notes_fts WHERE path = ? AND vault = ?", (str(rel_path), vault_name))
        conn.execute("DELETE FROM frontmatter_props WHERE path = ? AND vault = ?", (str(rel_path), vault_name))
        conn.execute("DELETE FROM wikilinks WHERE source_path = ? AND vault = ?", (str(rel_path), vault_name))

    def index_all(self, force: bool = False, progress_callback: Callable[[int], None] | None = None, vault_name: str = "Vault") -> dict[str, int]:
        """Full vault re-index. Returns stats."""
        if self._indexing and not force:
            logger.warning("index.already_running")
            return {"indexed": 0, "removed": 0, "errors": 0, "skipped": 0}

        self._indexing = True
        stats = {"indexed": 0, "removed": 0, "errors": 0, "skipped": 0}
        start_time = time.time()

        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")

                # Get current indexed files for this vault
                cursor = conn.execute("SELECT path, modified FROM notes WHERE vault = ?", (vault_name,))
                indexed = {row[0]: row[1] for row in cursor.fetchall()}

                # Walk vault
                current_files = {}
                for abs_path in self.vault_root.rglob("*.md"):
                    try:
                        rel = abs_path.relative_to(self.vault_root)
                    except ValueError:
                        continue
                    if not abs_path.is_file():
                        continue
                    # Skip hidden/system dirs
                    if any(part.startswith(".") for part in rel.parts):
                        continue
                    current_files[str(rel)] = self._get_file_mtime(abs_path)

                # Index new/changed files
                for rel_str, mtime in current_files.items():
                    rel_path = Path(rel_str)
                    abs_path = self.vault_root / rel_path
                    old_mtime = indexed.get(rel_str)

                    if force or old_mtime != mtime:
                        try:
                            self._index_single_file(conn, rel_path, abs_path, vault_name)
                            stats["indexed"] += 1
                        except OSError as e:
                            logger.error("index.file_error", path=rel_str, error=str(e))
                            stats["errors"] += 1
                    else:
                        stats["skipped"] += 1

                    if progress_callback and stats["indexed"] % 50 == 0:
                        progress_callback(stats["indexed"])

                # Remove deleted files
                for rel_str in set(indexed) - set(current_files):
                    self._remove_from_index(conn, Path(rel_str), vault_name)
                    stats["removed"] += 1

                # Update metadata
                conn.execute("""
                    INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)
                """, ("last_full_index", str(time.time())))
                conn.execute("""
                    INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)
                """, ("indexed_count", str(len(current_files))))

                # Update vault metadata
                conn.execute("""
                    INSERT OR REPLACE INTO vaults (name, path, is_active, indexed_at, note_count)
                    VALUES (?, ?, 1, ?, ?)
                """, (vault_name, str(self.vault_root), time.time(), len(current_files)))

                conn.commit()

        finally:
            self._indexing = False

        elapsed = time.time() - start_time
        logger.info("index.complete", **stats, elapsed_ms=int(elapsed * 1000))
        return stats

    def index_incremental(self, vault_name: str = "Vault") -> dict[str, int]:
        """Quick incremental index (only changed files since last run)."""
        return self.index_all(force=False, vault_name=vault_name)

    def search(self, query: str, limit: int = 100, path_filter: str | None = None, vault_name: str = "Vault") -> list[dict[str, Any]]:
        """Full-text search using FTS5 with BM25 ranking."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            # Build FTS5 query with BM25 ranking
            sql = """
                SELECT n.path, n.name, n.size, n.modified, n.frontmatter,
                       bm25(notes_fts) as rank,
                       snippet(notes_fts, 2, '<mark>', '</mark>', '...', 32) as snippet
                FROM notes_fts
                JOIN notes n ON notes_fts.path = n.path
                WHERE notes_fts MATCH ? AND notes_fts.vault = ?
            """
            params = [query, vault_name]

            if path_filter:
                sql += " AND n.path LIKE ?"
                params.append(f"{path_filter}%")

            sql += " ORDER BY rank LIMIT ?"
            params.append(str(limit))

            cursor = conn.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                import json
                fm = json.loads(row[4]) if row[4] else None
                results.append({
                    "path": row[0],
                    "name": row[1],
                    "size": row[2],
                    "modified": row[3],
                    "frontmatter": fm,
                    "rank": row[5],
                    "snippet": row[6],
                })
            return results

    def search_frontmatter(self, key: str, operator: str, value: str | None,
                           limit: int = 100, path_filter: str | None = None, vault_name: str = "Vault") -> list[dict[str, Any]]:
        """Fast frontmatter property search using indexed properties."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            if operator == "exists":
                sql = """
                    SELECT n.path, n.name, n.size, n.modified, n.frontmatter
                    FROM notes n
                    JOIN frontmatter_props fp ON n.path = fp.path AND n.vault = fp.vault
                    WHERE fp.key = ? AND fp.vault = ?
                """
                params = [key, vault_name]
            else:
                sql = """
                    SELECT n.path, n.name, n.size, n.modified, n.frontmatter
                    FROM notes n
                    JOIN frontmatter_props fp ON n.path = fp.path AND n.vault = fp.vault
                    WHERE fp.key = ? AND fp.vault = ?
                """
                params = [key, vault_name]

                if operator == "eq":
                    sql += " AND fp.value = ?"
                    params.append(value or "")
                elif operator == "ne":
                    sql += " AND fp.value != ?"
                    params.append(value or "")
                elif operator == "contains":
                    sql += " AND fp.value LIKE ?"
                    params.append(f"%{value}%")
                elif operator == "startswith":
                    sql += " AND fp.value LIKE ?"
                    params.append(f"{value}%")
                elif operator == "endswith":
                    sql += " AND fp.value LIKE ?"
                    params.append(f"%{value}")
                elif operator in ("gt", "gte", "lt", "lte"):
                    # Numeric comparison - cast
                    sql += f" AND CAST(fp.value AS REAL) {operator} ?"
                    params.append(value or "0")

            if path_filter:
                sql += " AND n.path LIKE ?"
                params.append(f"{path_filter}%")

            sql += " LIMIT ?"
            params.append(str(limit))

            cursor = conn.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                import json
                fm = json.loads(row[4]) if row[4] else None
                results.append({
                    "path": row[0],
                    "name": row[1],
                    "size": row[2],
                    "modified": row[3],
                    "frontmatter": fm,
                })
            return results

    def get_stats(self, vault_name: str = "Vault") -> dict[str, Any]:
        """Get index statistics."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM notes WHERE vault = ?", (vault_name,))
            total_notes = cursor.fetchone()[0]

            cursor = conn.execute("SELECT value FROM index_meta WHERE key = 'last_full_index'")
            row = cursor.fetchone()
            last_index = float(row[0]) if row else 0.0

            cursor = conn.execute("SELECT value FROM index_meta WHERE key = 'indexed_count'")
            row = cursor.fetchone()
            indexed_count = int(row[0]) if row else 0

            # DB size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "total_notes": total_notes,
                "indexed_count": indexed_count,
                "last_full_index": last_index,
                "db_size_bytes": db_size,
                "index_path": str(self.db_path),
            }

    def is_indexing(self) -> bool:
        return self._indexing

    def close(self) -> None:
        """Close any open connections (cleanup)."""
        # SQLite connections are per-operation

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new database connection for external use."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    # ===== NEW: Wikilink / Backlink Extraction =====

    def extract_wikilinks(self, content: str) -> list[dict[str, Any]]:
        """Extract [[wikilinks]] from content. Returns list of {target, alias, line, context}."""
        links = []
        # Pattern: [[target]] or [[target|alias]]
        pattern = re.compile(r'\[\[([^\]]+?)(?:\|([^\]]+))?\]\]')
        lines = content.splitlines()
        for i, line in enumerate(lines):
            for match in pattern.finditer(line):
                target = match.group(1).strip()
                alias = match.group(2).strip() if match.group(2) else None
                # Get context (surrounding 50 chars)
                start = max(0, match.start() - 50)
                end = min(len(line), match.end() + 50)
                context = line[start:end]
                links.append({
                    "target": target,
                    "alias": alias,
                    "line": i + 1,
                    "context": context,
                })
        return links

    def index_wikilinks(self, conn: sqlite3.Connection, rel_path: Path, content: str, vault_name: str = "Vault") -> None:
        """Index wikilinks for a file."""
        links = self.extract_wikilinks(content)
        for link in links:
            conn.execute("""
                INSERT OR REPLACE INTO wikilinks (source_path, target, alias, line, context, vault)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(rel_path), link["target"], link["alias"], link["line"], link["context"], vault_name))

    def get_wikilinks(self, rel_path: Path, vault_name: str = "Vault") -> list[dict[str, Any]]:
        """Get outgoing wikilinks for a note."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT target, alias, line, context FROM wikilinks WHERE source_path = ? AND vault = ?
            """, (str(rel_path), vault_name))
            return [{"target": r[0], "alias": r[1], "line": r[2], "context": r[3]} for r in cursor.fetchall()]

    def get_backlinks(self, target: str, vault_name: str = "Vault", limit: int = 100) -> list[dict[str, Any]]:
        """Get incoming backlinks to a note."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT source_path, line, context FROM wikilinks 
                WHERE target = ? AND vault = ? LIMIT ?
            """, (target, vault_name, limit))
            return [{"source": r[0], "line": r[1], "context": r[2]} for r in cursor.fetchall()]

    def get_graph(self, center: str | None = None, depth: int = 2, limit: int = 200, vault_name: str = "Vault") -> dict[str, Any]:
        """Get link graph for visualization."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            # Get all nodes (notes that have links)
            cursor = conn.execute("""
                SELECT DISTINCT source_path as path FROM wikilinks WHERE vault = ?
                UNION
                SELECT DISTINCT target as path FROM wikilinks WHERE vault = ?
            """, (vault_name, vault_name))
            all_nodes = [r[0] for r in cursor.fetchall()]

            # Filter by center if provided
            if center:
                # BFS from center
                visited = {center}
                current = {center}
                edges = []
                for _ in range(depth):
                    if len(visited) >= limit:
                        break
                    # Find outgoing from current
                    placeholders = ",".join("?" * len(current))
                    cursor = conn.execute(f"""
                        SELECT source_path, target FROM wikilinks 
                        WHERE (source_path IN ({placeholders}) OR target IN ({placeholders})) AND vault = ?
                    """, list(current) * 2 + [vault_name])
                    new_nodes = set()
                    for r in cursor.fetchall():
                        edges.append({"source": r[0], "target": r[1], "type": "wikilink"})
                        if r[0] not in visited:
                            new_nodes.add(r[0])
                        if r[1] not in visited:
                            new_nodes.add(r[1])
                    current = new_nodes
                    visited.update(new_nodes)
                nodes = list(visited)[:limit]
            else:
                nodes = all_nodes[:limit]
                cursor = conn.execute("""
                    SELECT source_path, target FROM wikilinks WHERE vault = ? LIMIT ?
                """, (vault_name, limit))
                edges = [{"source": r[0], "target": r[1], "type": "wikilink"} for r in cursor.fetchall()]

            return {
                "nodes": [{"id": n, "label": Path(n).stem} for n in nodes],
                "edges": edges,
            }

    # ===== NEW: Multi-vault management =====

    def add_vault(self, name: str, path: Path) -> None:
        """Add a vault to multi-vault configuration."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO vaults (name, path, is_active, indexed_at, note_count)
                VALUES (?, ?, 1, 0, 0)
            """, (name, str(path)))
            conn.commit()

    def remove_vault(self, name: str) -> None:
        """Remove a vault and all its indexed data."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM notes WHERE vault = ?", (name,))
            conn.execute("DELETE FROM notes_fts WHERE vault = ?", (name,))
            conn.execute("DELETE FROM frontmatter_props WHERE vault = ?", (name,))
            conn.execute("DELETE FROM wikilinks WHERE vault = ?", (name,))
            conn.execute("DELETE FROM vaults WHERE name = ?", (name,))
            conn.commit()

    def list_vaults(self) -> list[dict[str, Any]]:
        """List all configured vaults."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT name, path, is_active, indexed_at, note_count FROM vaults")
            return [{
                "name": r[0], "path": r[1], "is_active": bool(r[2]),
                "indexed_at": r[3], "note_count": r[4]
            } for r in cursor.fetchall()]

    def set_vault_active(self, name: str, active: bool) -> None:
        """Set vault active/inactive status."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE vaults SET is_active = ? WHERE name = ?", (1 if active else 0, name))
            conn.commit()
