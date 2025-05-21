from typing import List, Optional, Literal, Union
from pydantic import BaseModel, RootModel, Field, computed_field

class CodeReference(BaseModel):
    """Reference to another code element"""
    # unique_id: str
    name: str
    type: Literal["import", "variable", "function", "class", "method", "inheritance"]
class ImportStatement(BaseModel):
    """Generic representation of an import statement"""
    source: str  # The module/package being imported from
    name :Optional[str] = None  # The alias for the import
    alias: Optional[str] = None  # The alias for the import
    import_type: Literal["absolute", "relative", "side_effect"] = "absolute"
    file_path: str="" 

    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the import statement"""
        if self.name:
            return f"{self.file_path}:{self.source}:{self.name}"
        return f"{self.file_path}:{self.source}"

class VariableDeclaration(BaseModel):
    """Representation of a variable declaration"""
    name: str
    type_hint: Optional[str] = None
    value: Optional[str] = None    
    modifiers: List[str] = Field(default_factory=list)  # e.g., "final", "abstract"
    references: List[CodeReference] = []
    file_path: str = ""

    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the variable declaration"""
        return f"{self.file_path}:{self.name}"

class Parameter(BaseModel):
    """Function parameter representation"""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None

    @computed_field
    def is_optional(self)->bool:
        return bool(self.default_value)


class FunctionSignature(BaseModel):
    """Function signature with parameters and return type"""
    parameters: List[Parameter] = []
    return_type: Optional[str] = None
    # is_variadic: bool = False  # For *args-like constructs
    # is_kw_variadic: bool = False  # For **kwargs-like constructs


class FunctionDefinition(BaseModel):
    """Representation of a function definition"""
    name: str
    signature: Optional[FunctionSignature]=None
    modifiers: List[str] = Field(default_factory=list)  # e.g., "async", "generator", etc.
    decorators: List[str] = Field(default_factory=list)
    references: List[CodeReference] = Field(default_factory=list)
    file_path: str = ""
    raw :Optional[str] = None

    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the function definition"""
        return f"{self.file_path}:{self.name}"

class MethodDefinition(FunctionDefinition):
    """Class method representation"""

class ClassAttribute(VariableDeclaration):
    """Class attribute representation"""
    # unique_id: str
    visibility: Literal["public", "protected", "private"] = "public"

class ClassDefinition(BaseModel):
    """Representation of a class definition"""
    # unique_id: str
    name: str
    bases: List[str] = Field(default_factory=list)
    attributes: List[ClassAttribute] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)
    references: List[CodeReference] = Field(default_factory=list)
    file_path: str = ""
    raw :Optional[str] = None
    
    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the function definition"""
        return f"{self.file_path}:{self.name}"

class CodeFileModel(BaseModel):
    """Representation of a single code file"""
    file_path: str
    imports: List[ImportStatement] = Field(default_factory=list)
    variables: List[VariableDeclaration] = Field(default_factory=list)
    functions: List[FunctionDefinition] = Field(default_factory=list)
    classes: List[ClassDefinition] = Field(default_factory=list)
    file_path: str = ""
    raw: Optional[str] = None

    @staticmethod
    def _list_all_unique_ids(entries_list :List[Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]])->List[str]:
        return [entry.unique_id for entry in entries_list]
    
    @property
    def all_imports(self)->List[str]:
        return self._list_all_unique_ids(self.imports)
    
    @property
    def all_variables(self)->List[str]:
        return self._list_all_unique_ids(self.variables)
    
    @property
    def all_functions(self)->List[str]:
        return self._list_all_unique_ids(self.functions)
    
    @property
    def all_classes(self)->List[str]:
        return self._list_all_unique_ids(self.classes)

    def add_import(self, import_statement :ImportStatement):
        import_statement.file_path = self.file_path
        self.imports.append(import_statement)

    def add_variable(self, variable_declaration :VariableDeclaration):
        variable_declaration.file_path = self.file_path
        self.variables.append(variable_declaration)

    def add_function(self, function_definition :FunctionDefinition):
        function_definition.file_path = self.file_path
        self.functions.append(function_definition)

    def add_class(self, class_definition :ClassDefinition):
        class_definition.file_path = self.file_path
        self.classes.append(class_definition)        

class CodeBase(RootModel):
    """Root model representing a complete codebase"""
    root: List[CodeFileModel] = Field(default_factory=list)