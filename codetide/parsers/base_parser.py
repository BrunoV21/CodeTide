from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

from codetide.core.models import (
    CodeBase, CodeFile, CodeElement, Import, 
    Function, Class, Variable
)


class BaseParser(ABC, BaseModel):
    """
    Abstract base parser class that should be extended by language-specific parsers.
    """
    language: str = Field(..., description="Programming language this parser handles")
    
    @abstractmethod
    def parse_file(self, file_path: Path, content: str, rootpath :Optional[Path]=None) -> CodeFile:
        """
        Parse a single file and extract its components.
        
        Args:
            file_path: Path to the file
            content: Raw content of the file
            
        Returns:
            CodeFile object populated with extracted components
        """
        pass
    
    @abstractmethod
    def extract_imports(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Import]:
        """
        Extract import statements from file content.
        
        Args:
            content: Raw content of the file
            file_path: Path to the file
            
        Returns:
            List of Import objects
        """
        pass
    
    @abstractmethod
    def extract_classes(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Class]:
        """
        Extract class definitions from file content.
        
        Args:
            content: Raw content of the file
            file_path: Path to the file
            
        Returns:
            List of Class objects
        """
        pass
    
    @abstractmethod
    def extract_functions(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Function]:
        """
        Extract function definitions from file content.
        
        Args:
            content: Raw content of the file
            file_path: Path to the file
            
        Returns:
            List of Function objects
        """
        pass
    
    @abstractmethod
    def extract_variables(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Variable]:
        """
        Extract variable declarations from file content.
        
        Args:
            content: Raw content of the file
            file_path: Path to the file
            
        Returns:
            List of Variable objects
        """
        pass
    
    @abstractmethod
    def resolve_dependencies(self, codebase: CodeBase) -> None:
        """
        Analyze the codebase to identify and establish dependencies between elements.
        
        Args:
            codebase: CodeBase object containing all parsed elements
        """
        pass
    
    def generate_element_id(self, element_type: str, file_path: Path, name: str, 
                            start_line: Optional[int] = None, rootpath :Optional[Path]=None) -> str:
        """
        Generate a unique ID for a code element.
        
        Args:
            element_type: Type of the element (class, function, etc.)
            file_path: Path to the file containing the element
            name: Name of the element
            start_line: Optional start line of the element
            
        Returns:
            Unique ID string
        """
        if rootpath is not None:
            file_path = file_path.relative_to(rootpath)

        base_id = f"{element_type}:{file_path}:{name}"
        if start_line is not None:
            return f"{base_id}:{start_line}"
        return base_id
    
    def extract_all_elements(self, file_path: Path, content: str, rootpath :Optional[Path]=None) -> Dict[str, List[CodeElement]]:
        """
        Extract all code elements from a file.
        
        Args:
            file_path: Path to the file
            content: Raw content of the file
            
        Returns:
            Dictionary mapping element types to lists of extracted elements
        """
        return {
            "imports": self.extract_imports(content, file_path, rootpath),
            "classes": self.extract_classes(content, file_path, rootpath),
            "functions": self.extract_functions(content, file_path, rootpath),
            "variables": self.extract_variables(content, file_path, rootpath)
        }