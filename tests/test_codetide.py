from codetide.core.models import CodeBase, CodeFileModel
from codetide import CodeTide

from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
import pytest
import time
import os

# Fixture to create a temporary directory structure for testing
@pytest.fixture
def temp_code_root(tmp_path):
    """Creates a temporary directory with a mock project structure."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')")
    (root / "src" / "utils.js").write_text("console.log('utils');")
    (root / "README.md").write_text("# Project")
    (root / ".gitignore").write_text("*.log\n__pycache__/\n.env")
    (root / "ignored_file.log").write_text("this is a log")
    (root / ".env").write_text("SECRET=123")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "cache_file.pyc").write_text("cached")
    return root

@pytest.mark.asyncio
async def test_find_code_files_with_git(temp_code_root):
    """
    Tests that _find_code_files correctly identifies files using git,
    respecting .gitignore.
    """
    # Initialize a git repository in the temp directory
    os.chdir(temp_code_root)
    os.system("git init")
    os.system("git add .")
    os.system("git commit -m 'initial commit'")

    # Create an untracked file that should be ignored
    (temp_code_root / "untracked.log").write_text("untracked log")

    # Create an untracked file that should be included
    (temp_code_root / "new_feature.py").write_text("def new_func(): pass")
    
    tide = CodeTide(rootpath=temp_code_root)
    
    # We use a patch to avoid depending on a real git installation in the test runner
    with patch('pygit2.Repository') as mock_repo:
        # Mock the repository and its status to simulate git behavior
        mock_repo.return_value.workdir = str(temp_code_root)
        mock_repo.return_value.index = [MagicMock(path="src/main.py"), MagicMock(path="src/utils.js"), MagicMock(path="README.md")]
        mock_repo.return_value.status.return_value = {"new_feature.py": 1, "untracked.log": 128} # 1 = WT_NEW, 128 = IGNORED
        mock_repo.return_value.path_is_ignored = lambda x: x == 'untracked.log'
        
        found_files = tide._find_code_files()

        # Assert that the correct files were found and ignored files were excluded
        assert temp_code_root / "src" / "main.py" in found_files
        assert temp_code_root / "src" / "utils.js" in found_files
        assert temp_code_root / "README.md" in found_files
        assert temp_code_root / "new_feature.py" not in found_files
        assert temp_code_root / ".gitignore" not in found_files # .gitignore is not a code file by default
        assert temp_code_root / "untracked.log" not in found_files

def test_find_code_files_no_git(temp_code_root):
    """
    Tests _find_code_files fallback to a simple directory walk when not a git repo.
    """
    tide = CodeTide(rootpath=temp_code_root)
    found_files = tide._find_code_files(languages=['python', 'javascript'])
    
    # Assert that only files with the specified extensions are found
    assert temp_code_root / "src/main.py" in found_files
    assert temp_code_root / "src/utils.js" in found_files
    assert temp_code_root / "README.md" not in found_files
    assert len(found_files) == 2

def test_organize_files_by_language(temp_code_root):
    """
    Tests that _organize_files_by_language correctly groups files by their language.
    """
    files = [
        temp_code_root / "src/main.py",
        temp_code_root / "src/utils.js",
        temp_code_root / "README.md"
    ]
    organized = CodeTide._organize_files_by_language(files)
    
    # Assert that files are grouped under the correct language key
    assert "python" in organized
    assert "javascript" in organized
    assert "markdown" in organized
    assert organized["python"] == [temp_code_root / "src/main.py"]
    assert organized["javascript"] == [temp_code_root / "src/utils.js"]
    assert organized["markdown"] == [temp_code_root / "README.md"]

def test_serialize_deserialize(temp_code_root):
    """
    Tests the serialization and deserialization of a CodeTide instance.
    """
    tide = CodeTide(rootpath=temp_code_root, codebase=CodeBase(root=[CodeFileModel(file_path="test.py")]))
    tide.files = {temp_code_root / "test.py": datetime.now(timezone.utc)}
    
    serialization_path = temp_code_root / "storage" / "tide.json"
    tide.serialize(filepath=serialization_path, store_in_project_root=False)

    # Assert that the serialization file was created
    assert serialization_path.exists()
    
    deserialized_tide = CodeTide.deserialize(filepath=serialization_path)

    # Assert that the deserialized instance is of the correct type and has the correct data
    assert isinstance(deserialized_tide, CodeTide)
    assert deserialized_tide.rootpath == temp_code_root
    assert len(deserialized_tide.codebase.root) == 1
    assert deserialized_tide.codebase.root[0].file_path == "test.py"
    # Note: Pydantic converts Path objects to strings on serialization, so we compare strings
    assert str(temp_code_root / "test.py") in [str(p) for p in deserialized_tide.files.keys()]


@pytest.mark.asyncio
async def test_check_for_updates(temp_code_root):
    """
    Tests the check_for_updates method to detect new, modified, and deleted files.
    """
    # Mock the parser and its processing methods to isolate the test to file detection logic
    with patch('codetide.parsers.PythonParser.parse_file') as mock_parse, \
         patch('codetide.parsers.PythonParser.resolve_inter_files_dependencies'), \
         patch('codetide.parsers.PythonParser.resolve_intra_file_dependencies'):

        mock_parse.return_value = CodeFileModel(file_path=str(temp_code_root / "src/main.py"))
        
        tide = await CodeTide.from_path(temp_code_root)
        initial_file_count = len(tide.files)
        assert temp_code_root / "src/main.py" in tide.files

        # 1. Test file modification
        time.sleep(0.1) # Ensure modification time is different
        (temp_code_root / "src/main.py").write_text("print('updated')")
        
        changed_files, deletion_detected = tide._get_changed_files()
        assert not deletion_detected
        assert temp_code_root / "src/main.py" in changed_files

        # 2. Test new file creation
        (temp_code_root / "src/new_file.py").write_text("pass")
        mock_parse.return_value = CodeFileModel(file_path=str(temp_code_root / "src/new_file.py"))
        
        await tide.check_for_updates(serialize=False)
        assert len(tide.files) == initial_file_count + 1
        assert temp_code_root / "src/new_file.py" in tide.files

        # 3. Test file deletion
        (temp_code_root / "src/main.py").unlink()
        
        # Mock the reset method to verify it gets called on deletion
        with patch.object(tide, '_reset', new_callable=AsyncMock) as mock_reset:
             await tide.check_for_updates(serialize=False)
             mock_reset.assert_called_once()
             
@pytest.mark.asyncio
async def test_from_path_initialization(temp_code_root):
    """
    Tests the basic initialization of CodeTide using the from_path classmethod.
    This is a high-level test to ensure the factory method runs without crashing.
    """
    # Mock the parser to avoid dependency on tree-sitter binaries
    with patch('codetide.parsers.PythonParser.parse_file') as mock_parse:
        mock_parse.return_value = CodeFileModel(file_path="mock.py")
        
        tide = await CodeTide.from_path(temp_code_root)
        
        # Assert that the CodeTide instance was created with the correct rootpath
        assert tide.rootpath == temp_code_root
        # Assert that some files were found (the exact number depends on the mock setup)
        assert len(tide.files) > 0
        assert len(tide.codebase.root) > 0
