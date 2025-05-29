from codetide.core.defaults import DEFAULT_SERIALIZATION_PATH, LANGUAGE_EXTENSIONS, DEFAULT_MAX_CONCURRENT_TASKS, DEFAULT_BATCH_SIZE
from codetide.core.models import CodeFileModel, CodeBase
from codetide.core.common import readFile, writeFile

from codetide.parsers import BaseParser
from codetide import parsers

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union, Dict
from pathspec import GitIgnoreSpec
from pathlib import Path
import logging
import asyncio
import time
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CodeTide(BaseModel):
    """Root model representing a complete codebase"""
    rootpath : Union[str, Path]
    codebase :CodeBase = Field(default_factory=CodeBase)
    file_list :List[Path] = Field(default_factory=list)
    _instantiated_parsers :Dict[str, BaseParser] = {}
    _gitignore_cache :Dict[str, GitIgnoreSpec] = {}

    @field_validator("rootpath", mode="after")
    @classmethod
    def rootpath_to_path(cls, rootpath : Union[str, Path])->Path:
        return Path(rootpath)

    @staticmethod
    def parserId(language :Optional[str]=None)->str:
        if language is None:
            return ""
        return f"{language.capitalize()}Parser"

    @classmethod
    async def from_path(
        cls,
        rootpath: Union[str, Path],
        languages: Optional[List[str]] = None,
        max_concurrent_tasks: int = DEFAULT_MAX_CONCURRENT_TASKS,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> "CodeTide":
        """
        Asynchronously create a CodeTide from a directory path.

        Args:
            rootpath: Path to the root directory
            languages: List of languages to include (None for all)
            max_concurrent_tasks: Maximum concurrent file processing tasks
            batch_size: Number of files to process in each batch

        Returns:
            Initialized CodeTide instance
        """
        rootpath = Path(rootpath)
        codebase = cls(rootpath=rootpath)
        logger.info(f"Initializing CodeBase from path: {str(rootpath)}")

        st = time.time()
        codebase._find_code_files(rootpath, languages=languages)
        if not codebase.file_list:
            logger.warning("No code files found matching the criteria")
            return codebase

        language_files = codebase._organize_files_by_language()
        await codebase._initialize_parsers(language_files.keys())

        results = await codebase._process_files_concurrently(
            language_files,
            max_concurrent_tasks,
            batch_size
        )

        codebase._add_results_to_codebase(results)
        codebase._resolve_files_dependencies()
        logger.info(f"CodeBase initialized with {len(results)} files processed in {time.time() - st:.2f}s")

        return codebase
    
    def serialize(self, filepath :Optional[Union[str, Path]]=DEFAULT_SERIALIZATION_PATH):
        if not os.path.exists(filepath):
            os.makedirs(os.path.split(filepath)[0], exist_ok=True)
        writeFile(self.model_dump_json(indent=4), filepath)

    @classmethod
    def deserialize(cls, filepath :Optional[Union[str, Path]]=DEFAULT_SERIALIZATION_PATH)->"CodeTide":
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"{filepath} is not a valid path")
        
        kwargs = readFile(filepath)
        return cls(**kwargs)

    def _organize_files_by_language(
        self,
    ) -> Dict[str, List[Path]]:
        """Organize files by their programming language."""
        language_files = {}
        for filepath in self.file_list:
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
                if parser_obj is not None:
                    self._instantiated_parsers[language] = parser_obj()
                    logger.debug(f"Initialized parser for {language}")

    async def _process_files_concurrently(
        self,
        language_files: Dict[str, List[Path]],
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
                return await self._process_single_file(filepath, parser)

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
        parser: BaseParser
    ) -> Optional[CodeFileModel]:
        """Process a single file with error handling."""
        try:
            logger.debug(f"Processing file: {filepath}")
            return await parser.parse_file(filepath, self.rootpath)
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
                self.codebase.root.append(code_file)
        logger.debug(f"Added {len(results)} files to codebase")

    @staticmethod
    def _load_gitignore_spec(directory: Path) -> GitIgnoreSpec:
        """
        Load and parse .gitignore file from a directory into a GitIgnoreSpec object.

        Args:
            directory: Directory containing the .gitignore file

        Returns:
            GitIgnoreSpec object with the patterns from the .gitignore file
        """
        gitignore_path = directory / ".gitignore"
        patterns = [".git/"]

        if gitignore_path.exists() and gitignore_path.is_file():
            try:
                _gitignore = readFile(gitignore_path)
                for line in _gitignore.splitlines():
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        patterns.append(line)
            except Exception as e:
                logger.warning(f"Error reading .gitignore file {gitignore_path}: {e}")

        return GitIgnoreSpec.from_lines(patterns)

    def _get_gitignore_for_path(self, path: Path) -> GitIgnoreSpec:
        """
        Get the combined GitIgnoreSpec for a path by checking all parent directories.

        Args:
            path: The file path to check

        Returns:
            Combined GitIgnoreSpec for all relevant .gitignore files
        """
        # Check cache first
        if path in self._gitignore_cache:
            return self._gitignore_cache[path]

        # Collect all .gitignore specs from parent directories
        specs = []

        # Check the directory containing the file
        parent_dir = path.parent if path.is_file() else path

        # Walk up the directory tree
        for directory in [parent_dir, *parent_dir.parents]:
            if directory not in self._gitignore_cache:
                # Load and cache the spec for this directory
                self._gitignore_cache[directory] = self._load_gitignore_spec(directory)

            specs.append(self._gitignore_cache[directory])

        # Combine all specs into one
        combined_spec = GitIgnoreSpec([])
        for spec in reversed(specs):  # Apply from root to leaf
            combined_spec += spec

        return combined_spec

    def _find_code_files(self, rootpath: Path, languages: Optional[List[str]] = None) -> List[Path]:
        """
        Find all code files in a directory tree, respecting .gitignore rules in each directory.

        Args:
            rootpath: Root directory to search
            languages: List of languages to include (None for all supported)

        Returns:
            List of paths to code files
        """
        if not rootpath.exists() or not rootpath.is_dir():
            logger.error(f"Root path does not exist or is not a directory: {rootpath}")
            return []

        # Determine valid extensions
        extensions = []
        if languages:
            for lang in languages:
                if lang in LANGUAGE_EXTENSIONS:
                    extensions.extend(LANGUAGE_EXTENSIONS[lang])

        code_files = []

        for file_path in rootpath.rglob('*'):
            if not file_path.is_file() or (extensions and file_path.suffix.lower() not in extensions):
                continue

            # Get the combined gitignore spec for this path
            gitignore_spec = self._get_gitignore_for_path(file_path)

            # Convert path to relative path for gitignore matching
            try:
                rel_path = file_path.relative_to(rootpath)
            except ValueError:
                # This shouldn't happen since we're scanning from rootpath
                continue

            # Check if the file is ignored by any gitignore rules
            if gitignore_spec.match_file(rel_path):
                continue

            code_files.append(file_path)

        self.file_list = code_files
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

    def _resolve_files_dependencies(self):
        for _, parser in self._instantiated_parsers.items():
            parser.resolve_inter_files_dependencies(self.codebase)
            parser.resolve_intra_file_dependencies(self.codebase)

