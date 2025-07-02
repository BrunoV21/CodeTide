from codetide.mcp.tools.apply_patch import (
    DiffError,
    process_patch
)

from typing import Dict
import pytest
import re

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


def test_error_invalid_line_in_update(mock_fs):
    patch = """*** Begin Patch
*** Update File: main.py
@@ def hello():
this line is invalid
*** End Patch
"""
    with pytest.raises(DiffError, match=r"must start with '\+', '-', or ' '"):
        mock_fs.apply_patch(patch)