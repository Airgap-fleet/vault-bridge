"""Tests for ObsidianCore path resolution and security."""


import pytest


class TestPathResolution:
    """Test _resolve_path security and resolution."""

    def test_resolve_relative_path(self, core, temp_vault):
        """Test resolving a simple relative path."""
        path = core._resolve_path("note1.md")
        assert path == (temp_vault / "note1.md").resolve()

    def test_resolve_nested_path(self, core, temp_vault):
        """Test resolving a path in subdirectory."""
        path = core._resolve_path("subdir/note3.md")
        assert path == (temp_vault / "subdir" / "note3.md").resolve()

    def test_reject_absolute_path(self, core):
        """Test that absolute paths are rejected."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            core._resolve_path("/etc/passwd")

    def test_reject_path_traversal(self, core):
        """Test that path traversal is blocked."""
        with pytest.raises(ValueError, match="Path escapes vault root"):
            core._resolve_path("../note1.md")

    def test_reject_absolute_traversal(self, core):
        """Test that absolute path with traversal is blocked."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            core._resolve_path("/tmp/../../etc/passwd")


class TestFrontmatterParsing:
    """Test frontmatter parsing and formatting."""

    def test_parse_valid_frontmatter(self, core):
        """Test parsing valid YAML frontmatter."""
        content = "---\ntitle: Test\ntags: [a, b]\n---\n\nBody content"
        fm, body = core._parse_frontmatter(content)
        assert fm == {"title": "Test", "tags": ["a", "b"]}
        assert body == "Body content"

    def test_parse_no_frontmatter(self, core):
        """Test content without frontmatter returns None."""
        content = "# Heading\n\nNo frontmatter here."
        fm, body = core._parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_parse_invalid_yaml(self, core):
        """Test invalid YAML falls back gracefully."""
        content = "---\ntitle: Test\ninvalid: [\n---\n\nBody"
        fm, body = core._parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_format_frontmatter(self, core):
        """Test formatting frontmatter as YAML."""
        fm = {"title": "Test", "tags": ["a", "b"], "count": 42}
        result = core._format_frontmatter(fm)
        assert result.startswith("---\n")
        assert result.endswith("---\n")
        assert "title: Test" in result
        assert "tags:" in result
        assert "count: 42" in result

    def test_roundtrip_frontmatter(self, core):
        """Test parse -> format -> parse preserves data."""
        original = "---\ntitle: Roundtrip\nitems:\n  - one\n  - two\n---\n\nBody"
        fm, body = core._parse_frontmatter(original)
        formatted = core._format_frontmatter(fm)
        fm2, body2 = core._parse_frontmatter(formatted + body)
        assert fm == fm2
        assert body == body2


class TestReadNote:
    """Test read_note functionality."""

    def test_read_existing_note(self, core, temp_vault):
        """Test reading an existing note."""
        from obsidian_mcp.models import ReadNoteRequest
        req = ReadNoteRequest(path="note1.md", include_frontmatter=True)
        resp = core.read_note(req)
        
        assert resp.path == "note1.md"
        assert "Test Note 1" in resp.content
        assert resp.frontmatter == {"title": "Test Note 1", "tags": ["test", "example"]}
        assert resp.size > 0

    def test_read_note_without_frontmatter(self, core, temp_vault):
        """Test reading note without requesting frontmatter."""
        from obsidian_mcp.models import ReadNoteRequest
        req = ReadNoteRequest(path="note1.md", include_frontmatter=False)
        resp = core.read_note(req)
        
        assert resp.frontmatter is None
        # Content should include frontmatter since not parsed
        assert "title: Test Note 1" in resp.content

    def test_read_nonexistent_note(self, core):
        """Test reading non-existent note raises FileNotFoundError."""
        from obsidian_mcp.models import ReadNoteRequest
        req = ReadNoteRequest(path="does-not-exist.md")
        with pytest.raises(FileNotFoundError, match="Note not found"):
            core.read_note(req)

    def test_read_directory_as_file(self, core):
        """Test reading a directory as file raises ValueError."""
        from obsidian_mcp.models import ReadNoteRequest
        req = ReadNoteRequest(path="subdir")
        with pytest.raises(ValueError, match="not a file"):
            core.read_note(req)


class TestWriteNote:
    """Test write_note functionality."""

    def test_write_new_note(self, core, temp_vault):
        """Test writing a new note."""
        from obsidian_mcp.models import WriteNoteRequest
        req = WriteNoteRequest(
            path="new-note.md",
            content="# New Note\n\nContent here.",
            frontmatter={"title": "New Note", "created": "2026-01-15"}
        )
        resp = core.write_note(req)
        
        assert resp.path == "new-note.md"
        assert resp.size > 0
        assert (temp_vault / "new-note.md").exists()
        
        # Verify content
        written = (temp_vault / "new-note.md").read_text(encoding="utf-8")
        assert "title: New Note" in written
        assert "Content here." in written

    def test_write_note_atomic(self, core, temp_vault):
        """Test atomic write creates temp file then renames."""
        from obsidian_mcp.models import WriteNoteRequest
        req = WriteNoteRequest(
            path="atomic.md",
            content="Atomic write",
            atomic=True
        )
        core.write_note(req)
        
        assert (temp_vault / "atomic.md").exists()
        assert not (temp_vault / "atomic.md.tmp").exists()

    def test_write_note_creates_dirs(self, core, temp_vault):
        """Test write_note creates parent directories."""
        from obsidian_mcp.models import WriteNoteRequest
        req = WriteNoteRequest(
            path="new/dir/structure.md",
            content="Nested",
            create_dirs=True
        )
        core.write_note(req)
        
        assert (temp_vault / "new" / "dir" / "structure.md").exists()

    def test_write_note_rejects_no_create_dirs(self, core):
        """Test write fails when parent dirs don't exist and create_dirs=False."""
        from obsidian_mcp.models import WriteNoteRequest
        req = WriteNoteRequest(
            path="missing/parent.md",
            content="Test",
            create_dirs=False
        )
        with pytest.raises(FileNotFoundError):
            core.write_note(req)


class TestListNotes:
    """Test list_notes functionality."""

    def test_list_root(self, core, temp_vault):
        """Test listing notes in vault root."""
        from obsidian_mcp.models import ListNotesRequest
        req = ListNotesRequest(path=".", recursive=False)
        resp = core.list_notes(req)
        
        assert resp.path == "."
        assert resp.total >= 3  # note1, note2, no-frontmatter
        names = {e.name for e in resp.entries}
        assert "note1.md" in names
        assert "note2.md" in names

    def test_list_recursive(self, core, temp_vault):
        """Test recursive listing finds nested notes."""
        from obsidian_mcp.models import ListNotesRequest
        req = ListNotesRequest(path=".", recursive=True)
        resp = core.list_notes(req)
        
        assert resp.total >= 4  # includes subdir/note3.md
        paths = {e.path for e in resp.entries}
        # Windows uses backslashes in paths
        assert any("note3.md" in p for p in paths)

    def test_list_with_frontmatter(self, core, temp_vault):
        """Test listing includes frontmatter when requested."""
        from obsidian_mcp.models import ListNotesRequest
        req = ListNotesRequest(path=".", recursive=True, include_frontmatter=True)
        resp = core.list_notes(req)
        
        # Find note1.md entry
        entry = next(e for e in resp.entries if e.name == "note1.md")
        assert entry.frontmatter == {"title": "Test Note 1", "tags": ["test", "example"]}

    def test_list_nonexistent_dir(self, core):
        """Test listing non-existent directory raises FileNotFoundError."""
        from obsidian_mcp.models import ListNotesRequest
        req = ListNotesRequest(path="does-not-exist")
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            core.list_notes(req)


class TestSearchNotes:
    """Test search_notes functionality."""

    def test_search_simple_pattern(self, core, temp_vault):
        """Test basic regex search."""
        from obsidian_mcp.models import SearchNotesRequest
        req = SearchNotesRequest(pattern="Test Note", path=".", max_results=10)
        resp = core.search_notes(req)
        
        assert resp.total >= 2
        assert all("Test Note" in m.match for m in resp.matches)

    def test_search_case_insensitive(self, core, temp_vault):
        """Test case-insensitive search."""
        from obsidian_mcp.models import SearchNotesRequest
        req = SearchNotesRequest(pattern="test note", path=".", case_sensitive=False, max_results=10)
        resp = core.search_notes(req)
        
        assert resp.total >= 2

    def test_search_case_sensitive(self, core, temp_vault):
        """Test case-sensitive search."""
        from obsidian_mcp.models import SearchNotesRequest
        # The fixture content has "test note" in lowercase in the body text
        # Use a pattern that only matches uppercase
        req = SearchNotesRequest(pattern="Test Note", path=".", case_sensitive=True, max_results=10)
        resp = core.search_notes(req)
        
        assert resp.total >= 2  # Should match "Test Note" in titles

    def test_search_with_context(self, core, temp_vault):
        """Test search returns context lines."""
        from obsidian_mcp.models import SearchNotesRequest
        req = SearchNotesRequest(pattern="Test Note", path=".", context_lines=1, max_results=10)
        resp = core.search_notes(req)
        
        assert resp.total >= 2
        for match in resp.matches:
            assert len(match.context_before) <= 1
            assert len(match.context_after) <= 1

    def test_search_max_results(self, core, temp_vault):
        """Test max_results limits output."""
        from obsidian_mcp.models import SearchNotesRequest
        req = SearchNotesRequest(pattern="test", path=".", max_results=1, case_sensitive=False)
        resp = core.search_notes(req)
        
        assert resp.total <= 1
        assert resp.truncated is True

    def test_search_nonexistent_dir(self, core):
        """Test search in non-existent directory raises FileNotFoundError."""
        from obsidian_mcp.models import SearchNotesRequest
        req = SearchNotesRequest(pattern="test", path="does-not-exist")
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            core.search_notes(req)


class TestSearchFrontmatter:
    """Test search_frontmatter functionality."""

    def test_search_frontmatter_eq(self, core, temp_vault):
        """Test frontmatter equality search."""
        from obsidian_mcp.models import SearchFrontmatterRequest
        req = SearchFrontmatterRequest(key="title", value="Test Note 1", operator="eq", path=".")
        resp = core.search_frontmatter(req)
        
        assert resp.total == 1
        assert resp.matches[0].file == "note1.md"

    def test_search_frontmatter_contains(self, core, temp_vault):
        """Test frontmatter substring search."""
        from obsidian_mcp.models import SearchFrontmatterRequest
        req = SearchFrontmatterRequest(key="tags", value="test", operator="contains", path=".")
        resp = core.search_frontmatter(req)
        
        assert resp.total >= 2  # Both notes have "test" in tags

    def test_search_frontmatter_exists(self, core, temp_vault):
        """Test frontmatter key existence search."""
        from obsidian_mcp.models import SearchFrontmatterRequest
        req = SearchFrontmatterRequest(key="status", operator="exists", path=".")
        resp = core.search_frontmatter(req)
        
        assert resp.total == 1  # Only note2.md has status
        assert resp.matches[0].file == "note2.md"

    def test_search_frontmatter_no_match(self, core, temp_vault):
        """Test frontmatter search with no matches."""
        from obsidian_mcp.models import SearchFrontmatterRequest
        req = SearchFrontmatterRequest(key="nonexistent", value="value", operator="eq", path=".")
        resp = core.search_frontmatter(req)
        
        assert resp.total == 0


class TestDailyNote:
    """Test get_daily_note functionality."""

    def test_get_existing_daily_note(self, core, temp_vault):
        """Test getting an existing daily note."""
        from obsidian_mcp.models import DailyNoteRequest
        req = DailyNoteRequest(date="2026-01-15")
        resp = core.get_daily_note(req)
        
        assert resp.date == "2026-01-15"
        assert resp.created is False
        assert "Today I did things" in resp.content

    def test_create_daily_note(self, core, temp_vault):
        """Test creating a new daily note."""
        from obsidian_mcp.models import DailyNoteRequest
        req = DailyNoteRequest(date="2026-01-16", create_if_missing=True)
        resp = core.get_daily_note(req)
        
        assert resp.date == "2026-01-16"
        assert resp.created is True
        assert (temp_vault / "Daily Notes" / "2026-01-16.md").exists()

    def test_create_daily_note_with_frontmatter(self, core, temp_vault):
        """Test created daily note has date frontmatter."""
        from obsidian_mcp.models import DailyNoteRequest
        req = DailyNoteRequest(date="2026-01-17", create_if_missing=True)
        resp = core.get_daily_note(req)
        
        assert resp.frontmatter == {"date": "2026-01-17"}

    def test_reject_missing_daily_note(self, core):
        """Test missing daily note raises FileNotFoundError when create_if_missing=False."""
        from obsidian_mcp.models import DailyNoteRequest
        req = DailyNoteRequest(date="2026-02-01", create_if_missing=False)
        with pytest.raises(FileNotFoundError, match="Daily note not found"):
            core.get_daily_note(req)

    def test_reject_invalid_date_format(self, core):
        """Test invalid date format raises ValueError."""
        from obsidian_mcp.models import DailyNoteRequest
        req = DailyNoteRequest(date="01-15-2026")  # Wrong format
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            core.get_daily_note(req)