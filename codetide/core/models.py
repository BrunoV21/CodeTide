from pydantic import BaseModel, Field, computed_field
from typing import List, Optional, Literal, Union

class BaseCodeElement(BaseModel):
    _unique_id :Optional[str]=None

    @property
    def file_path_without_suffix(self)->str:
        return "".join(self.file_path.split(".")[:-1]).replace("\\", ".").replace("/", ".")
    
    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the function definition"""
        if self._unique_id is not None:
            return self._unique_id
        
        file_path_without_suffix = self.file_path_without_suffix
        if file_path_without_suffix:
            file_path_without_suffix = f"{file_path_without_suffix}:"

        return f"{file_path_without_suffix}{self.name}"
    
    @unique_id.setter
    def unique_id(self, value :str):
        self._unique_id = value

class CodeReference(BaseModel):
    """Reference to another code element"""
    unique_id :Optional[str]=None
    name: str
    # type: Literal["import", "variable", "function", "class", "method", "inheritance"]

class ImportStatement(BaseCodeElement):
    """Generic representation of an import statement"""
    source: str  # The module/package being imported from
    name :Optional[str] = None  # The alias for the import
    alias: Optional[str] = None  # The alias for the import
    import_type: Literal["absolute", "relative", "side_effect"] = "absolute"
    definition_id :Optional[str]=None # ID to store where the Import is defined if from another file, none if is package
    file_path: str=""
    
    @property
    def as_dependency(self)->str:
        return self.alias or self.name or self.source

class VariableDeclaration(BaseCodeElement):
    """Representation of a variable declaration"""
    name: str
    type_hint: Optional[str] = None
    value: Optional[str] = None    
    modifiers: List[str] = Field(default_factory=list)  # e.g., "final", "abstract"
    references: List[CodeReference] = []
    file_path: str = ""
    raw :Optional[str] = ""

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

class FunctionDefinition(BaseCodeElement):
    """Representation of a function definition"""
    name: str
    signature: Optional[FunctionSignature]=None
    modifiers: List[str] = Field(default_factory=list)  # e.g., "async", "generator", etc.
    decorators: List[str] = Field(default_factory=list)
    references: List[CodeReference] = Field(default_factory=list)
    file_path: str = ""
    raw :Optional[str] = ""

class MethodDefinition(FunctionDefinition):
    """Class method representation"""

class ClassAttribute(VariableDeclaration):
    """Class attribute representation"""
    # unique_id: str
    visibility: Literal["public", "protected", "private"] = "public"

class ClassDefinition(BaseCodeElement):
    """Representation of a class definition"""
    # unique_id: str
    name: str
    bases: List[str] = Field(default_factory=list)
    attributes: List[ClassAttribute] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)
    bases_references: List[CodeReference] = Field(default_factory=list)
    file_path: str = ""
    raw :Optional[str] = ""
    
    def add_method(self, method :MethodDefinition):
        method.file_path = self.file_path
        method.unique_id = f"{self.unique_id}.{method.unique_id}"
        self.methods.append(method)

    def add_attribute(self, attribute :ClassAttribute):
        attribute.file_path = self.file_path
        attribute.unique_id = f"{self.unique_id}.{attribute.unique_id}"
        self.attributes.append(attribute)

    @property
    def references(self)->List[CodeReference]:
        all_references = []
        all_references.extend(self.bases_references)
        all_references.extend(
            {attribute.references for attribute in self.attributes}
        )
        all_references.extend(
            {method.references for method in self.methods}
        )
        return all_references

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

    def get(self, unique_id: str) -> Optional[Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]:
        """Get any code element by its unique_id"""
        # Check imports
        for imp in self.imports:
            if imp.unique_id == unique_id:
                return imp
        
        # Check variables
        for var in self.variables:
            if var.unique_id == unique_id:
                return var
        
        # Check functions
        for func in self.functions:
            if func.unique_id == unique_id:
                return func
            # Check methods within functions (if this is a method)
            if isinstance(func, MethodDefinition):
                if func.unique_id == unique_id:
                    return func
        
        # Check classes and their members
        for _cls in self.classes:
            if _cls.unique_id == unique_id:
                return _cls
            
            # Check class attributes
            for attr in _cls.attributes:
                if attr.unique_id == unique_id:
                    return attr
            # Check methods
            for method in _cls.methods:
                if method.unique_id == unique_id:
                    return method
        
        return None

    def get_import(self, unique_id :str)->Optional[ImportStatement]:
        for importStatement in self.imports:
            if unique_id == importStatement.unique_id:
                return importStatement
        return None
    
    @property
    def list_raw_contents(self)->List[str]:
        raw :List[str] = []

        for classDefintion in self.classes:
            raw.append(classDefintion.raw)
        
        for function in self.functions:
            raw.append(function.raw)

        for variable in self.variables:
            raw.append(variable.raw)

        return raw

class CodeBase(BaseModel):
    """Root model representing a complete codebase"""
    root: List[CodeFileModel] = Field(default_factory=list)

    def _list_all_unique_ids_for_property(self, property :Literal["classes", "functions", "variables", "imports"])->List[str]:
        return sum([
            getattr(entry, f"all_{property}") for entry in self.root
        ], [])

    @property
    def all_variables(self)->List[str]:
        return self._list_all_unique_ids_for_property("variables")
    
    @property
    def all_functions(self)->List[str]:
        return self._list_all_unique_ids_for_property("functions")
    
    @property
    def all_classes(self)->List[str]:
        return self._list_all_unique_ids_for_property("classes")
    
    @property
    def all_imports(self)->List[str]:
        return self._list_all_unique_ids_for_property("imports")
    
    def get_import(self, unique_id :str)->Optional[ImportStatement]:
        match = None
        for codeFile in self.root:
            match = codeFile.get_import(unique_id)
            if match is not None:
                return match
        return match