from typing import List, Optional, Literal
from pydantic import BaseModel, RootModel, Field, computed_field

class CodeReference(BaseModel):
    """Reference to another code element"""
    unique_id: str
    name: str
class ImportStatement(BaseModel):
    """Generic representation of an import statement"""
    source: str  # The module/package being imported from
    name :Optional[str] = None  # The alias for the import
    alias: Optional[str] = None  # The alias for the import
    import_type: Literal["absolute", "relative", "side_effect"] = "absolute"

    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the import statement"""
        if self.name:
            return f"{self.source}:{self.name}"
        return self.source

class VariableDeclaration(BaseModel):
    """Representation of a variable declaration"""
    unique_id: str
    name: str
    type_hint: Optional[str] = None
    value: Optional[str] = None
    is_constant: bool = False
    references: List[CodeReference] = []

class Parameter(BaseModel):
    """Function parameter representation"""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_optional: bool = False


class FunctionSignature(BaseModel):
    """Function signature with parameters and return type"""
    parameters: List[Parameter] = []
    return_type: Optional[str] = None
    is_variadic: bool = False  # For *args-like constructs
    is_kw_variadic: bool = False  # For **kwargs-like constructs


class FunctionDefinition(BaseModel):
    """Representation of a function definition"""
    unique_id: str
    name: str
    signature: FunctionSignature
    modifiers: List[str] = Field(default_factory=list)  # e.g., "async", "generator", etc.
    decorators: List[str] = Field(default_factory=list)
    references: List[CodeReference] = Field(default_factory=list)

class MethodDefinition(FunctionDefinition):
    """Class method representation"""
    kind: Literal["instance", "static", "class"] = "instance"


class ClassAttribute(BaseModel):
    """Class attribute representation"""
    unique_id: str
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    visibility: Literal["public", "protected", "private"] = "public"
    modifiers: List[str] = Field(default_factory=list)  # e.g., "final", "abstract"
    references: List[CodeReference] = Field(default_factory=list)


class ClassDefinition(BaseModel):
    """Representation of a class definition"""
    unique_id: str
    name: str
    bases: List[str] = Field(default_factory=list)
    decorators: List[str] = Field(default_factory=list)
    attributes: List[ClassAttribute] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)
    references: List[CodeReference] = Field(default_factory=list)

class CodeFileModel(BaseModel):
    """Representation of a single code file"""
    file_path: str
    imports: List[ImportStatement] = Field(default_factory=list)
    variables: List[VariableDeclaration] = Field(default_factory=list)
    functions: List[FunctionDefinition] = Field(default_factory=list)
    classes: List[ClassDefinition] = Field(default_factory=list)
    raw_code: Optional[str] = None

class CodeBase(RootModel):
    """Root model representing a complete codebase"""
    root: List[CodeFileModel] = Field(default_factory=list)