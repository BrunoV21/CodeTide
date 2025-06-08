from codetide.core.defaults import (
    DEFAULT_SERIALIZATION_PATH, DEFAULT_MAX_CONCURRENT_TASKS,
    DEFAULT_BATCH_SIZE, DEFAULT_CACHED_ELEMENTS_FILE, DEFAULT_CACHED_IDS_FILE,
    LANGUAGE_EXTENSIONS
)
from codetide.core.models import CodeFileModel, CodeBase
from codetide.core.common import readFile, writeFile

from codetide.parsers import BaseParser
from codetide import parsers

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Tuple, Union, Dict
from datetime import datetime, timezone
from pathlib import Path
import logging
import asyncio
import pygit2
import time
import json
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
    files :Dict[Path, datetime]= Field(default_factory=dict)
    _instantiated_parsers :Dict[str, BaseParser] = {}

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
        codeTide = cls(rootpath=rootpath)
        logger.info(f"Initializing CodeTide from path: {str(rootpath)}")

        st = time.time()
        codeTide.files = codeTide._find_code_files(rootpath, languages=languages)
        if not codeTide.files:
            logger.warning("No code files found matching the criteria")
            return codeTide

        language_files = codeTide._organize_files_by_language(codeTide.files)
        codeTide._initialize_parsers(language_files.keys())

        results = await codeTide._process_files_concurrently(
            language_files,
            max_concurrent_tasks,
            batch_size
        )

        codeTide._add_results_to_codebase(results)
        codeTide._resolve_files_dependencies()
        logger.info(f"CodeTide initialized with {len(results)} files processed in {time.time() - st:.2f}s")

        return codeTide
    
    async def _reset(self):
        self = await self.from_path(self.rootpath)
    
    def serialize(self,
        filepath: Optional[Union[str, Path]] = DEFAULT_SERIALIZATION_PATH, 
        include_codebase_cached_elements: bool = False, 
        include_cached_ids: bool = False,
        store_in_project_root: bool=True):

        if store_in_project_root:
            filepath = Path(self.rootpath) / filepath
        
        if not os.path.exists(filepath):
            os.makedirs(os.path.split(filepath)[0], exist_ok=True)

        writeFile(self.model_dump_json(indent=4), filepath)

        dir_path = Path(os.path.split(filepath)[0])
        
        current_path = dir_path
        gitignore_path = None
        for parent in current_path.parents:
            potential_gitignore = parent / ".gitignore"
            if potential_gitignore.exists():
                gitignore_path = potential_gitignore
                break

        if gitignore_path:
            with open(gitignore_path, 'r+') as f:
                lines = f.read().splitlines()
                if f"{dir_path.name}/" not in lines:
                    f.write(f"\n{dir_path.name}/\n")

        if include_codebase_cached_elements:
            cached_elements_path = dir_path / DEFAULT_CACHED_ELEMENTS_FILE
            writeFile(self.codebase.serialize_cache_elements(), cached_elements_path)

        if include_cached_ids:
            cached_ids_path = dir_path / DEFAULT_CACHED_IDS_FILE
            writeFile(json.dumps(self.codebase.unique_ids, indent=4), cached_ids_path)

    @classmethod
    def deserialize(cls, filepath :Optional[Union[str, Path]]=DEFAULT_SERIALIZATION_PATH, rootpath :Optional[Union[str, Path]] = None)->"CodeTide":
        if rootpath is not None:
            filepath = Path(rootpath) / filepath

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"{filepath} is not a valid path")
        
        kwargs = json.loads(readFile(filepath))
        tideInstance = cls(**kwargs)
        
        # dir_path = Path(os.path.split(filepath))[0]
        # cached_elements_path = dir_path / DEFAULT_CACHED_ELEMENTS_FILE
        # if os.path.exists(cached_elements_path):
        #     cached_elements = json.loads(readFile(cached_elements_path))
        #     tideInstance.codebase._cached_elements = cached_elements

        return tideInstance

    @classmethod
    def _organize_files_by_language(cls, files :Union[List, Dict[str, str]]) -> Dict[str, List[Path]]:
        """Organize files by their programming language."""
        language_files = {}
        for filepath in files:
            language = cls._get_language_from_extension(filepath)
            if language not in language_files:
                language_files[language] = []
            language_files[language].append(filepath)
        return language_files

    def _initialize_parsers(
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

    def _find_code_files(self, rootpath: Path, languages: Optional[List[str]] = None) -> List[Path]:
        """
        Find all code files in a directory tree, respecting .gitignore rules in each directory.

        Args:
            rootpath: Root directory to search
            languages: List of languages to include (None for all supported)

        Returns:
            List of paths to code files with their last modified timestamps
        """
        if not rootpath.exists() or not rootpath.is_dir():
            logger.error(f"Root path does not exist or is not a directory: {rootpath}")
            return {}

        # Determine valid extensions
        extensions = []
        if languages:
            for lang in languages:
                if lang in LANGUAGE_EXTENSIONS:
                    extensions.extend(LANGUAGE_EXTENSIONS[lang])

        code_files = {}
        
        try:
            # Try to open the repository
            repo = pygit2.Repository(rootpath)
            
            # Get the repository's index (staging area)
            index = repo.index
            
            # Convert all tracked files to Path objects
            tracked_files = {Path(rootpath) / Path(entry.path) for entry in index}
            
            # Get status and filter files
            status = repo.status()
            
            # Untracked files are those with status == pygit2.GIT_STATUS_WT_NEW
            untracked_not_ignored = {
                Path(rootpath) / Path(filepath)
                for filepath, file_status in status.items()
                if file_status == pygit2.GIT_STATUS_WT_NEW and not repo.path_is_ignored(filepath)
            }
            
            all_files = tracked_files.union(untracked_not_ignored)
            
        except (pygit2.GitError, KeyError):
            # Fallback to simple directory walk if not a git repo
            all_files = set(rootpath.rglob('*'))
        
        for file_path in all_files:
            if not file_path.is_file():
                continue
                
            # Check extension filter if languages were specified
            if extensions and file_path.suffix.lower() not in extensions:
                continue
                
            # Get the last modified time and convert to UTC datetime
            modified_timestamp = file_path.stat().st_mtime
            modified_datetime = datetime.fromtimestamp(modified_timestamp, timezone.utc)
            
            code_files[file_path] = modified_datetime
        
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

        extension = Path(filepath).suffix.lower()

        for language, extensions in LANGUAGE_EXTENSIONS.items():
            if extension in extensions:
                return language

        return None

    def _resolve_files_dependencies(self):
        for _, parser in self._instantiated_parsers.items():
            parser.resolve_inter_files_dependencies(self.codebase)
            parser.resolve_intra_file_dependencies(self.codebase.root)

    def _get_changed_files(self) -> Tuple[List[Path], bool]:
        """
        TODO consider if it is worth storing singular timestamp for latest fetch and then just use 
        pygit2 to changed files based on commit history + current repo status
        """
        file_deletion_detected = False
        files = self._find_code_files(self.rootpath)  # Dict[Path, datetime]
        
        changed_files = []
        
        # Check for new files and modified files
        for file_path, current_modified_time in files.items():
            if file_path not in self.files:
                # New file
                changed_files.append(file_path)
            elif current_modified_time > self.files[file_path]:
                # File has been modified since last scan
                changed_files.append(file_path)
        
        # Check for deleted files
        for stored_file_path in self.files:
            if stored_file_path not in files:
                file_deletion_detected = True
                break
        
        self.files = files
        return changed_files, file_deletion_detected

    async def check_for_updates(self,
        serialize :bool=False,
        max_concurrent_tasks: int = DEFAULT_MAX_CONCURRENT_TASKS, 
        batch_size: int = DEFAULT_BATCH_SIZE, **kwargs):

        changed_files, deletion_detected = self._get_changed_files()
        if deletion_detected:
            logger.info("deletion operation detected reseting CodeTide [this is a temporary solution]")
            await self._reset()

        if not changed_files:
            return

        changed_language_files = self._organize_files_by_language(changed_files)
        self._initialize_parsers(changed_language_files.keys())

        results :List[CodeFileModel] = await self._process_files_concurrently(
            changed_language_files,
            max_concurrent_tasks=max_concurrent_tasks,
            batch_size=batch_size
        )

        changedPaths = {
            codeFile.file_path: None for codeFile in results
        }

        for i, codeFile in enumerate(self.codebase.root):
            if codeFile.file_path in changedPaths:
                changedPaths[codeFile.file_path] = i

        newFiles :List[CodeFileModel] = []
        for codeFile in results:
            i = changedPaths.get(codeFile.file_path)
            if i is not None: ### is file update
                ### TODO if new imports are found need to build inter and then intra
                ### otherwise can just build intra and add directly
                if codeFile.all_imports() == self.codebase.root[i].all_imports():
                    language = self._get_language_from_extension(codeFile.file_path)
                    parser = self._instantiated_parsers.get(language)
                    self.codebase.root[i] = codeFile
                    logger.info(f"updating {codeFile.file_path} no new dependencies detected")
                    continue
                
                self.codebase.root[i] = codeFile 
                logger.info(f"updating {codeFile.file_path} with new dependencies")

            else:
                self.codebase.root.append(codeFile)
                changedPaths[codeFile.file_path] = len(self.codebase.root) - 1
                logger.info(f"adding new file {codeFile.file_path}")
            
            newFiles.append(codeFile)
        

        for language, filepaths in changed_language_files.items():
            parser = self._instantiated_parsers.get(language)
            filteredNewFiles = [
                newFile for newFile in newFiles
                if self.rootpath / newFile.file_path in filepaths
            ]
            parser.resolve_inter_files_dependencies(self.codebase, filteredNewFiles)
            parser.resolve_intra_file_dependencies(filteredNewFiles)

            for codeFile in filteredNewFiles:
                i = changedPaths.get(codeFile.file_path)
                self.codebase.root[i] = codeFile

        if serialize:
            self.serialize(
                store_in_project_root=kwargs.get("include_cached_ids", True),
                include_cached_ids=kwargs.get("include_cached_ids", False)
            )