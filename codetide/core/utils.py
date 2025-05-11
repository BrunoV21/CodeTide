from codetide.core.defaults import DEFAULT_ENCODINGS, LANGUAGE_EXTENSIONS, DEFAULT_IGNORE_PATTERNS

from typing import List, Dict, Optional, Union, Any
from functools import lru_cache
from pathlib import Path
import fnmatch
import logging

# Setup logging
logger = logging.getLogger(__name__)

def get_language_from_extension(file_path: Union[str, Path]) -> Optional[str]:
    """
    Determine the programming language based on file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language name or None if not recognized
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    extension = file_path.suffix.lower()
    
    for language, extensions in LANGUAGE_EXTENSIONS.items():
        if extension in extensions:
            return language
    
    return None


def read_file_content(file_path: Union[str, Path]) -> Optional[str]:
    """
    Read the content of a file, trying different encodings.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File content as a string, or None if reading fails
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"File does not exist or is not a regular file: {file_path}")
        return None
    
    # Try different encodings
    for encoding in DEFAULT_ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    
    logger.warning(f"Could not decode file with any of the default encodings: {file_path}")
    return None


def should_ignore_file(file_path: Union[str, Path], ignore_patterns: List[str] = None) -> bool:
    """
    Check if a file should be ignored based on patterns.
    
    Args:
        file_path: Path to the file
        ignore_patterns: List of glob patterns to ignore
        
    Returns:
        True if the file should be ignored, False otherwise
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS
    
    # Check if any part of the path matches any ignore pattern
    path_str = str(file_path)
    for pattern in ignore_patterns:
        if any(fnmatch.fnmatch(part, pattern) for part in file_path.parts):
            return True
        if fnmatch.fnmatch(path_str, pattern):
            return True
    
    return False


def find_code_files(root_path: Union[str, Path], languages: List[str] = None, 
                   ignore_patterns: List[str] = None) -> List[Path]:
    """
    Find all code files in a directory tree.
    
    Args:
        root_path: Root directory to search
        languages: List of languages to include (None for all supported languages)
        ignore_patterns: List of glob patterns to ignore
        
    Returns:
        List of paths to code files
    """
    if isinstance(root_path, str):
        root_path = Path(root_path)
    
    if not root_path.exists() or not root_path.is_dir():
        logger.error(f"Root path does not exist or is not a directory: {root_path}")
        return []
    
    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS
    
    # Get relevant extensions
    extensions = []
    if languages:
        for lang in languages:
            if lang in LANGUAGE_EXTENSIONS:
                extensions.extend(LANGUAGE_EXTENSIONS[lang])
    else:
        # Use all supported extensions
        for exts in LANGUAGE_EXTENSIONS.values():
            extensions.extend(exts)
    
    # Find all files with relevant extensions
    code_files = []
    for file_path in root_path.glob('**/*'):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            if not should_ignore_file(file_path, ignore_patterns):
                code_files.append(file_path)
    
    return code_files


@lru_cache(maxsize=1024)
def get_relative_path(file_path: Path, base_path: Path) -> Path:
    """
    Get the path of a file relative to a base path.
    
    Args:
        file_path: Path of the file
        base_path: Base path
        
    Returns:
        Relative path
    """
    try:
        return file_path.relative_to(base_path)
    except ValueError:
        # Return the absolute path if the file is not under the base path
        return file_path.absolute()


def generate_module_structure(root_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Generate a dictionary representing the module structure of a codebase.
    
    Args:
        root_path: Root directory of the codebase
        
    Returns:
        Dictionary with module structure
    """
    if isinstance(root_path, str):
        root_path = Path(root_path)
    
    if not root_path.exists() or not root_path.is_dir():
        logger.error(f"Root path does not exist or is not a directory: {root_path}")
        return {}
    
    # Find all code files
    code_files = find_code_files(root_path)
    
    # Build module structure
    module_structure = {
        'name': root_path.name,
        'path': str(root_path),
        'modules': {},
        'files': []
    }
    
    for file_path in code_files:
        rel_path = get_relative_path(file_path, root_path)
        parts = rel_path.parts
        
        # Skip files at the root level
        if len(parts) == 1:
            module_structure['files'].append({
                'name': parts[0],
                'path': str(file_path),
                'language': get_language_from_extension(file_path)
            })
            continue
        
        # Navigate the module structure for this file
        current = module_structure
        for i, part in enumerate(parts[:-1]):
            if i == 0:
                if part not in current['modules']:
                    current['modules'][part] = {
                        'name': part,
                        'path': str(root_path / part),
                        'modules': {},
                        'files': []
                    }
                current = current['modules'][part]
            else:
                if part not in current['modules']:
                    current['modules'][part] = {
                        'name': part,
                        'path': str(root_path / '/'.join(parts[:i+1])),
                        'modules': {},
                        'files': []
                    }
                current = current['modules'][part]
        
        # Add the file to the current module
        current['files'].append({
            'name': parts[-1],
            'path': str(file_path),
            'language': get_language_from_extension(file_path)
        })
    
    return module_structure