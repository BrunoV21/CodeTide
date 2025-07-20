from codetide.mcp.tools.apply_patch import (
    DiffError,
    process_patch
)

from typing import Dict
import pytest
import re

from codetide.mcp.tools.patch_code.parser import peek_next_section

class MockFileSystem:
    """Mock filesystem for testing."""
    
    def __init__(self):
        self.fs: Dict[str, str] = {}
        # Pre-populate with some files
        self.fs['main.py'] = (
            "def hello():\n"
            "    print('Hello, world!')\n"
            "\n"
            "def goodbye():\n"
            "    print('Goodbye, world!')\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    hello()\n"
        )
        self.fs['data/old_data.txt'] = "line1\nline2\nline3\n"
        self.fs['empty.txt'] = ""
        self.fs['utils.py'] = "# A utility file.\n"
        self.fs['fuzzy.py'] = "  def my_func( a, b ):  \n    return a+b\n"

    def mock_open(self, path: str) -> str:
        if path not in self.fs:
            raise FileNotFoundError(f"File not found in mock filesystem: {path}")
        return self.fs[path]

    def mock_write(self, path: str, content: str) -> None:
        self.fs[path] = content

    def mock_remove(self, path: str) -> None:
        if path in self.fs:
            del self.fs[path]

    def mock_exists(self, path: str) -> bool:
        return path in self.fs

    def apply_patch(self, patch_text: str):
        """Helper to run the whole process against the mock fs."""
        return process_patch(
            patch_text,
            self.mock_open,
            self.mock_write,
            self.mock_remove,
            self.mock_exists,
        )


@pytest.fixture
def mock_fs():
    """Fixture providing a fresh mock filesystem for each test."""
    return MockFileSystem()


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
    assert 'new_module.py' in mock_fs.fs
    expected_content = "import os\n\ndef new_function():\n    return os.getcwd()\n"
    assert mock_fs.fs['new_module.py'] == expected_content


def test_delete_file(mock_fs):
    assert 'utils.py' in mock_fs.fs
    patch = """*** Begin Patch
*** Delete File: utils.py
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert 'utils.py' not in mock_fs.fs


def test_update_middle_of_file(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ def goodbye():
-    print('Goodbye, world!')
+    # A new and improved goodbye
+    print('Farewell, cruel world!')
 
 if __name__ == '__main__':
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert "Farewell, cruel world!" in mock_fs.fs['main.py']
    assert "Goodbye, world!" not in mock_fs.fs['main.py']


def test_update_start_of_file(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ def hello():
-def hello():
-    print('Hello, world!')
+def new_hello():
+    print('Greetings, planet!')
 
 def goodbye():
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert "Greetings, planet!" in mock_fs.fs['main.py']
    assert "Hello, world!" not in mock_fs.fs['main.py']
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
    assert mock_fs.fs['main.py'] == expected


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
    assert "goodbye()" in mock_fs.fs['main.py']
    assert "    hello()" not in mock_fs.fs['main.py']
    assert mock_fs.fs['main.py'].endswith("goodbye()\n")


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
 line3
*** End of File
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert 'data/old_data.txt' not in mock_fs.fs
    assert 'data/new_data.txt' in mock_fs.fs
    assert mock_fs.fs['data/new_data.txt'] == "line1\nline_two\nline3\n"


def test_crlf_handling(mock_fs):
    mock_fs.fs['crlf.txt'] = "line one\r\nline two\r\nline three\r\n"
    patch = """*** Begin Patch
*** Update File: crlf.txt
@@ line one
 line one
-line two
+line 2
 line three
*** End of File
*** End Patch
"""
    mock_fs.apply_patch(patch)
    assert mock_fs.fs['crlf.txt'] == "line one\nline 2\nline three\n"

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
    assert "return a * b" in mock_fs.fs['fuzzy.py']


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
    assert 'new_feature.py' in mock_fs.fs
    assert 'utils.py' not in mock_fs.fs
    assert 'Running main' in mock_fs.fs['main.py']
    # FIX: Make assertion more specific. Check that the *call* was removed,
    # not that the substring 'hello()' is gone from the entire file.
    assert '    hello()' not in mock_fs.fs['main.py']


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


def test_error_invalid_line_in_add(mock_fs):
    patch = """*** Begin Patch
*** Add File: a.txt
 this line is invalid
+but this one is ok
*** End Patch
"""
    with pytest.raises(DiffError, match=r"Unknown or malformed action line"):
        mock_fs.apply_patch(patch)