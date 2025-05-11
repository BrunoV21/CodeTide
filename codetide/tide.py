from codetide.core.utils import find_code_files, get_language_from_extension, read_file_content
from codetide.core.defaults import DEFAULT_IGNORE_PATTERNS
from codetide.parsers.python_parser import PythonParser
from codetide.core.models import CodeBase

from typing import List, Union
from pathlib import Path
from tqdm import tqdm
import logging

# Setup logging
logger = logging.getLogger(__name__)

class CodeTide:
    """
    Class for parsing an entire project and building a CodeBase model.
    """
    def __init__(self, root_path: Union[str, Path], 
                 languages: List[str] = None,
                 custom_ignore_patterns: List[str] = None):
        """
        Initialize a project parser.
        
        Args:
            root_path: Root directory of the project
            languages: List of languages to parse (None for all supported languages)
            custom_ignore_patterns: Additional patterns to ignore beyond gitignore and defaults
        """
        self.root_path = Path(root_path) if isinstance(root_path, str) else root_path
        self.languages = languages
        
        # Initialize parsers for different languages
        self.parsers = {
            "python": PythonParser()
        }
        
        # Combine ignore patterns from defaults, gitignore, and custom patterns
        self.ignore_patterns = list(DEFAULT_IGNORE_PATTERNS)
        
        # Add patterns from .gitignore if it exists
        gitignore_patterns = self._load_gitignore_patterns()
        if gitignore_patterns:
            self.ignore_patterns.extend(gitignore_patterns)
            
        # Add custom ignore patterns
        if custom_ignore_patterns:
            self.ignore_patterns.extend(custom_ignore_patterns)
            
    def _load_gitignore_patterns(self) -> List[str]:
        """
        Load patterns from .gitignore file if it exists.
        
        Returns:
            List of gitignore patterns
        """
        gitignore_path = self.root_path / ".gitignore"
        patterns = []
        
        if gitignore_path.exists() and gitignore_path.is_file():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            # Convert gitignore pattern to fnmatch pattern
                            if line.startswith('/'):
                                # Pattern anchored to root
                                line = line[1:]  # Remove leading slash
                                pattern = f"{self.root_path.name}/{line}"
                            else:
                                # Pattern can match anywhere
                                pattern = f"*{line}" if not line.startswith('*') else line
                                
                            patterns.append(pattern)
                            # Also add pattern with trailing /* to catch directories
                            if not pattern.endswith('*'):
                                patterns.append(f"{pattern}/*")
            except Exception as e:
                logger.warning(f"Error reading .gitignore file: {e}")
                
        return patterns
    
    def parse_project(self) -> CodeBase:
        """
        Parse the entire project and build a CodeBase model.
        
        Returns:
            CodeBase object containing all parsed elements
        """
        # Initialize an empty CodeBase
        codebase = CodeBase(root_path=self.root_path)
        
        # Find all code files in the project
        code_files = find_code_files(self.root_path, self.languages, self.ignore_patterns)
        
        # Parse each file with the appropriate parser
        for file_path in tqdm(code_files):
            language = get_language_from_extension(file_path)
            if language and language in self.parsers:
                try:
                    # Read file content
                    content = read_file_content(file_path)
                    if content is None:
                        logger.warning(f"Could not read file: {file_path}")
                        continue
                    
                    # Parse the file
                    parser = self.parsers[language]
                    code_file = parser.parse_file(file_path, content)
                    
                    # Add the file to the codebase
                    codebase.elements.add_element(code_file)
                    codebase.files.append(code_file.id)
                    
                    # Add all elements from the file to the codebase
                    elements = parser.extract_all_elements(file_path, content)
                    for element_type, element_list in elements.items():
                        for element in element_list:
                            codebase.elements.add_element(element)
                except Exception as e:
                    logger.error(f"Error parsing file {file_path}: {e}")
        
        # Resolve dependencies between elements
        self._resolve_dependencies(codebase)
        
        return codebase
    
    def _resolve_dependencies(self, codebase: CodeBase) -> None:
        """
        Resolve dependencies between elements in the codebase.
        
        Args:
            codebase: CodeBase object containing all parsed elements
        """
        # Resolve dependencies for each language
        for language, parser in self.parsers.items():
            # try:
            parser.resolve_dependencies(codebase)
            # except Exception as e:
            #     logger.error(f"Error resolving dependencies for language {language}: {e}")