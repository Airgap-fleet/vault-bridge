"""Core filesystem operations for Obsidian MCP Server."""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .logging import get_logger
from .models import (
    DailyNoteRequest,
    DailyNoteResponse,
    FrontmatterMatch,
    ListNotesRequest,
    ListNotesResponse,
    NoteEntry,
    ObsidianConfig,
    ReadNoteRequest,
    ReadNoteResponse,
    SearchFrontmatterRequest,
    SearchFrontmatterResponse,
    SearchMatch,
    SearchNotesRequest,
    SearchNotesResponse,
    WriteNoteRequest,
    WriteNoteResponse,
)

logger = get_logger(__name__)


class ObsidianCore:
    """Core operations for Obsidian vault interaction."""

    def __init__(self, config: ObsidianConfig | None = None):
        self.config = config or ObsidianConfig()
        self._vault_root = self.config.resolved_vault_path

    @property
    def vault_root(self) -> Path:
        return self._vault_root

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
        return "---\n" + yaml.dump(fm, default_flow_style=False, sort_keys=False) + "---\n"

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

        stat = path.stat()
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
        matches = []

        def compare(op: str, a: Any, b: Any) -> bool:
            if op == "eq":
                return a == b
            elif op == "ne":
                return a != b
            elif op == "contains":
                return str(b).lower() in str(a).lower()
            elif op == "startswith":
                return str(a).lower().startswith(str(b).lower())
            elif op == "endswith":
                return str(a).lower().endswith(str(b).lower())
            elif op == "gt":
                return a > b
            elif op == "lt":
                return a < b
            elif op == "gte":
                return a >= b
            elif op == "lte":
                return a <= b
            elif op == "exists":
                return a is not None
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
            frontmatter: dict[str, str] = {}
            if not path.exists():
                if not request.create_if_missing:
                    logger.warning("get_daily_note.not_found", path=str(path))
                    raise FileNotFoundError(f"Daily note not found: {path}")
                path.parent.mkdir(parents=True, exist_ok=True)
                content = ""
                initial_frontmatter = {"date": date_str}
                if request.template:
                    # TODO: load template
                    pass
                content = self._format_frontmatter(initial_frontmatter)
                path.write_text(content, encoding=self.config.default_encoding)
                created = True
                frontmatter = initial_frontmatter
                logger.info("get_daily_note.created", path=str(path.relative_to(self._vault_root)), date=date_str)
            else:
                content = path.read_text(encoding=self.config.default_encoding)
                frontmatter_raw, content = self._parse_frontmatter(content)
                frontmatter = frontmatter_raw or {}
                logger.info("get_daily_note.existing", path=str(path.relative_to(self._vault_root)), date=date_str)

            return DailyNoteResponse(
                path=str(path.relative_to(self._vault_root)),
                content=content,
                frontmatter=frontmatter,
                date=date_str,
                created=created,
            )