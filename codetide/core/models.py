from codetide.core.common import readFile, writeFile
from codetide.core.defaults import SERIALIZED_CODEBASE

from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field, computed_field
from pathlib import Path
from enum import Enum
import json
import re

class DependencyType(str, Enum):
    """Enumeration of different types of dependencies."""
    IMPORT = "import"                    # General import
    IMPORT_MODULE = "import_module"      # Module
    IMPORT_PACKAGE = "import_package"    # Package imports
    FUNCTION_CALL = "function_call"      # Function calls
    CLASS_REFERENCE = "class_reference"  # Class references
    INHERITANCE = "inheritance"          # Class inheritance
    IMPLEMENTATION = "implementation"    # Interface implementation
    VARIABLE_USE = "variable_use"        # Variable references


class CodeElement(BaseModel):
    """Base class for all code elements."""
    id: str = Field(..., description="Unique identifier for this element")
    name: str = Field(..., description="Name of the element")
    language: str = Field(..., description="Programming language")
    file_path: Path = Field(..., description="Path to the file containing this element")
    start_line: int = Field(..., description="Start line in the file")
    end_line: int = Field(..., description="End line in the file")
    start_col: Optional[int] = Field(None, description="Start column")
    end_col: Optional[int] = Field(None, description="End column")
    content: str = Field(..., description="Raw content of the code element")
    dependencies: Dict[str, List[str]] = Field(default_factory=dict, 
                                             description="Dictionary mapping dependency types to lists of element IDs")
    
    @computed_field
    def element_type(self)->str:
        """
        Type of the element
        """
        return self.id.split(":")[0]
    
    @computed_field
    def relative_name(self)->str:
        return ":".join(self.id.split(":")[1:-1])

    def add_dependency(self, dep_type: Union[DependencyType, str], target_id: str) -> None:
        """Add a dependency to this element."""
        if isinstance(dep_type, DependencyType):
            dep_type = dep_type.value
            
        if dep_type not in self.dependencies:
            self.dependencies[dep_type] = []
            
        if target_id not in self.dependencies[dep_type]:
            self.dependencies[dep_type].append(target_id)


class Import(CodeElement):
    """Model representing an import statement."""
    is_from_import: bool = Field(False, description="Whether this is a 'from X import Y' statement")
    module_name: str = Field(..., description="Name of the imported module")
    imported_names: List[str] = Field(default_factory=list, description="Names imported from the module")
    aliases: Dict[str, str] = Field(default_factory=dict, description="Mapping of original names to aliases")


class Function(CodeElement):
    """Model representing a function definition."""
    is_method: bool = Field(False, description="Whether this function is a class method")
    parameters: List[str] = Field(default_factory=list, description="List of parameter names")
    return_type: Optional[str] = Field(None, description="Return type annotation if available")
    decorators: List[str] = Field(default_factory=list, description="List of decorator names")
    parent_class: Optional[str] = Field(None, description="ID of parent class if this is a method")


class Class(CodeElement):
    """Model representing a class definition."""
    base_classes: List[str] = Field(default_factory=list, description="List of base class names")
    methods: List[str] = Field(default_factory=list, description="List of method IDs defined in this class")
    fields: List[str] = Field(default_factory=list, description="List of field names defined in this class")
    decorators: List[str] = Field(default_factory=list, description="List of decorator names")


class Variable(CodeElement):
    """Model representing a variable declaration."""
    var_type: Optional[str] = Field(None, description="Type annotation if available")
    is_constant: bool = Field(False, description="Whether this is a constant")
    value: Optional[str] = Field(None, description="Initial value as string representation")
    scope: str = Field("global", description="Scope of the variable (global, class, function)")
    parent_id: Optional[str] = Field(None, description="ID of parent element (class, function)")


class CodeFile(BaseModel):
    """Model representing a single code file."""
    file_path: Path = Field(..., description="Path to the file")
    language: str = Field(..., description="Programming language")
    content: str = Field(..., description="Raw content of the file")
    imports: List[str] = Field(default_factory=list, description="List of import IDs in this file")
    classes: List[str] = Field(default_factory=list, description="List of class IDs defined in this file")
    functions: List[str] = Field(default_factory=list, description="List of function IDs defined in this file")
    variables: List[str] = Field(default_factory=list, description="List of global variable IDs defined in this file")
    
    @property
    def id(self) -> str:
        """Generate a unique ID for this file."""
        return f"file:{self.file_path}"


class CodeModule(BaseModel):
    """Model representing a module (directory with code files)."""
    path: Path = Field(..., description="Path to the module directory")
    name: str = Field(..., description="Name of the module")
    files: List[str] = Field(default_factory=list, description="List of file IDs in this module")
    submodules: List[str] = Field(default_factory=list, description="List of submodule IDs")
    
    @property
    def id(self) -> str:
        """Generate a unique ID for this module."""
        return f"module:{self.path}"


class CodeBaseElements(BaseModel):
    """Container for all code elements in the codebase."""
    root: Dict[str, Union[CodeElement, CodeFile, CodeModule]] = {}
    
    def add_element(self, element: Union[CodeElement, CodeFile, CodeModule]) -> None:
        """Add an element to the codebase."""
        if hasattr(element, 'id'):
            self.root[element.id] = element
        else:
            element_id = f"{element.element_type}:{element.file_path}:{element.name}"
            self.root[element_id] = element
    
    def get_element(self, element_id: str) -> Union[CodeElement, CodeFile, CodeModule, None]:
        """Get an element by its ID."""
        return self.root.get(element_id)


class CodeBase(BaseModel):
    """Root model representing an entire codebase."""
    root_path: Path = Field(..., description="Root path of the codebase")
    elements: CodeBaseElements = Field(default_factory=CodeBaseElements, 
                                     description="Dictionary of all code elements by ID")
    modules: List[str] = Field(default_factory=list, description="List of top-level module IDs")
    files: List[str] = Field(default_factory=list, description="List of file IDs not in any module")
    
    def get_dependency_graph(self) -> Dict[str, List[Dict[str, str]]]:
        """Generate a graph representation of dependencies."""
        graph = {}
        
        for element_id, element in self.elements.root.items():
            if isinstance(element, CodeElement):
                graph[element_id] = [
                    {"type": dep_type, "target": target_id}
                    for dep_type, targets in element.dependencies.items()
                    for target_id in targets
                ]
        
        return graph
    
    def serialize(self, path :Optional[Union[Path, str]]=SERIALIZED_CODEBASE):
        if isinstance(path, str):
            path = Path(path)

        writeFile(self.model_dump_json(indent=4), path)

    @classmethod
    def deserialize(cls, path :Optional[Union[Path, str]]=SERIALIZED_CODEBASE)->"CodeBase":
        if isinstance(path, str):
            path = Path(path)

        kwargs = json.loads(readFile(path))
        return cls(**kwargs)
    
    @staticmethod
    def extract_key(entry: str):
        match = re.match(r".*:(.*?):.*?:(\d+)", entry)
        if match:
            file_name, line_num = match.groups()
            return (file_name, int(line_num))
        else:
            return ("", 0)
    
    def _sort_modules(self) -> None:
        self.modules = sorted(self.modules, key=self.extract_key)