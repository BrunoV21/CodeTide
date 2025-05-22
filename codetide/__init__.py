from codetide.core.defaults import LANGUAGE_EXTENSIONS
from codetide.core.models import CodeFileModel
from codetide.parsers import BaseParser
from codetide import parsers

from pydantic import RootModel, Field, computed_field
from typing import Optional, List, Union, Dict
from pathlib import Path
from tqdm import tqdm
import fnmatch
import logging

logger = logging.getLogger(__name__)

class CodeBase(RootModel):
    """Root model representing a complete codebase"""
    root: List[CodeFileModel] = Field(default_factory=list)
    _ignore_patterns :Optional[str] = None
    _instantiated_parsers :Dict[str, BaseParser]

    @computed_field
    def ignore_patterns(self)->str:
        return self._ignore_patterns
    
    @ignore_patterns.setter
    def ignore_patterns(self, content :str):
        self._ignore_patterns = content

    @staticmethod
    def parserId(language :str)->str:
        return f"{language.upper()}Parser"

    @classmethod
    def from_path(cls, rootpath: Union[str, Path], languages: Optional[List[str]] = None) -> "CodeBase":
        rootpath = Path(rootpath)
        codeBase = cls()
        codeBase._load_gitignore_patterns(rootpath)

        fileList = codeBase._find_code_files(rootpath, languages=languages)
        
        # Wrap the loop with tqdm, displaying the file path
        for filepath in tqdm(fileList, desc="Processing files", unit="file"):
            tqdm.write(f"Processing: {filepath}")  # Optional: show current file outside of progress bar
            
            language = codeBase._get_language_from_extension(filepath)
            if language not in codeBase._instantiated_parsers:
                parserObj = getattr(parsers, codeBase.parserId(language), None)
                if parserObj is None:
                    logger.error(f"Skipping {filepath} as no parser is implemented for {language}")
                    continue
                parserObj = parserObj()
                codeBase._instantiated_parsers[language] = parserObj
            else:
                parserObj = codeBase._instantiated_parsers[language]

            codeFile = parserObj.parse_file(filepath, rootpath)
            codeBase.root.append(codeFile)
    
    def _load_gitignore_patterns(self, rootpath :Path):
        """
        Load patterns from .gitignore file if it exists.
        
        Returns:
            List of gitignore patterns
        """
        gitignore_path = rootpath / ".gitignore"
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
                                pattern = f"{rootpath.name}/{line}"
                            else:
                                # Pattern can match anywhere
                                pattern = f"*{line}" if not line.startswith('*') else line
                                
                            patterns.append(pattern)
                            # Also add pattern with trailing /* to catch directories
                            if not pattern.endswith('*'):
                                patterns.append(f"{pattern}/*")
            except Exception as e:
                logger.warning(f"Error reading .gitignore file: {e}")
                
        self.ignore_patterns = patterns

    def _should_ignore_file(self, file_path: Path) -> bool:
        """
        Check if a file should be ignored based on patterns.
        
        Args:
            file_path: Path to the file
            ignore_patterns: List of glob patterns to ignore
            
        Returns:
            True if the file should be ignored, False otherwise
        """
        if not self.ignore_patterns:
            return False
        
        # Check if any part of the path matches any ignore pattern
        path_str = str(file_path)
        for pattern in self.ignore_patterns:
            if any(fnmatch.fnmatch(part, pattern) for part in file_path.parts):
                return True
            if fnmatch.fnmatch(path_str, pattern):
                return True
        
        return False

    def _find_code_files(self, rootpath: Path, languages: Optional[List[str]] = None) -> List[Path]:
        """
        Find all code files in a directory tree.
        
        Args:
            root_path: Root directory to search
            languages: List of languages to include (None for all supported languages)
            ignore_patterns: List of glob patterns to ignore
            
        Returns:
            List of paths to code files
        """
        
        if not rootpath.exists() or not rootpath.is_dir():
            logger.error(f"Root path does not exist or is not a directory: {rootpath}")
            return []
        
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
        for file_path in rootpath.glob('**/*'):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                print(f"{file_path=}")
                if not self._should_ignore_file(file_path):
                    code_files.append(file_path)
        
        return code_files
    
    @staticmethod
    def _get_language_from_extension(filepath: Path) -> Optional[str]:
        """
        Determine the programming language based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Language name or None if not recognized
        """
        
        extension = filepath.suffix.lower()
        
        for language, extensions in LANGUAGE_EXTENSIONS.items():
            if extension in extensions:
                return language
        
        return None


