from ..core.models import CodeBase, CodeFileModel, ImportStatement


from typing import List, Optional, Union
from abc import ABC, abstractmethod
from tree_sitter import  Parser
from pydantic import BaseModel
from pathlib import Path

class BaseParser(ABC, BaseModel):
    """
    Abstract base class for language-specific parsers.
    """
    
    @property
    @abstractmethod
    def language(self) -> str:
        """The programming language this parser handles"""
        pass

    @property
    @abstractmethod
    def extension(self) -> str:
        pass

    @property
    @abstractmethod
    def tree_parser(self) -> Optional[Parser]:
        """The tree-sitter parser instance"""
        pass
    
    @staticmethod
    @abstractmethod
    def import_statement_template(importSatement :ImportStatement)->str:
        pass

    @abstractmethod
    async def parse_file(self, file_path: Union[str, Path], root_path: Optional[Union[str, Path]]=None) -> CodeFileModel:
        """
        Parse a source file and return a CodeFileModel.
        
        Args:
            file_path: Path to the source file to parse
            
        Returns:
            CodeFileModel representing the parsed file
        """
        pass

    @abstractmethod
    def resolve_inter_files_dependencies(self, codeBase: CodeBase, codeFiles :Optional[List[CodeFileModel]]=None) -> None:
        pass
    
    @abstractmethod
    def resolve_intra_file_dependencies(self, codeFiles: List[CodeFileModel]) -> None:
        pass

    # @abstractmethod
    # def _generate_unique_id(self, file_path: Path, component_type: str, name: str) -> str:
    #     """
    #     Generate a unique ID for a code component based on file path and component details.
        
    #     Args:
    #         file_path: Path to the source file
    #         component_type: Type of component ('import', 'class', 'function', 'variable')
    #         name: Name of the component
            
    #     Returns:
    #         Unique string identifier
    #     """
    #     pass