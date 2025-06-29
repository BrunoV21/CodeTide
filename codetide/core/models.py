from .common import CONTEXT_INTRUCTION, TARGET_INSTRUCTION, wrap_content
from .defaults import BREAKLINE
from .logs import logger

from pydantic import BaseModel, Field, RootModel, computed_field, field_validator
from typing import Any, Dict, List, Optional, Literal, Union
from collections import defaultdict
import json

class BaseCodeElement(BaseModel):
    """Base class representing any code element with file path and raw content handling."""
    file_path: str = ""
    raw :Optional[str] = ""
    stored_unique_id :Optional[str]=None

    @field_validator("raw")
    @classmethod
    def apply_second_line_indent_to_first(cls, value):
        """Normalizes raw content by ensuring consistent line indentation."""

        if not value:
            return value

        lines = value.splitlines()
        return "\n".join(lines)

    @property
    def file_path_without_suffix(self)->str:
        """Returns file path without extension, with path separators converted to dots."""

        split_file_path = self.file_path.split(".")[:-1]
        if not split_file_path:
            split_file_path = [self.file_path]
        return ".".join(split_file_path).replace("\\", ".").replace("/", ".")
    
    @computed_field
    def unique_id(self) -> str:
        """Generates unique identifier combining file path and element name."""

        if self.stored_unique_id is not None:
            return self.stored_unique_id
        
        file_path_without_suffix = self.file_path_without_suffix
        if file_path_without_suffix:
            file_path_without_suffix = f"{file_path_without_suffix}."

        return f"{file_path_without_suffix}{self.name}"
    
    @unique_id.setter
    def unique_id(self, value :str):
        self.stored_unique_id = value 

class CodeReference(BaseModel):
    """Represents a reference to another code element with type information."""
    unique_id :Optional[str]=None
    name: str
    type: Optional[Literal["import", "variable", "function", "class", "attribute", "method", "inheritance", "type_hint"]]=None

class ImportStatement(BaseCodeElement):
    """Represents an import statement with source, alias, and import type details."""
    source: Optional[str] = None  # The module/package being imported from
    name :Optional[str] = None  # The alias for the import
    alias: Optional[str] = None  # The alias for the import
    import_type: Literal["absolute", "relative", "side_effect"] = "absolute"
    definition_id :Optional[str]=None # ID to store where the Import is defined if from another file, none if is package
    raw: str=""
    
    @property
    def as_dependency(self)->str:
        return self.alias or self.name or self.source

class VariableDeclaration(BaseCodeElement):
    """Represents a variable declaration with type hints, value, and modifiers."""
    name: str
    type_hint: Optional[str] = None
    value: Optional[str] = None    
    modifiers: List[str] = Field(default_factory=list)  # e.g., "final", "abstract"
    references: List[CodeReference] = []
    raw :Optional[str] = ""

class Parameter(BaseModel):
    """Represents a function parameter with type hint and default value."""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None

    @computed_field
    def is_optional(self)->bool:
        return bool(self.default_value)


class FunctionSignature(BaseModel):
    """Contains function signature information including parameters and return type."""
    parameters: List[Parameter] = []
    return_type: Optional[str] = None

    @property
    def type_hints(self)->List[str]:
        """Returns list of all type hints including parameters and return type."""
        return [
            param.type_hint for param in self.parameters
        ] + [self.return_type]

class FunctionDefinition(BaseCodeElement):
    """Represents a function definition with signature, modifiers, and references."""
    name: str
    signature: Optional[FunctionSignature]=None
    modifiers: List[str] = Field(default_factory=list)  # e.g., "async", "generator", etc.
    decorators: List[str] = Field(default_factory=list)
    docstring: Optional[str]=None
    references: List[CodeReference] = Field(default_factory=list)

class MethodDefinition(FunctionDefinition):
    """Represents a class method with association to its containing class."""
    class_id :str=""

class ClassAttribute(VariableDeclaration):
    """Represents a class attribute with visibility modifiers."""
    class_id :str=""
    visibility: Literal["public", "protected", "private"] = "public"

class ClassDefinition(BaseCodeElement):
    """Represents a class definition with bases, attributes, methods, and references."""
    name: str
    bases: List[str] = Field(default_factory=list)
    attributes: List[ClassAttribute] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)
    bases_references: List[CodeReference] = Field(default_factory=list)
    docstring: Optional[str] = None

    @property
    def header(self)->Optional[str]:
        if not self.docstring:
            return None
        
        return f"{self.docstring}{BREAKLINE}{BREAKLINE.join([attr.raw for attr in self.attributes])}"
    
    def add_method(self, method :MethodDefinition):        
        """Adds method to class while setting proper file path and unique ID."""

        method.file_path = self.file_path
        method.unique_id = f"{self.unique_id}.{method.name}"
        method.class_id = self.unique_id
        self.methods.append(method)

    def add_attribute(self, attribute :ClassAttribute):
        """Adds attribute to class while setting proper file path and unique ID."""

        attribute.file_path = self.file_path
        attribute.unique_id = f"{self.unique_id}.{attribute.name}"
        attribute.class_id = self.unique_id
        self.attributes.append(attribute)

    @property
    def references(self)->List[CodeReference]:
        """Aggregates all references from bases, attributes, and methods."""

        all_references = []
        all_references.extend(self.bases_references)
        all_references.extend(
            sum([attribute.references for attribute in self.attributes], [])
        )
        all_references.extend(
            sum([method.references for method in self.methods], [])
        )
        return all_references
    
    @property
    def all_methods_ids(self)->List[str]:
        return [
            method.unique_id for method in self.methods
        ]
    
    def get_slim_raw(self)->str:
        if not self.docstring:
            return self.raw
        
        return self.header

class CodeFileModel(BaseModel):
    """Represents a code file with imports, variables, functions, and classes."""
    file_path: str
    imports: List[ImportStatement] = Field(default_factory=list)
    variables: List[VariableDeclaration] = Field(default_factory=list)
    functions: List[FunctionDefinition] = Field(default_factory=list)
    classes: List[ClassDefinition] = Field(default_factory=list)
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
        """Retrieves any code element in file by its unique_id through exhaustive search."""

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
        """Finds import statement in file by unique_id through direct lookup."""

        for importStatement in self.imports:
            if unique_id == importStatement.unique_id:
                return importStatement
        return None
    
    @property
    def list_raw_contents(self)->List[str]:
        """Returns list of raw contents for all classes, functions, and variables."""

        raw :List[str] = []

        for classDefintion in self.classes:
            raw.append(classDefintion.raw)
        
        for function in self.functions:
            raw.append(function.raw)

        for variable in self.variables:
            raw.append(variable.raw)

        return raw
    
class PartialClasses(BaseModel):
    """Represents partially defined classes with headers, attributes, and methods."""
    class_id :str
    class_header :str
    filepath :str
    attributes :List[ClassAttribute] = Field(default_factory=list)
    methods :List[MethodDefinition] = Field(default_factory=list)

    @property
    def raw(self)->str:
        return f"{self.class_header}{BREAKLINE}{BREAKLINE.join(self.attributes)}{BREAKLINE}{(2*BREAKLINE).join(self.methods)}" # noqa: E999
    
class CodeContextStructure(BaseModel):
    """Structured collection of code elements for context with request tracking."""
    imports :Dict[str, ImportStatement] = Field(default_factory=dict)
    variables :Dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions :Dict[str, FunctionDefinition] = Field(default_factory=dict)
    classes :Dict[str, ClassDefinition] = Field(default_factory=dict)
    classes_headers :Dict[str, ClassDefinition] = Field(default_factory=dict)
    class_attributes :Dict[str, ClassAttribute] = Field(default_factory=dict)
    class_methods :Dict[str, MethodDefinition] = Field(default_factory=dict)
    requested_elements :Optional[Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]] = Field(default_factory=dict)
    preloaded :Optional[Dict[str, str]]=Field(default_factory=dict)

    _cached_elements :Dict[str, Any] = dict()
    _unique_class_elements_ids :List[str] = list()

    @staticmethod
    def trim(raw: str, top_lines: int = 15) -> str:
        """Trims content to specified lines with ellipsis while preserving indentation."""

        lines = raw.splitlines()
        if len(lines) <= top_lines:
            return "\n".join(lines)
        
        trimmed = lines[:top_lines]
        
        # Determine indentation from the last line
        last_line = trimmed[-1]
        indent = len(last_line) - len(last_line.lstrip())
        ellipsis_line = " " * indent + "..."
        
        return "\n".join(trimmed + [ellipsis_line])

    def add_requested_element(self, element :Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition, ClassAttribute, MethodDefinition]):
        """Adds element to requested collection and tracks class associations."""

        if isinstance(element, (ClassDefinition, ClassAttribute, MethodDefinition)):
            element_class_id = element.unique_id if isinstance(element, ClassDefinition) else element.class_id
            if element_class_id not in self._unique_class_elements_ids:
                self._unique_class_elements_ids.append(element_class_id)

        self.requested_elements[element.unique_id ] = element

    def add_import(self, import_statement :ImportStatement):
        """Adds import to context if not already present in requested elements."""

        if import_statement.unique_id in self.imports or import_statement.unique_id in self.requested_elements:
            return
        self.imports[import_statement.unique_id] = import_statement

    def add_class_method(self, method :MethodDefinition):
        """Adds method to context if its class isn't in requested elements."""

        if method.class_id in self.requested_elements:
            return

        if method.class_id not in self._unique_class_elements_ids:
            self._unique_class_elements_ids.append(method.class_id)

        self.class_methods[method.unique_id] = method

    def add_class_attribute(self, attribute :ClassAttribute):
        """Adds attribute to context if its class isn't in requested elements."""

        if attribute.class_id in self.requested_elements:
            return

        if attribute.class_id not in self._unique_class_elements_ids:
            self._unique_class_elements_ids.append(attribute.class_id)
            
        self.class_attributes[attribute.unique_id] = attribute

    def add_variable(self, variable: VariableDeclaration):
        """Adds variable to context if not already present in requested elements."""

        if variable.unique_id in self.variables or variable.unique_id in self.requested_elements:
            return
        self.variables[variable.unique_id] = variable

    def add_function(self, function: ClassDefinition):
        """Adds function to context if not already present in requested elements."""

        if function.unique_id in self.functions or function.unique_id in self.requested_elements:
            return
        self.functions[function.unique_id] = function

    def add_class(self, cls: ClassDefinition):
        """Adds class to context if not already present in requested elements."""

        if cls.unique_id in self.classes or cls.unique_id in self.requested_elements:
            return
        self.classes[cls.unique_id] = cls

    def add_class_header(self, cls: ClassDefinition):
        """Adds class header to context if not already present in requested elements."""
        
        if cls.unique_id in self.classes or cls.unique_id in self.requested_elements:
            return
        self.classes_headers[cls.unique_id] = cls

    def add_preloaded(self, preloaded :Dict[str, str]):
        """Merges preloaded file contents into the context."""

        self.preloaded.update(preloaded)

    def as_list_str(self, slim :Optional[bool]=True)->List[List[str]]:
        """Organizes elements by file path and wraps content with filepath metadata."""

        partially_filled_classes :Dict[str, PartialClasses]= {}

        raw_elements_by_file = defaultdict(list)

        # Assuming each entry has a `.raw` (str) and `.filepath` (str) attribute
        for entry in self.imports.values():
            raw_elements_by_file["PACKAGES"].append(entry.raw)

        for entry in self.variables.values():
            raw_elements_by_file[entry.file_path].append(f"\n{entry.raw}")

        for entry in self.functions.values():
            if slim and entry.docstring:
                content = entry.docstring
            else:
                content = entry.raw
                
            raw_elements_by_file[entry.file_path].append(f"\n{content}")

        for entry in self.classes.values():
            if slim:
                content = entry.get_slim_raw()
            else:
                content = entry.raw

            raw_elements_by_file[entry.file_path].append(f"\n{content}")
            
        for entry in self.classes_headers.values():
            raw_elements_by_file[entry.file_path].append(f"\n{self.trim(entry.raw) if slim else entry.raw}")

        unique_class_elements_not_in_classes = set(self._unique_class_elements_ids) - set(self.classes.keys()) - set(self.classes_headers.keys()) - set(self.requested_elements)
            
        for target_class in unique_class_elements_not_in_classes:
            classObj :ClassDefinition = self._cached_elements.get(target_class)
            if classObj is not None:
                partially_filled_classes[classObj.unique_id] = PartialClasses(
                    filepath=classObj.file_path,
                    class_id=classObj.unique_id,
                    class_header= classObj.header or classObj.raw.split("\n")[0]
                )

        for class_attribute in self.class_attributes.values():
            if class_attribute.class_id in unique_class_elements_not_in_classes:
                partially_filled_classes[classObj.unique_id].attributes.append(f"\n{class_attribute.raw}")

        for class_method in self.class_methods.values():
            if class_method.class_id in unique_class_elements_not_in_classes:
                if not partially_filled_classes[classObj.unique_id].methods:
                    partially_filled_classes[classObj.unique_id].methods.append("    ...")
                
                if slim and class_method.docstring:
                    content = class_method.docstring
                else:
                    content = class_method.raw

                partially_filled_classes[classObj.unique_id].methods.append(content)

        for partial in partially_filled_classes.values():
            raw_elements_by_file[partial.filepath].append(f"\n{partial.raw}")

        for requested_elemtent in self.requested_elements.values():
            if isinstance(requested_elemtent, (ClassAttribute, MethodDefinition)):
                classObj :ClassDefinition = self._cached_elements.get(requested_elemtent.class_id)
                requested_elemtent.raw = f"{classObj.raw.split(BREAKLINE)[0]}{BREAKLINE}    ...{2*BREAKLINE}{requested_elemtent.raw}"

        wrapped_list = [
            [
                wrap_content(content="\n".join(elements), filepath=filepath)
                for filepath, elements in raw_elements_by_file.items()
            ], [
                wrap_content(content=content, filepath=filepath)
                for filepath, content in self.preloaded.items()
            ] + [
                wrap_content(content=requested_elemtent.raw, filepath=requested_elemtent.file_path)
                for requested_elemtent in self.requested_elements.values()
            ]
        ]

        return wrapped_list

    @classmethod
    def from_list_of_elements(cls,
        elements: list,
        retrieved_elements_reference_type :List[Optional[str]]=None,
        requested_element_index :List[int]=[0],
        preloaded_files :Optional[List[Dict[str, str]]]=None) -> 'CodeContextStructure':
        """Creates context structure from elements list with request tracking."""

        instance = cls()
        # Normalize negative indices to positive
        normalized_indices = [
            idx if idx >= 0 else len(elements) + idx
            for idx in requested_element_index
        ]

        # Optional: Ensure indices are within bounds
        normalized_indices = [
            idx for idx in normalized_indices
            if 0 <= idx < len(elements)
        ]

        if not retrieved_elements_reference_type:
            retrieved_elements_reference_type = [
                None for _ in elements
            ]

        for i, (element, reference_type) in enumerate(zip(elements, retrieved_elements_reference_type)):
            if i in requested_element_index:
                instance.add_requested_element(element)
            elif isinstance(element, ImportStatement):
                instance.add_import(element)
            elif isinstance(element, ClassDefinition):
                if reference_type == "type_hint":
                    instance.add_class_header(element)
                    continue
                instance.add_class(element)
            elif isinstance(element, MethodDefinition):
                instance.add_class_method(element)
            elif isinstance(element, ClassAttribute):
                instance.add_class_attribute(element)
            elif isinstance(element, VariableDeclaration):
                instance.add_variable(element)
            elif isinstance(element, FunctionDefinition):
                instance.add_function(element)
            else:
                raise TypeError(f"Unsupported element type: {type(element).__name__}")
        
        if preloaded_files:
            instance.add_preloaded(preloaded_files)

        return instance

class CodeBase(RootModel):
    """Root model representing complete codebase with file hierarchy and caching."""
    root: List[CodeFileModel] = Field(default_factory=list)
    _cached_elements :Dict[str, Any] = dict()

    def _build_cached_elements(self, force_update :bool=False):
        """Builds cache of all elements with unique IDs across entire codebase."""
        
        if not self._cached_elements or force_update:
            for codeFile in self.root:
                for unique_id, element in codeFile.all_classes(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        # print(f"CLASS {unique_id} already exists")
                        continue
                    self._cached_elements[unique_id] = element

                    for classAttribute in element.attributes:
                        if classAttribute.unique_id in self._cached_elements:
                            # print(f"CLASS ATTRIBUTE {classAttribute.unique_id} already exists")
                            continue
                        self._cached_elements[classAttribute.unique_id] = classAttribute
                    
                    for classMethod in element.methods:
                        if classMethod.unique_id in self._cached_elements:
                            ### due to setters vs properties
                            # print(f"CLASS METHOD {classMethod.unique_id } already exists")
                            continue
                        self._cached_elements[classMethod.unique_id] = classMethod
            
                for unique_id, element in codeFile.all_functions(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        # print(f"FUNCTION {unique_id} already exists")
                        continue
                    self._cached_elements[unique_id] = element

                for unique_id, element in codeFile.all_variables(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        # print(f"VARIABLE {unique_id} already exists")
                        continue
                    self._cached_elements[unique_id] = element

            ### DO IMPORT LATER
            for codeFile in self.root:
                for unique_id, element in codeFile.all_imports(as_dict=True).items():
                    ### TODO double check this later with tests
                    if element.definition_id and element.definition_id in self._cached_elements:
                        self._cached_elements[unique_id] = self._cached_elements[element.definition_id]
                    elif unique_id in self._cached_elements:
                        # print(f"IMPORT {unique_id} already exists")
                        continue
                    else:
                        self._cached_elements[unique_id] = element
                

    def _list_all_unique_ids_for_property(self, property :Literal["classes", "functions", "variables", "imports"])->List[str]:
        """Aggregates unique IDs for specified element type across all files."""
        
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
        """Finds import statement in codebase by unique_id through file search."""

        match = None
        for codeFile in self.root:
            match = codeFile.get_import(unique_id)
            if match is not None:
                return match
        return match

    def get_tree_view(self, include_modules: bool = False, include_types: bool = False) -> str:
        """Generates ASCII tree view of codebase structure with optional details."""
       
        # Build the nested structure first
        tree_dict = self._build_tree_dict()
        
        # Convert to ASCII tree
        lines = []
        self._render_tree_node(tree_dict, "", True, lines, include_modules, include_types)
        
        return "\n".join(lines)

    def _build_tree_dict(self) -> dict:
        """Creates nested dictionary representing codebase directory structure."""

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

    def _render_tree_node(self, node: dict, prefix: str, is_last: bool, lines: list, include_modules: bool, include_types: bool, depth: int = 0):
        """Recursively renders tree node with ASCII art and optional type prefixes."""
        
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

    def _render_file_contents(self, code_file: CodeFileModel, prefix: str, lines: list, include_types: bool):
        """Renders file contents in tree view with variables, functions, and classes."""

        contents = []
        
        # Collect all file-level items
        for variable in code_file.variables:
            name = f"V {variable.name}" if include_types else variable.name
            contents.append(("variable", name, None))
        
        for function in code_file.functions:
            name = f"F {function.name}" if include_types else function.name
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
        """Renders class contents in tree view with attributes and methods."""

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

    def get(self,
            unique_id :Union[str, List[str]],
            degree :int=1,
            as_string :bool=False,
            as_list_str :bool=False,
            slim :Optional[bool]=False,
            preloaded_files :Optional[Dict[str, str]]=None)->Union[CodeContextStructure, str, List[str]]:
        """Retrieves code context with specified elements and their references."""

        if not self._cached_elements:
            logger.debug("Building cached elements for the first time")
            self._build_cached_elements()
                
        if isinstance(unique_id, str):
            unique_id = [unique_id]

        references_ids = unique_id
        references_types = [None for _ in unique_id]
        retrieved_elements = []
        retrieved_elements_reference_type = []
        retrieved_ids = []
        first_swipe = True

        while True:
            new_references_ids = []
            new_references_types = []
            logger.debug(f"Current degree level: {degree}, processing {len(references_ids)} references")
            
            for i, reference in enumerate(references_ids):
                # print(reference)
                element = self._cached_elements.get(reference)
                processed = False
                if (
                    element is not None and
                    element.unique_id in retrieved_ids and not first_swipe and references_types[i] and slim
                ):
                    el_index = retrieved_elements.index(element)
                    if not retrieved_elements_reference_type[el_index]:
                        retrieved_elements_reference_type[el_index] = references_types[i]
                        processed = True

                if (
                    element is not None and
                    element.unique_id not in retrieved_ids and
                    (not preloaded_files or element.file_path not in preloaded_files or first_swipe)
                ):
                    retrieved_elements.append(element)
                    retrieved_ids.append(element.unique_id)
                    if not processed:
                        retrieved_elements_reference_type.append(references_types[i])
                    logger.debug(f"Added element: {element.unique_id} ({element.__class__.__name__})")

                    if hasattr(element, "references") and degree >= 0:
                        new_refs = [
                            _reference for _reference in element.references
                            if _reference.unique_id and _reference.unique_id not in references_ids
                        ]

                        new_references_types.extend([ref.type if slim else None for ref in new_refs])

                        ### TODO need a way to distinguish between references that are used in code and references that are functionsignature
                        ### in the case of function signature only the methods that are used in the requested elements [methods / attr if class] should be present
                        new_references_ids.extend([ref.unique_id for ref in new_refs])
                        if new_refs:
                            logger.debug(f"Found {len(new_refs)} new references from {element.unique_id}")


            if degree == 0:
                logger.debug("Reached maximum degree depth")
                break

            references_ids = new_references_ids.copy()
            references_types = new_references_types.copy()
            first_swipe = False
            degree -= 1

        logger.info(f"Retrieved {len(retrieved_elements)} total elements")

        # for _id, _type in zip(retrieved_ids, retrieved_elements_reference_type):
        #     if _type:
        #         print(f"{_id} -> {_type}")
        
        assert len(retrieved_elements_reference_type) == len(retrieved_elements), "Mismatch between retrieved elements and retrieved reference types"
        codeContext = CodeContextStructure.from_list_of_elements(
            retrieved_elements, 
            retrieved_elements_reference_type,
            requested_element_index=[i for i in range(len(unique_id)-len(preloaded_files or []))], 
            preloaded_files=preloaded_files
        )
        codeContext._cached_elements = self._cached_elements

        if as_string:
            context = codeContext.as_list_str(slim)
            if context[0]:
                context.insert(0, [CONTEXT_INTRUCTION])
                context.insert(-1, [TARGET_INSTRUCTION])
            logger.debug(f"Returning as string with {len(context)} sections")
            return "\n\n".join(sum(context, []))
            
        elif as_list_str:
            flat_list = sum(codeContext.as_list_str(), [])
            logger.debug(f"Returning as list with {len(flat_list)} items")
            return flat_list
            
        else:
            logger.debug("Returning raw CodeContextStructure")
            return codeContext
        
    def serialize_cache_elements(self, indent :int=4)->str:
        """Serializes cached elements to JSON for storage."""
        
        return json.dumps(
            {
                key: value.model_dump()
                for key, value in self._cached_elements
            }
        )

    def deserialize_cache_elements(self, contents :str):
        self._cached_elements = json.loads(contents)
        ### TODO need to handle model validates and so on
        # return json.dumps(
        #     {
        #         key: value.model_dump()
        #         for key, value in self._cached_elements
        #     }
        # )

    @property
    def unique_ids(self)->List[str]:
        if not self._cached_elements:
            self._build_cached_elements()

        return list(self._cached_elements.keys())

# TODO add mcp support for agent -> leverage CodeFile pydantic model to apply changes via unique_ids and generate file from there