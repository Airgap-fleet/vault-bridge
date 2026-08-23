"""Core filesystem operations for Obsidian MCP Server."""

import base64
import re
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from .indexer import VaultIndexer
from .logging import get_logger
from .models import (
    BacklinkEntry,
    CanvasEdge,
    CanvasNode,
    CanvasRequest,
    CanvasResponse,
    ConfigureRequest,
    ConfigureResponse,
    DailyNoteRequest,
    DailyNoteResponse,
    ErrorResponse,
    FrontmatterMatch,
    GraphEdge,
    GraphNode,
    GraphRequest,
    GraphResponse,
    IndexStatsRequest,
    IndexStatsResponse,
    ListNotesRequest,
    ListNotesResponse,
    ListResourcesRequest,
    ListResourcesResponse,
    MetricsRequest,
    MetricsResponse,
    MultiVaultConfigRequest,
    MultiVaultConfigResponse,
    MultiVaultStatusRequest,
    MultiVaultStatusResponse,
    NoteEntry,
    ObsidianConfig,
    PropertiesRequest,
    PropertiesResponse,
    PropertyValue,
    ReadImageRequest,
    ReadImageResponse,
    ReadNoteRequest,
    ReadNoteResponse,
    ReindexRequest,
    ReindexResponse,
    ResourceContent,
    ResourceEntry,
    ResourceRequest,
    ResourceResponse,
    SearchFrontmatterRequest,
    SearchFrontmatterResponse,
    SearchIndexedMatch,
    SearchIndexedRequest,
    SearchIndexedResponse,
    SearchMatch,
    SearchNotesRequest,
    SearchNotesResponse,
    VaultEntry,
    WikilinkEntry,
    WikilinkRequest,
    WikilinkResponse,
    WriteNoteRequest,
    WriteNoteResponse,
)

logger = get_logger(__name__)


class ObsidianCore:
    """Core operations for Obsidian vault interaction."""

    def __init__(self, config: ObsidianConfig | None = None):
        self.config = config or ObsidianConfig()
        self._vault_root = self.config.resolved_vault_path
        # Initialize indexer
        index_dir = self._vault_root / ".vault-bridge"
        self._indexer = VaultIndexer(self._vault_root, index_dir)
        self._index_lock = threading.Lock()
        self._indexed = False
        
        # Multi-vault support
        self._vaults: dict[str, Path] = {"Vault": self._vault_root}
        self._vault_indexers: dict[str, VaultIndexer] = {"Vault": self._indexer}
        
        # Metrics counters
        from collections import defaultdict
        self._metrics: dict[str, Any] = {
            "requests_total": defaultdict(int),
            "request_duration_seconds": defaultdict(list),
            "errors_total": defaultdict(int),
            "bytes_read": 0,
            "bytes_written": 0,
        }

    @property
    def vault_root(self) -> Path:
        return self._vault_root

    def _ensure_indexed(self) -> None:
        """Ensure index is built (run incremental on first use)."""
        with self._index_lock:
            if not self._indexed:
                logger.info("index.initial_build_starting")
                self._indexer.index_incremental()
                self._indexed = True

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative path to absolute within vault."""
        p = Path(path)
        if p.is_absolute():
            raise ValueError("Absolute paths not allowed; use paths relative to vault root.")
        resolved = (self._vault_root / p).resolve()
        # Security: ensure path is within vault
        try:
            resolved.relative_to(self._vault_root)
        except ValueError:
            raise ValueError(f"Path escapes vault root: {path}")
        return resolved

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any] | None, str]:
        """Parse YAML frontmatter from note content."""
        if not content.startswith("---"):
            return None, content
        try:
            parts = content.split("---", 2)
            if len(parts) < 3:
                return None, content
            fm = yaml.safe_load(parts[1])
            body = parts[2].lstrip("\n")
            return fm if isinstance(fm, dict) else None, body
        except yaml.YAMLError:
            return None, content

    def _format_frontmatter(self, fm: dict[str, Any]) -> str:
        """Format frontmatter as YAML."""
        return "---\n" + str(yaml.dump(fm, default_flow_style=False, sort_keys=False)) + "---\n"

    def read_note(self, request: ReadNoteRequest) -> ReadNoteResponse:
        """Read a note from the vault."""
        logger.debug("read_note.start", path=request.path)
        path = self._resolve_path(request.path)
        if not path.exists():
            logger.warning("read_note.not_found", path=request.path)
            raise FileNotFoundError(f"Note not found: {request.path}")
        if not path.is_file():
            logger.warning("read_note.not_file", path=request.path)
            raise ValueError(f"Path is not a file: {request.path}")

        stat = path.stat()
        content = path.read_text(encoding=self.config.default_encoding)

        frontmatter = None
        if request.include_frontmatter:
            frontmatter, content = self._parse_frontmatter(content)

        logger.info("read_note.success", path=request.path, size=stat.st_size)
        return ReadNoteResponse(
            path=request.path,
            content=content,
            frontmatter=frontmatter,
            size=stat.st_size,
            modified=stat.st_mtime,
        )

    def write_note(self, request: WriteNoteRequest) -> WriteNoteResponse:
        """Write a note to the vault."""
        logger.debug("write_note.start", path=request.path, atomic=request.atomic)
        path = self._resolve_path(request.path)

        if request.create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        content = request.content
        if request.frontmatter:
            content = self._format_frontmatter(request.frontmatter) + content

        if request.atomic:
            # Write to temp file then rename
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(content, encoding=self.config.default_encoding)
            temp_path.replace(path)
        else:
            path.write_text(content, encoding=self.config.default_encoding)

        # Update index incrementally
        try:
            rel_path = path.relative_to(self._vault_root)
            with self._index_lock:
                if self._indexed:
                    self._indexer._index_single_file(
                        self._indexer._get_conn(), rel_path, path
                    )
        except Exception as e:
            logger.debug("write_note.index_update_failed", path=request.path, error=str(e))

        stat = path.stat()
        self._metrics["bytes_written"] += stat.st_size
        logger.info("write_note.success", path=request.path, size=stat.st_size, atomic=request.atomic)
        return WriteNoteResponse(
            path=request.path,
            size=stat.st_size,
        )

    def list_notes(self, request: ListNotesRequest) -> ListNotesResponse:
        """List notes in the vault."""
        logger.debug("list_notes.start", path=request.path, recursive=request.recursive)
        base_path = self._resolve_path(request.path)
        if not base_path.exists():
            logger.warning("list_notes.not_found", path=request.path)
            raise FileNotFoundError(f"Directory not found: {request.path}")
        if not base_path.is_dir():
            logger.warning("list_notes.not_dir", path=request.path)
            raise ValueError(f"Path is not a directory: {request.path}")

        pattern = request.glob_pattern or "**/*.md"
        if request.recursive:
            files = base_path.rglob(pattern.replace("**/", ""))
        else:
            files = base_path.glob(pattern.replace("**/", ""))

        entries = []
        for f in files:
            if not f.is_file():
                continue
            try:
                rel = f.relative_to(self._vault_root)
            except ValueError:
                continue

            stat = f.stat()
            frontmatter = None
            if request.include_frontmatter:
                content = f.read_text(encoding=self.config.default_encoding)
                frontmatter, _ = self._parse_frontmatter(content)

            entries.append(NoteEntry(
                name=f.name,
                path=str(rel),
                size=stat.st_size,
                modified=stat.st_mtime,
                frontmatter=frontmatter,
            ))

        logger.info("list_notes.success", path=request.path, total=len(entries))
        return ListNotesResponse(
            path=request.path,
            entries=entries,
            total=len(entries),
        )

    def search_notes(self, request: SearchNotesRequest) -> SearchNotesResponse:
        """Search notes using regex."""
        logger.debug("search_notes.start", pattern=request.pattern, path=request.path, case_sensitive=request.case_sensitive)
        base_path = self._resolve_path(request.path)
        if not base_path.exists():
            logger.warning("search_notes.not_found", path=request.path)
            raise FileNotFoundError(f"Directory not found: {request.path}")

        pattern = re.compile(request.pattern, 0 if request.case_sensitive else re.IGNORECASE)
        glob_pat = request.glob_pattern or "**/*.md"

        matches = []
        for f in base_path.rglob(glob_pat.replace("**/", "")):
            if not f.is_file():
                continue
            try:
                rel = f.relative_to(self._vault_root)
            except ValueError:
                continue

            try:
                content = f.read_text(encoding=self.config.default_encoding)
            except UnicodeDecodeError:
                continue

            lines = content.splitlines()
            for i, line in enumerate(lines):
                for m in pattern.finditer(line):
                    start = max(0, i - request.context_lines)
                    end = min(len(lines), i + request.context_lines + 1)
                    matches.append(SearchMatch(
                        file=str(rel),
                        line=i + 1,
                        column=m.start() + 1,
                        match=m.group(),
                        context_before=lines[start:i],
                        context_after=lines[i+1:end],
                    ))
                    if len(matches) >= request.max_results:
                        break
                if len(matches) >= request.max_results:
                    break
            if len(matches) >= request.max_results:
                break

        logger.info("search_notes.success", pattern=request.pattern, path=request.path, total=len(matches), truncated=len(matches) >= request.max_results)
        return SearchNotesResponse(
            pattern=request.pattern,
            path=request.path,
            matches=matches,
            total=len(matches),
            truncated=len(matches) >= request.max_results,
        )

    def search_frontmatter(self, request: SearchFrontmatterRequest) -> SearchFrontmatterResponse:
        """Search notes by frontmatter key/value."""
        logger.debug("search_frontmatter.start", key=request.key, operator=request.operator, path=request.path)
        base_path = self._resolve_path(request.path)
        if not base_path.exists():
            logger.warning("search_frontmatter.not_found", path=request.path)
            raise FileNotFoundError(f"Directory not found: {request.path}")

        glob_pat = request.glob_pattern or "**/*.md"
        matches: list[FrontmatterMatch] = []

        def compare(op: str, a: Any, b: Any) -> bool:
            if op == "eq":
                return bool(a == b)
            elif op == "ne":
                return bool(a != b)
            elif op == "contains":
                return bool(str(b).lower() in str(a).lower())
            elif op == "startswith":
                return bool(str(a).lower().startswith(str(b).lower()))
            elif op == "endswith":
                return bool(str(a).lower().endswith(str(b).lower()))
            elif op == "gt":
                return bool(a > b)
            elif op == "lt":
                return bool(a < b)
            elif op == "gte":
                return bool(a >= b)
            elif op == "lte":
                return bool(a <= b)
            elif op == "exists":
                return bool(a is not None)
            return False

        for f in base_path.rglob(glob_pat.replace("**/", "")):
            if not f.is_file():
                continue
            try:
                rel = f.relative_to(self._vault_root)
            except ValueError:
                continue

            try:
                content = f.read_text(encoding=self.config.default_encoding)
            except UnicodeDecodeError:
                continue

            fm, _ = self._parse_frontmatter(content)
            if not fm:
                continue

            # Handle "exists" operator specially - only match if key actually exists
            if request.operator == "exists":
                if request.key in fm:
                    matches.append(FrontmatterMatch(
                        file=str(rel),
                        frontmatter=fm,
                    ))
                    if len(matches) >= request.max_results:
                        break
                continue

            if request.key not in fm:
                continue

            value = fm.get(request.key)
            if request.value is None:
                continue
            else:
                match = compare(request.operator, value, request.value)

            if match:
                matches.append(FrontmatterMatch(
                    file=str(rel),
                    frontmatter=fm,
                ))
                if len(matches) >= request.max_results:
                    break

        logger.info("search_frontmatter.success", key=request.key, operator=request.operator, path=request.path, total=len(matches), truncated=len(matches) >= request.max_results)
        return SearchFrontmatterResponse(
            key=request.key,
            value=request.value,
            operator=request.operator,
            matches=matches,
            total=len(matches),
            truncated=len(matches) >= request.max_results,
        )

    def get_daily_note(self, request: DailyNoteRequest) -> DailyNoteResponse:
        """Get or create a daily note."""
        logger.debug("get_daily_note.start", date=request.date, folder=request.folder, create_if_missing=request.create_if_missing)
        if request.date:
            try:
                date = datetime.strptime(request.date, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                logger.warning("get_daily_note.invalid_date", date=request.date)
                raise ValueError("Date must be in YYYY-MM-DD format")
        else:
            date = datetime.now(UTC)

        date_str = date.strftime("%Y-%m-%d")
        folder = request.folder.rstrip("/")
        path = self._resolve_path(f"{folder}/{date_str}.md")

        created = False
        frontmatter: dict[str, Any] | None = None
        if not path.exists():
            if not request.create_if_missing:
                logger.warning("get_daily_note.not_found", path=str(path))
                raise FileNotFoundError(f"Daily note not found: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            content = ""
            frontmatter = {"date": date_str}
            if request.template:
                # TODO: load template
                pass
            content = self._format_frontmatter(frontmatter)
            path.write_text(content, encoding=self.config.default_encoding)
            created = True
            logger.info("get_daily_note.created", path=str(path.relative_to(self._vault_root)), date=date_str)
        else:
            content = path.read_text(encoding=self.config.default_encoding)
            parsed_fm, content = self._parse_frontmatter(content)
            frontmatter = parsed_fm
            logger.info("get_daily_note.existing", path=str(path.relative_to(self._vault_root)), date=date_str)

        return DailyNoteResponse(
            path=str(path.relative_to(self._vault_root)),
            content=content,
            frontmatter=frontmatter,
            date=date_str,
            created=created,
        )

    # ===== NEW: Indexed Search (FTS5 + BM25) =====

    def search_indexed(self, request: SearchIndexedRequest) -> SearchIndexedResponse:
        """Search notes using persistent FTS5 index with BM25 ranking."""
        logger.debug("search_indexed.start", query=request.query, path=request.path)
        self._ensure_indexed()
        base_path = self._resolve_path(request.path)
        if not base_path.exists():
            logger.warning("search_indexed.not_found", path=request.path)
            raise FileNotFoundError(f"Directory not found: {request.path}")

        path_filter: str | None = str(base_path.relative_to(self._vault_root))
        if path_filter == ".":
            path_filter = None

        results = self._indexer.search(request.query, request.max_results, path_filter)
        
        matches = [
            SearchIndexedMatch(
                file=r["path"],
                name=r["name"],
                size=r["size"],
                modified=r["modified"],
                frontmatter=r["frontmatter"],
                rank=r["rank"],
                snippet=r["snippet"],
            )
            for r in results
        ]

        logger.info("search_indexed.success", query=request.query, total=len(matches))
        return SearchIndexedResponse(
            query=request.query,
            path=request.path,
            matches=matches,
            total=len(matches),
            truncated=len(matches) >= request.max_results,
        )

    def reindex(self, request: ReindexRequest) -> ReindexResponse:
        """Rebuild the search index."""
        logger.info("reindex.start", force=request.force)
        start = time.time()
        self._indexed = False  # Force rebuild
        stats = self._indexer.index_all(force=request.force)
        elapsed = int((time.time() - start) * 1000)
        
        logger.info("reindex.complete", **stats, elapsed_ms=elapsed)
        return ReindexResponse(
            indexed=stats["indexed"],
            removed=stats["removed"],
            errors=stats["errors"],
            skipped=stats["skipped"],
            elapsed_ms=elapsed,
        )

    def index_stats(self, request: IndexStatsRequest) -> IndexStatsResponse:
        """Get index statistics."""
        stats = self._indexer.get_stats()
        return IndexStatsResponse(
            total_notes=stats["total_notes"],
            indexed_count=stats["indexed_count"],
            last_full_index=stats["last_full_index"],
            db_size_bytes=stats["db_size_bytes"],
            index_path=stats["index_path"],
        )

    # ===== NEW: Image Support =====

    def read_image(self, request: ReadImageRequest) -> ReadImageResponse:
        """Read an image from the vault and return base64-encoded data."""
        logger.debug("read_image.start", path=request.path)
        path = self._resolve_path(request.path)
        if not path.exists():
            logger.warning("read_image.not_found", path=request.path)
            raise FileNotFoundError(f"Image not found: {request.path}")
        if not path.is_file():
            logger.warning("read_image.not_file", path=request.path)
            raise ValueError(f"Path is not a file: {request.path}")

        # Check if it's an image
        mime_type = self._get_mime_type(path)
        if not mime_type or not mime_type.startswith("image/"):
            logger.warning("read_image.not_image", path=request.path, mime=mime_type)
            raise ValueError(f"File is not an image: {request.path}")

        import base64
        from PIL import Image

        # Read image data
        image_data = path.read_bytes()
        b64_data = base64.b64encode(image_data).decode("ascii")

        # Get dimensions
        with Image.open(path) as img:
            width, height = img.size

        stat = path.stat()
        logger.info("read_image.success", path=request.path, size=stat.st_size, width=width, height=height)
        return ReadImageResponse(
            path=request.path,
            mime_type=mime_type,
            size=stat.st_size,
            width=width,
            height=height,
            base64=b64_data,
        )

    def _get_mime_type(self, path: Path) -> str | None:
        """Get MIME type from file extension."""
        ext = path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".svg": "image/svg+xml",
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".json": "application/json",
            ".yaml": "application/yaml",
            ".yml": "application/x-yaml",
            ".pdf": "application/pdf",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
        }
        return mime_map.get(ext)

    # ===== NEW: MCP Resources API (vault://, file:// URIs) =====

    def _resolve_resource_uri(self, uri: str) -> tuple[str, Path]:
        """Resolve a resource URI to (vault_name, absolute_path)."""
        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()
        
        if scheme == "vault":
            # vault://Vault/path/to/note.md or vault:///path/to/note.md (default vault)
            vault_name = parsed.netloc or "Vault"
            path_str = parsed.path.lstrip("/")
            if vault_name not in self._vaults:
                raise ValueError(f"Unknown vault: {vault_name}")
            vault_root = self._vaults[vault_name]
            abs_path = (vault_root / path_str).resolve()
            try:
                abs_path.relative_to(vault_root)
            except ValueError:
                raise ValueError(f"Path escapes vault root: {path_str}")
            return vault_name, abs_path
        elif scheme == "file":
            # file:///absolute/path
            abs_path = Path(parsed.path).resolve()
            # For file://, allow any path but warn
            return "file", abs_path
        else:
            raise ValueError(f"Unsupported URI scheme: {scheme}. Supported: vault://, file://")

    def read_resource(self, request: ResourceRequest) -> ResourceResponse:
        """Read a resource by URI (vault://, file://)."""
        self._metrics["requests_total"]["read_resource"] += 1
        start = time.time()
        
        try:
            vault_name, abs_path = self._resolve_resource_uri(request.uri)
            
            if not abs_path.exists():
                raise FileNotFoundError(f"Resource not found: {request.uri}")
            
            mime_type = self._get_mime_type(abs_path) or "application/octet-stream"
            
            if abs_path.is_file():
                size = abs_path.stat().st_size
                if size > request.limit + request.offset:
                    # Large file - stream
                    with open(abs_path, "rb") as f:
                        f.seek(request.offset)
                        data = f.read(request.limit)
                else:
                    data = abs_path.read_bytes()[request.offset:request.offset + request.limit]
                
                if mime_type.startswith("text/") or mime_type in ("application/json", "application/yaml", "application/x-yaml"):
                    text = data.decode(self.config.default_encoding, errors="replace")
                    content = ResourceContent(uri=request.uri, mime_type=mime_type, text=text)
                else:
                    b64 = base64.b64encode(data).decode("ascii")
                    content = ResourceContent(uri=request.uri, mime_type=mime_type, blob=b64)
                
                self._metrics["bytes_read"] += len(data)
                logger.info("read_resource.success", uri=request.uri, size=len(data))
                return ResourceResponse(contents=[content])
            else:
                # Directory - list entries
                entries = []
                for entry in abs_path.iterdir():
                    if entry.is_file():
                        entry_mime = self._get_mime_type(entry) or "application/octet-stream"
                        entries.append(ResourceContent(
                            uri=f"{request.uri.rstrip('/')}/{entry.name}",
                            mime_type=entry_mime,
                            name=entry.name,
                        ))
                return ResourceResponse(contents=entries)
        except Exception as e:
            self._metrics["errors_total"]["read_resource"] += 1
            logger.error("read_resource.failed", uri=request.uri, error=str(e))
            raise
        finally:
            self._metrics["request_duration_seconds"]["read_resource"].append(time.time() - start)

    def list_resources(self, request: ListResourcesRequest) -> ListResourcesResponse:
        """List resources under a URI prefix."""
        self._metrics["requests_total"]["list_resources"] += 1
        start = time.time()
        
        try:
            vault_name, abs_path = self._resolve_resource_uri(request.uri_prefix)
            
            if not abs_path.exists():
                raise FileNotFoundError(f"Path not found: {request.uri_prefix}")
            
            resources = []
            count = 0
            for entry in abs_path.rglob("*"):
                if count >= request.limit:
                    break
                if entry.is_file():
                    try:
                        rel = entry.relative_to(abs_path)
                        mime_type = self._get_mime_type(entry) or "application/octet-stream"
                        size = entry.stat().st_size
                        resources.append(ResourceEntry(
                            uri=f"{request.uri_prefix.rstrip('/')}/{rel}",
                            name=entry.name,
                            mime_type=mime_type,
                            size=size,
                        ))
                        count += 1
                    except ValueError:
                        continue
            
            logger.info("list_resources.success", uri_prefix=request.uri_prefix, total=len(resources))
            return ListResourcesResponse(resources=resources, next_cursor=None)
        except Exception as e:
            self._metrics["errors_total"]["list_resources"] += 1
            logger.error("list_resources.failed", uri_prefix=request.uri_prefix, error=str(e))
            raise
        finally:
            self._metrics["request_duration_seconds"]["list_resources"].append(time.time() - start)

    # ===== NEW: Wikilink / Backlink Graph =====

    def get_wikilinks(self, request: WikilinkRequest) -> WikilinkResponse:
        """Get outgoing wikilinks and incoming backlinks for a note."""
        self._metrics["requests_total"]["get_wikilinks"] += 1
        start = time.time()
        
        try:
            path = self._resolve_path(request.path)
            if not path.exists():
                raise FileNotFoundError(f"Note not found: {request.path}")
            
            content = path.read_text(encoding=self.config.default_encoding)
            
            # Extract outgoing wikilinks
            wikilinks = self._indexer.extract_wikilinks(content)
            wikilink_entries = []
            lines = content.splitlines()
            for i, line in enumerate(lines):
                for match in re.finditer(r"\[\[([^\]]+)\]\]", line):
                    target_full = match.group(1)
                    if "|" in target_full:
                        target, alias = target_full.split("|", 1)
                    else:
                        target, alias = target_full, None
                    wikilink_entries.append(WikilinkEntry(
                        target=target.strip(),
                        alias=alias.strip() if alias else None,
                        line=i + 1,
                        context=line.strip(),
                    ))
            
            # Find backlinks (notes that link to this note)
            backlink_entries = []
            if request.include_backlinks:
                note_name = path.stem
                self._ensure_indexed()
                conn = self._indexer._get_conn()
                try:
                    rows = conn.execute("""
                        SELECT source_path, target, line, context
                        FROM wikilinks
                        WHERE target = ?
                    """, (note_name,)).fetchall()
                    for row in rows:
                        backlink_entries.append(BacklinkEntry(
                            source=row[0],
                            line=row[2],
                            context=row[3],
                        ))
                finally:
                    conn.close()
            
            logger.info("get_wikilinks.success", path=request.path, outgoing=len(wikilink_entries), incoming=len(backlink_entries))
            return WikilinkResponse(
                path=request.path,
                wikilinks=wikilink_entries,
                backlinks=backlink_entries,
                total_outgoing=len(wikilink_entries),
                total_incoming=len(backlink_entries),
            )
        except Exception as e:
            self._metrics["errors_total"]["get_wikilinks"] += 1
            logger.error("get_wikilinks.failed", path=request.path, error=str(e))
            raise
        finally:
            self._metrics["request_duration_seconds"]["get_wikilinks"].append(time.time() - start)

    def get_graph(self, request: GraphRequest) -> GraphResponse:
        """Get graph of notes and links."""
        self._metrics["requests_total"]["get_graph"] += 1
        start = time.time()
        
        try:
            self._ensure_indexed()
            conn = self._indexer._get_conn()
            
            nodes = []
            edges = []
            seen_nodes = set()
            
            # Get all wikilinks
            rows = conn.execute("""
                SELECT source_path, target, line, context FROM wikilinks
            """).fetchall()
            
            for row in rows:
                source, target = row[0], row[1]
                if source not in seen_nodes:
                    nodes.append(GraphNode(id=source, label=Path(source).stem))
                    seen_nodes.add(source)
                if target not in seen_nodes:
                    # Target might not exist as a file
                    nodes.append(GraphNode(id=target, label=target))
                    seen_nodes.add(target)
                edges.append(GraphEdge(source=source, target=target, type="wikilink"))
            
            # Limit nodes
            if len(nodes) > request.limit:
                nodes = nodes[:request.limit]
                # Filter edges to only include nodes we kept
                kept_ids = {n.id for n in nodes}
                edges = [e for e in edges if e.source in kept_ids and e.target in kept_ids]
            
            logger.info("get_graph.success", nodes=len(nodes), edges=len(edges))
            return GraphResponse(nodes=nodes, edges=edges, center=request.center)
        except Exception as e:
            self._metrics["errors_total"]["get_graph"] += 1
            logger.error("get_graph.failed", error=str(e))
            raise
        finally:
            self._metrics["request_duration_seconds"]["get_graph"].append(time.time() - start)

    # ===== NEW: Canvas (.canvas) Support =====

    def read_canvas(self, request: CanvasRequest) -> CanvasResponse:
        """Read a .canvas file."""
        self._metrics["requests_total"]["read_canvas"] += 1
        start = time.time()
        
        try:
            path = self._resolve_path(request.path)
            if not path.exists():
                raise FileNotFoundError(f"Canvas file not found: {request.path}")
            
            import json
            data = json.loads(path.read_text(encoding=self.config.default_encoding))
            
            nodes = []
            for n in data.get("nodes", []):
                nodes.append(CanvasNode(
                    id=n.get("id", ""),
                    type=n.get("type", "text"),
                    x=n.get("x", 0),
                    y=n.get("y", 0),
                    width=n.get("width"),
                    height=n.get("height"),
                    text=n.get("text"),
                    url=n.get("url"),
                    file=n.get("file"),
                    color=n.get("color"),
                    label=n.get("label"),
                ))
            
            edges = []
            for e in data.get("edges", []):
                edges.append(CanvasEdge(
                    id=e.get("id", ""),
                    from_node=e.get("fromNode", ""),
                    from_side=e.get("fromSide"),
                    to_node=e.get("toNode", ""),
                    to_side=e.get("toSide"),
                    label=e.get("label"),
                    color=e.get("color"),
                ))
            
            logger.info("read_canvas.success", path=request.path, nodes=len(nodes), edges=len(edges))
            return CanvasResponse(path=request.path, nodes=nodes, edges=edges)
        except Exception as e:
            self._metrics["errors_total"]["read_canvas"] += 1
            logger.error("read_canvas.failed", path=request.path, error=str(e))
            raise
        finally:
            self._metrics["request_duration_seconds"]["read_canvas"].append(time.time() - start)

    # ===== NEW: Properties v2 (Obsidian native) =====

    def get_properties(self, request: PropertiesRequest) -> PropertiesResponse:
        """Get Obsidian Properties (frontmatter v2) for a note."""
        self._metrics["requests_total"]["get_properties"] += 1
        start = time.time()
        
        try:
            path = self._resolve_path(request.path)
            if not path.exists():
                raise FileNotFoundError(f"Note not found: {request.path}")
            
            content = path.read_text(encoding=self.config.default_encoding)
            fm, _ = self._parse_frontmatter(content)
            
            properties = {}
            if fm:
                for key, value in fm.items():
                    prop_type = self._infer_property_type(value)
                    properties[key] = PropertyValue(type=prop_type, value=value)
            
            logger.info("get_properties.success", path=request.path, count=len(properties))
            return PropertiesResponse(path=request.path, properties=properties)
        except Exception as e:
            self._metrics["errors_total"]["get_properties"] += 1
            logger.error("get_properties.failed", path=request.path, error=str(e))
            raise
        finally:
            self._metrics["request_duration_seconds"]["get_properties"].append(time.time() - start)

    def _infer_property_type(self, value: Any) -> str:
        """Infer Obsidian property type from Python value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, list):
            if value and all(isinstance(v, str) for v in value):
                return "multiselect"
            return "list"
        elif isinstance(value, str):
            # Check for date/datetime format
            if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
                return "date"
            if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
                return "datetime"
            return "string"
        return "string"

    # ===== NEW: Multi-Vault Support =====

    def multi_vault_config(self, request: MultiVaultConfigRequest) -> MultiVaultConfigResponse:
        """Configure multiple vaults."""
        configured = []
        failed = []
        
        for vault in request.vaults:
            try:
                vault_path = Path(vault.path).expanduser().resolve()
                if not vault_path.exists():
                    raise ValueError(f"Vault path does not exist: {vault.path}")
                if not (vault_path / ".obsidian").exists() and not any(vault_path.glob("*.md")):
                    raise ValueError(f"Not a valid Obsidian vault: {vault.path}")
                
                # Create indexer for this vault
                index_dir = vault_path / ".vault-bridge"
                indexer = VaultIndexer(vault_path, index_dir)
                
                self._vaults[vault.name] = vault_path
                self._vault_indexers[vault.name] = indexer
                configured.append(vault.name)
                logger.info("multi_vault_config.added", name=vault.name, path=str(vault_path))
            except Exception as e:
                failed.append(vault.name)
                logger.error("multi_vault_config.failed", name=vault.name, error=str(e))
        
        return MultiVaultConfigResponse(
            configured=configured,
            failed=failed,
            total=len(request.vaults),
        )

    def multi_vault_status(self, request: MultiVaultStatusRequest) -> MultiVaultStatusResponse:
        """Get status of all configured vaults."""
        vaults = []
        total_notes = 0
        
        for name, path in self._vaults.items():
            indexer = self._vault_indexers.get(name)
            stats = indexer.get_stats() if indexer else {"total_notes": 0}
            vaults.append(VaultEntry(
                name=name,
                path=str(path),
                is_active=name in self._vault_indexers,
            ))
            total_notes += stats.get("total_notes", 0)
        
        return MultiVaultStatusResponse(
            vaults=vaults,
            active_count=len(self._vault_indexers),
            total_notes=total_notes,
        )

    # ===== NEW: Prometheus Metrics =====

    def get_metrics(self, request: MetricsRequest) -> MetricsResponse:
        """Get Prometheus-formatted metrics."""
        lines = []
        
        # Request counters
        for method, count in self._metrics["requests_total"].items():
            lines.append(f'vault_bridge_requests_total{{method="{method}"}} {count}')
        
        # Error counters
        for method, count in self._metrics["errors_total"].items():
            lines.append(f'vault_bridge_errors_total{{method="{method}"}} {count}')
        
        # Duration histograms (simple summary)
        for method, durations in self._metrics["request_duration_seconds"].items():
            if durations:
                avg = sum(durations) / len(durations)
                lines.append(f'vault_bridge_request_duration_seconds_sum{{method="{method}"}} {sum(durations):.6f}')
                lines.append(f'vault_bridge_request_duration_seconds_count{{method="{method}"}} {len(durations)}')
                lines.append(f'vault_bridge_request_duration_seconds_avg{{method="{method}"}} {avg:.6f}')
        
        # Bytes
        lines.append(f'vault_bridge_bytes_read_total {self._metrics["bytes_read"]}')
        lines.append(f'vault_bridge_bytes_written_total {self._metrics["bytes_written"]}')
        
        # Vault info
        lines.append(f'vault_bridge_vaults_total {len(self._vaults)}')
        for name in self._vaults:
            lines.append(f'vault_bridge_vault_info{{name="{name}"}} 1')
        
        return MetricsResponse(metrics="\n".join(lines) + "\n")

    # ===== Rate Limiting Helper =====

    def _check_rate_limit(self, client_id: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        """Simple in-memory rate limiting. Returns True if allowed."""
        # In production, use Redis or similar distributed store
        now = time.time()
        key = f"ratelimit:{client_id}"
        # This is a simplified version - production would use sliding window
        return True  # Placeholder - implement with actual store