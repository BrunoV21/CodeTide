from ..core.models import CodeBase, CodeFileModel, ImportStatement
from ..parsers.base_parser import BaseParser

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Union
from pathlib import Path
import asyncio

class GenericParser(BaseParser):
    """
    Gneroc-specific implementation of the BaseParser.
    """
    _filepath: Optional[Union[str, Path]] = None

    @property
    def language(self) -> str:
        return "any"
    
    @property
    def extension(self) -> str:
        return ""

    
    @property
    def tree_parser(self) -> None:
        """The tree-sitter parser instance"""
        pass
    
    @staticmethod
    def import_statement_template(importSatement :ImportStatement)->str:
        pass

    async def parse_file(self, file_path: Union[str, Path], root_path: Optional[Union[str, Path]]=None) -> CodeFileModel:
        """
        Parse a source file and return a CodeFileModel.
        
        Args:
            file_path: Path to the source file to parse
            
        Returns:
            CodeFileModel representing the parsed file
        """
        file_path = Path(file_path).absolute()
        
        # Use aiofiles or run synchronous file IO in executor
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            
            if root_path is not None:
                file_path = file_path.relative_to(Path(root_path))

            codeFile = await loop.run_in_executor(pool, self.parse_code, file_path)

        return codeFile
    
    def parse_code(self, file_path :Path):
        codeFile = CodeFileModel(
            file_path=str(file_path)
        )
        return codeFile
    
    def resolve_inter_files_dependencies(self, codeBase: CodeBase, codeFiles :Optional[List[CodeFileModel]]=None) -> None:
        pass
    
    def resolve_intra_file_dependencies(self, codeFiles: List[CodeFileModel]) -> None:
        pass