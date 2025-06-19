from codetide.core.common import readFile, writeFile, wrap_content, wrap_package_dependencies
from codetide.core.defaults import DEFAULT_ENCODING

import pytest

@pytest.fixture
def tmp_text_file(tmp_path):
    file_path = tmp_path / "example.txt"
    content = "Sample content for testing."
    file_path.write_text(content, encoding=DEFAULT_ENCODING)
    return file_path, content

def test_readFile_reads_text_correctly(tmp_text_file):
    file_path, original_content = tmp_text_file
    result = readFile(file_path)
    assert result == original_content

def test_readFile_reads_binary_correctly(tmp_path):
    file_path = tmp_path / "binary.bin"
    data = b"\x00\x01\x02text\xff"
    file_path.write_bytes(data)
    result = readFile(file_path, mode="rb")
    assert result == data

def test_writeFile_writes_text_correctly(tmp_path):
    file_path = tmp_path / "output.txt"
    content = "This is written content."
    writeFile(content, file_path)
    assert file_path.read_text(encoding=DEFAULT_ENCODING) == content

@pytest.mark.parametrize("content", ["dependency: foo==1.2.3", "import bar", ""])
def test_wrap_package_dependencies_formats_correctly(content):
    result = wrap_package_dependencies(content)
    assert result.startswith("<PACKAGE_DEPENDENCIES_START>")
    assert result.endswith("</PACKAGE_DEPENDENCIES_END>")
    assert content in result

def test_wrap_content_for_packages_uses_wrap_package_dependencies():
    content = "package_content"
    wrapped = wrap_content(content, "PACKAGES")
    assert "<PACKAGE_DEPENDENCIES_START>" in wrapped
    assert content in wrapped

def test_wrap_content_for_regular_file():
    content = "def foo(): pass"
    filepath = "src/module.py"
    wrapped = wrap_content(content, filepath)
    assert wrapped.startswith(f"<FILE_START::{filepath}>")
    assert wrapped.endswith(f"</FILE_END::{filepath}>")
    assert content in wrapped