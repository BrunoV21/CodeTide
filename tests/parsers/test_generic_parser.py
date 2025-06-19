from codetide.parsers.generic_parser import GenericParser
from codetide.core.models import CodeFileModel

import asyncio
import pytest

class TestGenericParser:
    @pytest.fixture
    def parser(self):
        return GenericParser()

    def test_language_property(self, parser):
        """Test that language property returns 'any'"""
        assert parser.language == "any"

    def test_extension_property(self, parser):
        """Test that extension property returns empty string"""
        assert parser.extension == ""

    def test_tree_parser_property(self, parser):
        """Test that tree_parser property returns None"""
        assert parser.tree_parser is None

    def test_import_statement_template(self, parser):
        """Test that import_statement_template returns None"""
        assert parser.import_statement_template(None) is None

    @pytest.mark.asyncio
    async def test_parse_file_with_absolute_path(self, parser, tmp_path):
        """Test parsing a file with absolute path"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        result = await parser.parse_file(test_file)
        assert isinstance(result, CodeFileModel)
        assert result.file_path == str(test_file)
        assert not result.imports
        assert not result.variables
        assert not result.functions
        assert not result.classes

    @pytest.mark.asyncio
    async def test_parse_file_with_relative_path(self, parser, tmp_path):
        """Test parsing a file with relative path and root_path"""
        # Create a test directory structure
        root_dir = tmp_path / "project"
        root_dir.mkdir()
        test_file = root_dir / "test.txt"
        test_file.write_text("test content")
        
        # Get relative path from within the project
        rel_path = test_file.relative_to(root_dir)
        
        result = await parser.parse_file(test_file, root_path=root_dir)
        assert isinstance(result, CodeFileModel)
        assert result.file_path == str(rel_path)

    @pytest.mark.asyncio
    async def test_parse_file_with_string_path(self, parser, tmp_path):
        """Test parsing a file with string path"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        result = await parser.parse_file(str(test_file))
        assert isinstance(result, CodeFileModel)
        assert result.file_path == str(test_file)

    def test_parse_code(self, parser, tmp_path):
        """Test the synchronous parse_code method"""
        test_file = tmp_path / "test.txt"
        result = parser.parse_code(test_file)
        assert isinstance(result, CodeFileModel)
        assert result.file_path == str(test_file)

    def test_resolve_inter_files_dependencies(self, parser):
        """Test that resolve_inter_files_dependencies does nothing"""
        # Should not raise any exceptions
        parser.resolve_inter_files_dependencies(None)

    def test_resolve_intra_file_dependencies(self, parser):
        """Test that resolve_intra_file_dependencies does nothing"""
        # Should not raise any exceptions
        parser.resolve_intra_file_dependencies([])

    @pytest.mark.asyncio
    async def test_concurrent_parsing(self, parser, tmp_path):
        """Test that parser can handle concurrent requests"""
        files = [tmp_path / f"test_{i}.txt" for i in range(5)]
        for file in files:
            file.write_text("content")

        # Parse all files concurrently
        tasks = [parser.parse_file(file) for file in files]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert isinstance(result, CodeFileModel)

    def test_filepath_attribute(self, parser):
        """Test that _filepath attribute exists and is None by default"""
        assert hasattr(parser, '_filepath')
        assert parser._filepath is None