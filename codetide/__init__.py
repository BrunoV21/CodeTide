from codetide.core.defaults import LANGUAGE_EXTENSIONS, DEFAULT_MAX_CONCURRENT_TASKS, DEFAULT_BATCH_SIZE
from codetide.core.models import CodeFileModel
from codetide.parsers import BaseParser
from codetide import parsers

from pydantic import RootModel, Field, computed_field
from typing import Optional, List, Union, Dict
from pathlib import Path
import fnmatch
import logging
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CodeBase(RootModel):
    """Root model representing a complete codebase"""
    root: List[CodeFileModel] = Field(default_factory=list)
    _ignore_patterns :Optional[str] = None
    _instantiated_parsers :Dict[str, BaseParser] = {}

    @computed_field
    def ignore_patterns(self)->str:
        return self._ignore_patterns
    
    @ignore_patterns.setter
    def ignore_patterns(self, content :str):
        self._ignore_patterns = content

    @staticmethod
    def parserId(language :str)->str:
        return f"{language.capitalize()}Parser"

    @classmethod
    async def from_path(
        cls,
        rootpath: Union[str, Path],
        languages: Optional[List[str]] = None,
        max_concurrent_tasks: int = DEFAULT_MAX_CONCURRENT_TASKS,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> "CodeBase":
        """
        Asynchronously create a CodeBase from a directory path.
        
        Args:
            rootpath: Path to the root directory
            languages: List of languages to include (None for all)
            max_concurrent_tasks: Maximum concurrent file processing tasks
            batch_size: Number of files to process in each batch
            
        Returns:
            Initialized CodeBase instance
        """
        rootpath = Path(rootpath)
        codebase = cls()
        logger.info(f"Initializing CodeBase from path: {rootpath}")
        
        await codebase._initialize_codebase(rootpath)
        
        file_list = codebase._find_code_files(rootpath, languages=languages)

        if not file_list:
            logger.warning("No code files found matching the criteria")
            return codebase
            
        language_files = codebase._organize_files_by_language(file_list)
        await codebase._initialize_parsers(language_files.keys())
        
        results = await codebase._process_files_concurrently(
            language_files,
            rootpath,
            max_concurrent_tasks,
            batch_size
        )
        
        codebase._add_results_to_codebase(results)
        logger.info(f"CodeBase initialized with {len(results)} files processed")
        
        return codebase

    async def _initialize_codebase(
        self,
        rootpath: Path
    ) -> None:
        """Initialize the codebase with gitignore patterns and basic setup."""
        self._load_gitignore_patterns(rootpath)
        logger.debug("Loaded gitignore patterns")

    def _organize_files_by_language(
        self,
        file_list: List[Path]
    ) -> Dict[str, List[Path]]:
        """Organize files by their programming language."""
        language_files = {}
        for filepath in file_list:
            language = self._get_language_from_extension(filepath)
            if language not in language_files:
                language_files[language] = []
            language_files[language].append(filepath)
        return language_files

    async def _initialize_parsers(
        self,
        languages: List[str]
    ) -> None:
        """Initialize parsers for all required languages."""
        for language in languages:
            if language not in self._instantiated_parsers:
                parser_obj = getattr(parsers, self.parserId(language), None)
                if parser_obj is None:
                    logger.warning(f"No parser {self.parserId(language)} implemented for {language}")
                    continue
                self._instantiated_parsers[language] = parser_obj()
                logger.debug(f"Initialized parser for {language}")

    async def _process_files_concurrently(
        self,
        language_files: Dict[str, List[Path]],
        rootpath: Path,
        max_concurrent_tasks: int,
        batch_size: int
    ) -> List:
        """
        Process all files concurrently with progress tracking.
        
        Returns:
            List of successfully processed CodeFileModel objects
        """
        semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        async def process_file_with_semaphore(filepath: Path, parser: BaseParser):
            async with semaphore:
                return await self._process_single_file(filepath, parser, rootpath)

        tasks = []
        for language, files in language_files.items():
            parser = self._instantiated_parsers.get(language)
            if parser is None:
                continue
            for filepath in files:
                task = asyncio.create_task(process_file_with_semaphore(filepath, parser))
                tasks.append(task)

        # Process in batches with progress bar
        results = []
        for i in range(0, len(tasks), batch_size ):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.debug(f"File processing failed: {str(result)}")
                    continue
                if result is not None:
                    results.append(result)
        
        return results

    async def _process_single_file(
        self,
        filepath: Path,
        parser: BaseParser,
        rootpath: Path
    ) -> Optional[CodeFileModel]:
        """Process a single file with error handling."""
        try:
            logger.debug(f"Processing file: {filepath}")
            return await parser.parse_file(filepath, rootpath)
        except Exception as e:
            logger.warning(f"Failed to process {filepath}: {str(e)}")
            return None

    def _add_results_to_codebase(
        self,
        results: List[CodeFileModel]
    ) -> None:
        """Add processed files to the codebase."""
        for code_file in results:
            if code_file is not None:
                self.root.append(code_file)
        logger.debug(f"Added {len(results)} files to codebase")
    
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


