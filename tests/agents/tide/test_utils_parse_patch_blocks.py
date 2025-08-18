from codetide.mcp.tools.patch_code.parser import peek_next_section
from codetide.mcp.tools.apply_patch import (
    DiffError,
    process_patch
)

from pathlib import Path
import tempfile
import pytest
import re

class MockFileSystem:
    """Mock filesystem for testing with temporary files."""
    
    def __init__(self):
        # Create a temporary directory for our test files
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)
        
        # Pre-populate with some files
        self._create_file('main.py', (
            "def hello():\n"
            "    print('Hello, world!')\n"
            "\n"
            "def goodbye():\n"
            "    print('Goodbye, world!')\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    hello()\n"
        ))
        
        self._create_file('data/old_data.txt', "line1\nline2\nline3\n")
        self._create_file('empty.txt', "")
        self._create_file('utils.py', "# A utility file.\n")
        self._create_file('fuzzy.py', "  def my_func( a, b ):  \n    return a+b\n")

    def _create_file(self, relative_path: str, content: str):
        """Create a file with the given content."""
        file_path = self.base_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    def mock_open(self, path: str) -> str:
        """Mock open function that reads files relative to base_path."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.base_path / path
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_text()

    def mock_write(self, path: str, content: str) -> None:
        """Mock write function that writes files relative to base_path."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.base_path / path
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    def mock_remove(self, path: str) -> None:
        """Mock remove function that deletes files relative to base_path."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.base_path / path
        
        if file_path.exists():
            file_path.unlink()

    def mock_exists(self, path: str) -> bool:
        """Mock exists function that checks files relative to base_path."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.base_path / path
        
        return file_path.exists()

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists."""
        return (self.base_path / relative_path).exists()

    def read_file(self, relative_path: str) -> str:
        """Read file content."""
        return (self.base_path / relative_path).read_text()

    def apply_patch(self, patch_text: str):
        """Helper to run the whole process against the temp filesystem."""
        # Write patch content to a temporary patch file
        patch_file = self.base_path / "temp_patch.patch"
        patch_file.write_text(patch_text)
        
        return process_patch(
            str(patch_file),
            self.mock_open,
            self.mock_write,
            self.mock_remove,
            self.mock_exists,
        )

    def cleanup(self):
        """Clean up the temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
def mock_fs():
    """Fixture providing a fresh mock filesystem for each test."""
    fs = MockFileSystem()
    yield fs
    fs.cleanup()


def test_add_file(mock_fs):
    patch = """*** Begin Patch
*** Add File: new_module.py
+import os
+
+def new_function():
+    return os.getcwd()
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert mock_fs.file_exists('new_module.py')
    expected_content = "import os\n\ndef new_function():\n    return os.getcwd()\n"
    assert mock_fs.read_file('new_module.py') == expected_content


def test_delete_file(mock_fs):
    assert mock_fs.file_exists('utils.py')
    patch = """*** Begin Patch
*** Delete File: utils.py
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert not mock_fs.file_exists('utils.py')


def test_update_middle_of_file(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ def goodbye():
-    print('Goodbye, world!')
+    # A new and improved goodbye
+    print('Farewell, cruel world!')
*** End Patch
"""
    mock_fs.apply_patch(patch)
    content = mock_fs.read_file('main.py')
    assert "Farewell, cruel world!" in content
    assert "Goodbye, world!" not in content


def test_update_start_of_file(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ def hello():
-def hello():
-    print('Hello, world!')
+def new_hello():
+    print('Greetings, planet!')
*** End Patch
"""
    mock_fs.apply_patch(patch)
    content = mock_fs.read_file('main.py')
    assert "Greetings, planet!" in content
    assert "Hello, world!" not in content
    expected = (
        "def new_hello():\n"
        "    print('Greetings, planet!')\n"
        "\n"
        "def goodbye():\n"
        "    print('Goodbye, world!')\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    hello()\n"
    )
    assert content == expected


def test_update_end_of_file_marker(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ if __name__ == '__main__':
-    hello()
+    # A new entrypoint
+    goodbye()
*** End of File
*** End Patch
"""
    mock_fs.apply_patch(patch)
    content = mock_fs.read_file('main.py')
    assert "goodbye()" in content
    assert "    hello()" not in content
    assert content.endswith("goodbye()\n")


def test_rename_file(mock_fs):
    # The original file has "line1\nline2\nline3\n"
    # We need to match this content exactly
    patch = """*** Begin Patch
*** Update File: data/old_data.txt
*** Move to: data/new_data.txt
@@ line1
 line1
-line2
+line_two
*** End of File
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert not mock_fs.file_exists('data/old_data.txt')
    assert mock_fs.file_exists('data/new_data.txt')
    assert mock_fs.read_file('data/new_data.txt') == "line1\nline_two\nline3\n"


def test_crlf_handling(mock_fs):
    mock_fs._create_file('crlf.txt', "line one\r\nline two\r\nline three\r\n")
    patch = """*** Begin Patch
*** Update File: crlf.txt
@@ line one
 line one
-line two
+line 2
*** End of File
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert mock_fs.read_file('crlf.txt') == "line one\nline 2\nline three\n"

def test_peek_next_section_basic():
    """Test the basic functionality of peek_next_section"""
    lines = [
        " line1",         # keep (note: single space prefix)
        "-line2",         # delete  
        "+line_two",      # add
        " line3",         # keep
        "*** End of File"
    ]
    
    context_lines, chunks, index, is_eof = peek_next_section(lines, 0)
    
    # context_lines should contain the original content (keep + delete lines)
    # The content is the part after the prefix character
    assert context_lines == ["line1", "line2"]
    
    # Should have one chunk with the change
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.del_lines == ["line2"]
    assert chunk.ins_lines == ["line_two"]
    assert chunk.orig_index == 1  # Position where the change occurs
    
    assert is_eof is True
    assert index == 5  # Should point past the "*** End of File" line


def test_peek_next_section_multiple_changes():
    """Test peek_next_section with multiple change blocks"""
    lines = [
        " line1",         # keep
        "-line2",         # delete  
        "+line_two",      # add
        " line3",         # keep
        "-line4",         # delete
        "+line_four",     # add
        " line5",         # keep
        "*** End of File"
    ]
    
    context_lines, chunks, index, is_eof = peek_next_section(lines, 0)
    
    # context_lines should contain original content (keep + delete lines)
    assert context_lines == ["line1", "line2", "line3", "line4"]
    
    # Should have two chunks
    assert len(chunks) == 2
    
    # First chunk
    assert chunks[0].del_lines == ["line2"]
    assert chunks[0].ins_lines == ["line_two"]
    assert chunks[0].orig_index == 1
    
    # Second chunk  
    assert chunks[1].del_lines == ["line4"]
    assert chunks[1].ins_lines == ["line_four"]
    assert chunks[1].orig_index == 3  # Position in original content


def test_peek_next_section_trailing_keep_lines():
    """Test that trailing keep lines are handled correctly"""
    lines = [
        "-line1",         # delete  
        "+line_one",      # add
        " line2",         # keep
        " line3",         # keep - these are trailing
        " line4",         # keep - these are trailing
        "*** End of File"
    ]
    
    context_lines, chunks, index, is_eof = peek_next_section(lines, 0)
    
    # All lines should be in context_lines (original content)
    assert context_lines == ["line1"]
    
    # Should have one chunk
    assert len(chunks) == 1
    assert chunks[0].del_lines == ["line1"]
    assert chunks[0].ins_lines == ["line_one"]
    assert chunks[0].orig_index == 0


def test_peek_next_section_only_keep_lines():
    """Test what happens with only keep lines (no changes)"""
    lines = [
        " line1",         # keep
        " line2",         # keep
        " line3",         # keep
        "*** End of File"
    ]
    
    context_lines, chunks, index, is_eof = peek_next_section(lines, 0)
    
    # All lines should be in context_lines
    assert context_lines == ["line1", "line2", "line3"]
    
    # Should have no chunks since there are no changes
    assert len(chunks) == 0
    
    assert is_eof is True


def test_peek_next_section_empty():
    """Test with empty input"""
    lines = [
        "*** End of File"
    ]
    
    context_lines, chunks, index, is_eof = peek_next_section(lines, 0)
    
    assert context_lines == []
    assert len(chunks) == 0
    assert is_eof is True

def test_fuzzy_matching_whitespace(mock_fs):
    # The patch context has different surrounding whitespace than the original file
    patch = """*** Begin Patch
*** Update File: fuzzy.py
@@ def my_func( a, b ):
-    return a+b
+    return a * b # Now we multiply
*** End of File
*** End Patch
"""
    mock_fs.apply_patch(patch)
    content = mock_fs.read_file('fuzzy.py')
    assert "return a * b" in content


def test_full_add_update_delete_patch(mock_fs):
    patch = """*** Begin Patch
*** Add File: new_feature.py
+def feature():
+    print("New!")

*** Update File: main.py
@@ if __name__ == '__main__':
 if __name__ == '__main__':
-    hello()
+    print("Running main")
*** Delete File: utils.py
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert mock_fs.file_exists('new_feature.py')
    assert not mock_fs.file_exists('utils.py')
    content = mock_fs.read_file('main.py')
    assert 'Running main' in content
    # FIX: Make assertion more specific. Check that the *call* was removed,
    # not that the substring 'hello()' is gone from the entire file.
    assert '    hello()' not in content


# --- Error Condition Tests ---

def test_error_missing_sentinels(mock_fs):
    with pytest.raises(DiffError, match=r"must start with '\*\*\* Begin Patch'"):
        mock_fs.apply_patch("just some text\n*** End Patch\n")
    
    with pytest.raises(DiffError, match=r"must end with '\*\*\* End Patch'"):
        mock_fs.apply_patch("*** Begin Patch\n*** Add File: a.txt")


def test_error_update_nonexistent_file(mock_fs):
    patch = """*** Begin Patch
*** Update File: no_such_file.py
*** End Patch
"""
    with pytest.raises(FileNotFoundError):
        mock_fs.apply_patch(patch)


def test_error_delete_nonexistent_file(mock_fs):
    patch = """*** Begin Patch
*** Delete File: no_such_file.py
*** End Patch
"""
    with pytest.raises(FileNotFoundError):
        mock_fs.apply_patch(patch)


def test_error_add_existing_file(mock_fs):
    patch = """*** Begin Patch
*** Add File: main.py
+print("overwrite!")
*** End Patch
"""
    with pytest.raises(DiffError, match="file already exists: main.py"):
        mock_fs.apply_patch(patch)


def test_error_duplicate_action(mock_fs):
    patch = """*** Begin Patch
*** Delete File: utils.py
*** Delete File: utils.py
*** End Patch
"""
    with pytest.raises(DiffError, match="Duplicate delete for file: utils.py"):
        mock_fs.apply_patch(patch)


def test_error_context_not_found(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ some nonexistent context
-foo
+bar
*** End Patch
"""
    with pytest.raises(DiffError, match="could not find initial context line"):
        mock_fs.apply_patch(patch)


def test_error_second_context_not_found(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ def hello():
-    print('Hello, world!')
+    print('Hello, new world!')
@@ this context does not exist
-goodbye
+farewell
*** End Patch
"""
    with pytest.raises(DiffError, match=re.escape("could not find context block")):
        mock_fs.apply_patch(patch)


def test_error_move_to_existing_file(mock_fs):
    patch = """*** Begin Patch
*** Update File: utils.py
*** Move to: main.py
@@ # A utility file.
-# A utility file.
+# Overwrite main!
*** End of File
*** End Patch
"""
    with pytest.raises(DiffError, match="Cannot move 'utils.py' to 'main.py' because the target file already exists"):
        mock_fs.apply_patch(patch)