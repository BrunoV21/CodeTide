from pydantic import BaseModel, Field, computed_field
from typing import Any, Dict, List, Optional, Literal, Union

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
            file_path_without_suffix = f"{file_path_without_suffix}."

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
    raw: str=""
    
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
    class_id :str

class ClassAttribute(VariableDeclaration):
    """Class attribute representation"""
    # unique_id: str
    class_id :str
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
        method.unique_id = f"{self.unique_id}.{method.name}"
        method.class_id = self.unique_id
        self.methods.append(method)

    def add_attribute(self, attribute :ClassAttribute):
        attribute.file_path = self.file_path
        attribute.unique_id = f"{self.unique_id}.{attribute.name}"
        attribute.class_id = self.unique_id
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
    def _list_all(entries_list :List[Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]])->Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]:
        return {entry.unique_id: entry for entry in entries_list}

    def all_imports(self, as_dict :bool=False)->Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.imports)
        return list(unique_dict.keys()) if not as_dict else unique_dict
    
    def all_variables(self, as_dict :bool=False)->Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.variables)
        return list(unique_dict.keys()) if not as_dict else unique_dict
    
    def all_classes(self, as_dict :bool=False)->Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.classes)
        return list(unique_dict.keys()) if not as_dict else unique_dict
    
    def all_functions(self, as_dict :bool=False)->Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.functions)
        return list(unique_dict.keys()) if not as_dict else unique_dict

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
    _cached_elements :Dict[str, Any]= dict()

    def _build_cached_elements(self, force_update :bool=False):
        if not self._cached_elements or force_update:
            for codeFile in self.root:
                for unique_id, element in codeFile.all_classes(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        print(f"CLASS {unique_id} already exists")                        
                        continue
                    self._cached_elements[unique_id] = element
                
                for unique_id, element in codeFile.all_functions(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        print(f"FUNCTION {unique_id} already exists")                        
                        continue
                    self._cached_elements[unique_id] = element

                for unique_id, element in codeFile.all_variables(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        print(f"VARIABLE {unique_id} already exists")
                        continue
                    self._cached_elements[unique_id] = element
                
                for unique_id, element in codeFile.all_imports(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        print(f"IMPORT {unique_id} already exists")
                        continue
                    self._cached_elements[unique_id] = element
                

    def _list_all_unique_ids_for_property(self, property :Literal["classes", "functions", "variables", "imports"])->List[str]:
        return sum([
            getattr(entry, f"all_{property}")() for entry in self.root
        ], [])
    
    # @property
    def all_variables(self)->List[str]:
        return self._list_all_unique_ids_for_property("variables")
    
    # @property
    def all_functions(self)->List[str]:
        return self._list_all_unique_ids_for_property("functions")
    
    # @property
    def all_classes(self)->List[str]:
        return self._list_all_unique_ids_for_property("classes")
    
    # @property
    def all_imports(self)->List[str]:
        return self._list_all_unique_ids_for_property("imports")
    
    def get_import(self, unique_id :str)->Optional[ImportStatement]:
        match = None
        for codeFile in self.root:
            match = codeFile.get_import(unique_id)
            if match is not None:
                return match
        return match

    def get_tree_view(self, include_modules: bool = False, include_types: bool = False) -> str:
        """
        Generate a bash-style tree view of the codebase structure.
        
        Args:
            include_modules: If True, include classes, functions, and variables within each file
            include_types: If True, prefix each entry with its type (F/V/C/A/M)
        
        Returns:
            str: ASCII tree representation of the codebase structure
        """
        # Build the nested structure first
        tree_dict = self._build_tree_dict()
        
        # Convert to ASCII tree
        lines = []
        self._render_tree_node(tree_dict, "", True, lines, include_modules, include_types)
        
        return "\n".join(lines)

    def _build_tree_dict(self) -> dict:
        """Build a nested dictionary representing the directory structure."""
        tree = {}
        
        for code_file in self.root:
            if not code_file.file_path:
                continue
                
            # Split the file path into parts
            path_parts = code_file.file_path.replace("\\", "/").split("/")
            
            # Navigate/create the nested dictionary structure
            current_level = tree
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:  # This is the file
                    current_level[part] = {"_type": "file", "_data": code_file}
                else:  # This is a directory
                    if part not in current_level:
                        current_level[part] = {"_type": "directory"}
                    current_level = current_level[part]
        
        return tree

    def _render_tree_node(self, node: dict, prefix: str, is_last: bool, lines: list, 
                        include_modules: bool, include_types: bool, depth: int = 0):
        """
        Recursively render a tree node with ASCII art.
        
        Args:
            node: Dictionary node to render
            prefix: Current line prefix for ASCII art
            is_last: Whether this is the last item at current level
            lines: List to append rendered lines to
            include_modules: Whether to include module contents
            include_types: Whether to include type prefixes
            depth: Current depth in the tree
        """
        items = [(k, v) for k, v in node.items() if not k.startswith("_")]
        items.sort(key=lambda x: (x[1].get("_type", "directory") == "file", x[0]))
        
        for i, (name, data) in enumerate(items):
            is_last_item = i == len(items) - 1
            
            # Choose the appropriate tree characters
            if is_last_item:
                current_prefix = "└── "
                next_prefix = prefix + "    "
            else:
                current_prefix = "├── "
                next_prefix = prefix + "│   "
            
            # Determine display name with optional type prefix
            display_name = name
            if include_types:
                if data.get("_type") == "file":
                    display_name = f" {name}"
                else:
                    display_name = f"{name}"
            
            lines.append(f"{prefix}{current_prefix}{display_name}")
            
            # Handle file contents if requested
            if data.get("_type") == "file" and include_modules:
                code_file = data["_data"]
                self._render_file_contents(code_file, next_prefix, lines, include_types)
            elif data.get("_type") != "file":
                # This is a directory - recursively render its contents
                self._render_tree_node(data, next_prefix, is_last_item, lines, 
                                    include_modules, include_types, depth + 1)

    def _render_file_contents(self, code_file: 'CodeFileModel', prefix: str, 
                            lines: list, include_types: bool):
        """
        Render the contents of a file in the tree.
        
        Args:
            code_file: The CodeFileModel to render
            prefix: Current line prefix
            lines: List to append lines to
            include_types: Whether to include type prefixes
        """
        contents = []
        
        # Collect all file-level items
        for variable in code_file.variables:
            name = f"V {variable.name}" if include_types else variable.name
            contents.append(("variable", name, None))
        
        for function in code_file.functions:
            name = f" {function.name}" if include_types else function.name
            contents.append(("function", name, None))
        
        for class_def in code_file.classes:
            name = f"C {class_def.name}" if include_types else class_def.name
            contents.append(("class", name, class_def))
        
        # Sort: variables, functions, then classes
        contents.sort(key=lambda x: (
            {"variable": 0, "function": 1, "class": 2}[x[0]], 
            x[1]
        ))
        
        for i, (item_type, name, class_def) in enumerate(contents):
            is_last_item = i == len(contents) - 1
            
            if is_last_item:
                current_prefix = "└── "
                next_prefix = prefix + "    "
            else:
                current_prefix = "├── "
                next_prefix = prefix + "│   "
            
            lines.append(f"{prefix}{current_prefix}{name}")
            
            # If it's a class, render its contents
            if item_type == "class" and class_def:
                self._render_class_contents(class_def, next_prefix, lines, include_types)

    def _render_class_contents(self, class_def: 'ClassDefinition', prefix: str, 
                            lines: list, include_types: bool):
        """
        Render the contents of a class in the tree.
        
        Args:
            class_def: The ClassDefinition to render
            prefix: Current line prefix
            lines: List to append lines to
            include_types: Whether to include type prefixes
        """
        class_contents = []
        
        # Collect class attributes
        for attribute in class_def.attributes:
            name = f"A {attribute.name}" if include_types else attribute.name
            class_contents.append(("attribute", name))
        
        # Collect class methods
        for method in class_def.methods:
            name = f"M {method.name}" if include_types else method.name
            class_contents.append(("method", name))
        
        # Sort: attributes first, then methods
        class_contents.sort(key=lambda x: (
            {"attribute": 0, "method": 1}[x[0]], 
            x[1]
        ))
        
        for i, (item_type, name) in enumerate(class_contents):
            is_last_item = i == len(class_contents) - 1
            
            if is_last_item:
                current_prefix = "└── "
            else:
                current_prefix = "├── "
            
            lines.append(f"{prefix}{current_prefix}{name}")