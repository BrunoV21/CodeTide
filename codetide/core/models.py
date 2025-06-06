from codetide.core.common import CONTEXT_INTRUCTION, TARGET_INSTRUCTION, wrap_content

from pydantic import BaseModel, Field, computed_field, field_validator
from typing import Dict, List, Optional, Set, Union, Any, Literal
from collections import defaultdict
import hashlib
import json

class BaseCodeElement(BaseModel):
    file_path: str = ""
    raw: Optional[str] = ""
    stored_unique_id: Optional[str] = None
    _hash: Optional[str] = None
    _dependencies_hash: Optional[str] = None

    @field_validator("raw")
    @classmethod
    def apply_second_line_indent_to_first(cls, value):
        if not value:
            return value

        lines = value.splitlines()
        return "\n".join(lines)

    @property
    def file_path_without_suffix(self) -> str:
        return "".join(self.file_path.split(".")[:-1]).replace("\\", ".").replace("/", ".")
    
    @computed_field
    def unique_id(self) -> str:
        """Generate a unique ID for the function definition"""
        if self.stored_unique_id is not None:
            return self.stored_unique_id
        
        file_path_without_suffix = self.file_path_without_suffix
        if file_path_without_suffix:
            file_path_without_suffix = f"{file_path_without_suffix}."

        return f"{file_path_without_suffix}{self.name}"
    
    @unique_id.setter
    def unique_id(self, value: str):
        self.stored_unique_id = value

    def get_content_hash(self) -> str:
        """Generate hash based on element's content"""
        if self._hash is None:
            # Create a canonical representation for hashing
            content_dict = self._get_hashable_content()
            content_str = json.dumps(content_dict, sort_keys=True)
            self._hash = hashlib.sha256(content_str.encode()).hexdigest()
        return self._hash
    
    def get_dependencies_hash(self, dependency_hashes: List[str]) -> str:
        """Generate hash including dependencies"""
        if self._dependencies_hash is None:
            content_hash = self.get_content_hash()
            all_hashes = [content_hash] + sorted(dependency_hashes)
            combined = "".join(all_hashes)
            self._dependencies_hash = hashlib.sha256(combined.encode()).hexdigest()
        return self._dependencies_hash
    
    def _get_hashable_content(self) -> Dict:
        """Override in subclasses to define what content to hash"""
        return {
            "file_path": self.file_path,
            "name": getattr(self, 'name', ''),
            "raw": self.raw or ""
        }
    
    def invalidate_hash(self):
        """Clear cached hashes when content changes"""
        self._hash = None
        self._dependencies_hash = None

class CodeReference(BaseModel):
    """Reference to another code element"""
    unique_id: Optional[str] = None
    name: str

class ImportStatement(BaseCodeElement):
    """Generic representation of an import statement"""
    source: str  # The module/package being imported from
    name: Optional[str] = None  # The alias for the import
    alias: Optional[str] = None  # The alias for the import
    import_type: Literal["absolute", "relative", "side_effect"] = "absolute"
    definition_id: Optional[str] = None # ID to store where the Import is defined if from another file, none if is package
    raw: str = ""
    
    @property
    def as_dependency(self) -> str:
        return self.alias or self.name or self.source

    def _get_hashable_content(self) -> Dict:
        return {
            "source": self.source,
            "name": self.name,
            "alias": self.alias,
            "import_type": self.import_type
        }

class VariableDeclaration(BaseCodeElement):
    """Representation of a variable declaration"""
    name: str
    type_hint: Optional[str] = None
    value: Optional[str] = None    
    modifiers: List[str] = Field(default_factory=list)  # e.g., "final", "abstract"
    references: List[CodeReference] = []
    raw: Optional[str] = ""

    def _get_hashable_content(self) -> Dict:
        return {
            "name": self.name,
            "type_hint": self.type_hint,
            "value": self.value,
            "modifiers": sorted(self.modifiers)
        }

class Parameter(BaseModel):
    """Function parameter representation"""
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None

    @computed_field
    def is_optional(self) -> bool:
        return bool(self.default_value)

class FunctionSignature(BaseModel):
    """Function signature with parameters and return type"""
    parameters: List[Parameter] = []
    return_type: Optional[str] = None

class FunctionDefinition(BaseCodeElement):
    """Representation of a function definition"""
    name: str
    signature: Optional[FunctionSignature] = None
    modifiers: List[str] = Field(default_factory=list)  # e.g., "async", "generator", etc.
    decorators: List[str] = Field(default_factory=list)
    references: List[CodeReference] = Field(default_factory=list)

    def _get_hashable_content(self) -> Dict:
        signature_dict = {}
        if self.signature:
            signature_dict = {
                "parameters": [
                    {
                        "name": p.name,
                        "type_hint": p.type_hint,
                        "default_value": p.default_value
                    }
                    for p in self.signature.parameters
                ],
                "return_type": self.signature.return_type
            }
        
        return {
            "name": self.name,
            "signature": signature_dict,
            "modifiers": sorted(self.modifiers),
            "decorators": sorted(self.decorators)
        }

class MethodDefinition(FunctionDefinition):
    """Class method representation"""
    class_id: str = ""

class ClassAttribute(VariableDeclaration):
    """Class attribute representation"""
    class_id: str = ""
    visibility: Literal["public", "protected", "private"] = "public"

class ClassDefinition(BaseCodeElement):
    """Representation of a class definition"""
    name: str
    bases: List[str] = Field(default_factory=list)
    attributes: List[ClassAttribute] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)
    bases_references: List[CodeReference] = Field(default_factory=list)
    
    def add_method(self, method: MethodDefinition):
        method.file_path = self.file_path
        method.unique_id = f"{self.unique_id}.{method.name}"
        method.class_id = self.unique_id
        self.methods.append(method)

    def add_attribute(self, attribute: ClassAttribute):
        attribute.file_path = self.file_path
        attribute.unique_id = f"{self.unique_id}.{attribute.name}"
        attribute.class_id = self.unique_id
        self.attributes.append(attribute)

    @property
    def references(self) -> List[CodeReference]:
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
    def all_methods_ids(self) -> List[str]:
        return [
            method.unique_id for method in self.methods
        ]

    def _get_hashable_content(self) -> Dict:
        return {
            "name": self.name,
            "bases": sorted(self.bases),
            "attribute_hashes": [attr.get_content_hash() for attr in self.attributes],
            "method_hashes": [method.get_content_hash() for method in self.methods]
        }

class MerkleNode(BaseModel):
    """Represents a node in the Merkle tree"""
    hash_value: str
    children: List[str] = Field(default_factory=list)  # List of child hashes
    element_id: Optional[str] = None  # Reference to actual code element
    node_type: str = "internal"  # "leaf", "internal", "root"

class MerkleCodeTree(BaseModel):
    """Merkle tree for tracking code element changes"""
    nodes: Dict[str, MerkleNode] = Field(default_factory=dict)
    root_hash: Optional[str] = None
    element_to_hash: Dict[str, str] = Field(default_factory=dict)  # element_id -> hash
    hash_to_elements: Dict[str, List[str]] = Field(default_factory=dict)  # hash -> [element_ids]
    dependency_graph: Dict[str, Set[str]] = Field(default_factory=dict)  # element_id -> dependencies
    
    def add_element(self, element: BaseCodeElement, dependencies: List[str] = None):
        """Add a code element to the Merkle tree"""
        dependencies = dependencies or []
        element_id = element.unique_id
        
        # Get dependency hashes
        dep_hashes = []
        for dep_id in dependencies:
            if dep_id in self.element_to_hash:
                dep_hashes.append(self.element_to_hash[dep_id])
        
        # Calculate element hash including dependencies
        element_hash = element.get_dependencies_hash(dep_hashes)
        
        # Update mappings
        self.element_to_hash[element_id] = element_hash
        if element_hash not in self.hash_to_elements:
            self.hash_to_elements[element_hash] = []
        self.hash_to_elements[element_hash].append(element_id)
        
        # Store dependencies
        self.dependency_graph[element_id] = set(dependencies)
        
        # Create leaf node
        leaf_node = MerkleNode(
            hash_value=element_hash,
            element_id=element_id,
            node_type="leaf"
        )
        self.nodes[element_hash] = leaf_node
    
    def build_tree(self):
        """Build the complete Merkle tree from leaf nodes"""
        current_level = [node.hash_value for node in self.nodes.values() if node.node_type == "leaf"]
        
        while len(current_level) > 1:
            next_level = []
            
            # Process pairs of nodes
            for i in range(0, len(current_level), 2):
                left_hash = current_level[i]
                right_hash = current_level[i + 1] if i + 1 < len(current_level) else current_level[i]
                
                # Create parent hash
                combined = left_hash + right_hash
                parent_hash = hashlib.sha256(combined.encode()).hexdigest()
                
                # Create internal node
                internal_node = MerkleNode(
                    hash_value=parent_hash,
                    children=[left_hash, right_hash] if left_hash != right_hash else [left_hash],
                    node_type="internal"
                )
                self.nodes[parent_hash] = internal_node
                next_level.append(parent_hash)
            
            current_level = next_level
        
        # Set root hash
        if current_level:
            self.root_hash = current_level[0]
            if self.root_hash in self.nodes:
                self.nodes[self.root_hash].node_type = "root"
    
    def get_affected_elements(self, changed_element_id: str) -> Set[str]:
        """Get all elements affected by a change to the given element"""
        affected = set()
        
        def find_dependents(element_id: str):
            for dep_element_id, deps in self.dependency_graph.items():
                if element_id in deps:
                    affected.add(dep_element_id)
                    find_dependents(dep_element_id)  # Recursive search
        
        affected.add(changed_element_id)
        find_dependents(changed_element_id)
        return affected
    
    def update_element(self, element: BaseCodeElement, dependencies: List[str] = None):
        """Update an element and recalculate affected hashes"""
        element_id = element.unique_id
        old_hash = self.element_to_hash.get(element_id)
        
        # Get affected elements before updating
        affected_elements = self.get_affected_elements(element_id)
        
        # Remove old mappings
        if old_hash and old_hash in self.hash_to_elements:
            if element_id in self.hash_to_elements[old_hash]:
                self.hash_to_elements[old_hash].remove(element_id)
            if not self.hash_to_elements[old_hash]:
                del self.hash_to_elements[old_hash]
                if old_hash in self.nodes:
                    del self.nodes[old_hash]
        
        # Add updated element
        self.add_element(element, dependencies)
        
        return affected_elements
    
    def verify_integrity(self) -> bool:
        """Verify the integrity of the Merkle tree"""
        if not self.root_hash or self.root_hash not in self.nodes:
            return False
        
        def verify_node(node_hash: str) -> bool:
            if node_hash not in self.nodes:
                return False
            
            node = self.nodes[node_hash]
            
            if node.node_type == "leaf":
                return True
            
            if not node.children:
                return False
            
            # Verify children exist and hash correctly
            for child_hash in node.children:
                if not verify_node(child_hash):
                    return False
            
            # Verify parent hash is correct
            if len(node.children) == 1:
                expected_hash = hashlib.sha256(node.children[0].encode()).hexdigest()
            else:
                combined = "".join(node.children)
                expected_hash = hashlib.sha256(combined.encode()).hexdigest()
            
            return expected_hash == node_hash
        
        return verify_node(self.root_hash)

class CodeFileModel(BaseModel):
    """Representation of a single code file"""
    file_path: str
    imports: List[ImportStatement] = Field(default_factory=list)
    variables: List[VariableDeclaration] = Field(default_factory=list)
    functions: List[FunctionDefinition] = Field(default_factory=list)
    classes: List[ClassDefinition] = Field(default_factory=list)
    raw: Optional[str] = None
    merkle_tree: MerkleCodeTree = Field(default_factory=MerkleCodeTree)
    file_hash: Optional[str] = None
    
    @staticmethod
    def _list_all(entries_list: List[Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]) -> Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]:
        return {entry.unique_id: entry for entry in entries_list}

    def all_imports(self, as_dict: bool = False) -> Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.imports)
        return list(unique_dict.keys()) if not as_dict else unique_dict
    
    def all_variables(self, as_dict: bool = False) -> Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.variables)
        return list(unique_dict.keys()) if not as_dict else unique_dict
    
    def all_classes(self, as_dict: bool = False) -> Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.classes)
        return list(unique_dict.keys()) if not as_dict else unique_dict
    
    def all_functions(self, as_dict: bool = False) -> Union[List[str], Dict[str, Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]]:
        unique_dict = self._list_all(self.functions)
        return list(unique_dict.keys()) if not as_dict else unique_dict

    def add_import(self, import_statement: ImportStatement):
        import_statement.file_path = self.file_path
        self.imports.append(import_statement)

    def add_variable(self, variable_declaration: VariableDeclaration):
        variable_declaration.file_path = self.file_path
        self.variables.append(variable_declaration)

    def add_function(self, function_definition: FunctionDefinition):
        function_definition.file_path = self.file_path
        self.functions.append(function_definition)

    def add_class(self, class_definition: ClassDefinition):
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

    def get_import(self, unique_id: str) -> Optional[ImportStatement]:
        for importStatement in self.imports:
            if unique_id == importStatement.unique_id:
                return importStatement
        return None
    
    @property
    def list_raw_contents(self) -> List[str]:
        raw: List[str] = []

        for classDefintion in self.classes:
            raw.append(classDefintion.raw)
        
        for function in self.functions:
            raw.append(function.raw)

        for variable in self.variables:
            raw.append(variable.raw)

        return raw
    
    def calculate_file_hash(self) -> str:
        """Calculate hash for the entire file"""
        if not self.merkle_tree.root_hash:
            self.build_merkle_tree()
        
        file_content = {
            "file_path": self.file_path,
            "root_hash": self.merkle_tree.root_hash
        }
        content_str = json.dumps(file_content, sort_keys=True)
        self.file_hash = hashlib.sha256(content_str.encode()).hexdigest()
        return self.file_hash
    
    def build_merkle_tree(self):
        """Build Merkle tree for all elements in the file"""
        # Add all elements to the tree
        for imp in self.imports:
            self.merkle_tree.add_element(imp)
        
        for var in self.variables:
            # Find dependencies (references)
            deps = [ref.unique_id for ref in var.references if ref.unique_id]
            self.merkle_tree.add_element(var, deps)
        
        for func in self.functions:
            deps = [ref.unique_id for ref in func.references if ref.unique_id]
            self.merkle_tree.add_element(func, deps)
        
        for cls in self.classes:
            deps = [ref.unique_id for ref in cls.references if ref.unique_id]
            self.merkle_tree.add_element(cls, deps)
        
        # Build the tree structure
        self.merkle_tree.build_tree()
    
    def update_element_and_get_affected(self, unique_id: str, new_raw_content: str) -> Set[str]:
        """Update an element and return IDs of all affected elements"""
        element = self.get(unique_id)
        if not element:
            return set()
        
        # Update the raw content
        element.raw = new_raw_content
        element.invalidate_hash()
        
        # Update tree with dependencies
        if isinstance(element, VariableDeclaration):
            deps = [ref.unique_id for ref in element.references if ref.unique_id]
            return self.merkle_tree.update_element(element, deps)
        elif isinstance(element, FunctionDefinition):
            deps = [ref.unique_id for ref in element.references if ref.unique_id]
            return self.merkle_tree.update_element(element, deps)
        elif isinstance(element, ClassDefinition):
            deps = [ref.unique_id for ref in element.references if ref.unique_id]
            return self.merkle_tree.update_element(element, deps)
        
        return self.merkle_tree.update_element(element)

class PartialClasses(BaseModel):
    class_id: str
    class_header: str
    filepath: str
    attributes: List[ClassAttribute] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)

    @property
    def raw(self) -> str:
        return f"{self.class_header}\n{'\n'.join(self.attributes)}\n{'\n\n'.join(self.methods)}" # noqa: E999
    
class CodeContextStructure(BaseModel):
    imports: Dict[str, ImportStatement] = Field(default_factory=dict)
    variables: Dict[str, VariableDeclaration] = Field(default_factory=dict)
    functions: Dict[str, ClassDefinition] = Field(default_factory=dict)
    classes: Dict[str, ClassDefinition] = Field(default_factory=dict)
    class_attributes: Dict[str, ClassAttribute] = Field(default_factory=dict)
    class_methods: Dict[str, MethodDefinition] = Field(default_factory=dict)
    requested_elements: Optional[List[Union[ImportStatement, VariableDeclaration, FunctionDefinition, ClassDefinition]]] = Field(default_factory=list)

    _cached_elements: Dict[str, Any] = dict()
    _unique_class_elements_ids: List[str] = list()
    
    def add_import(self, import_statement: ImportStatement):
        if import_statement.unique_id in self.imports:
            return
        self.imports[import_statement.unique_id] = import_statement

    def add_class_method(self, method: MethodDefinition):
        if method.class_id not in self._unique_class_elements_ids:
            self._unique_class_elements_ids.append(method.class_id)

        self.class_methods[method.unique_id] = method

    def add_class_attribute(self, attribute: ClassAttribute):
        if attribute.class_id not in self._unique_class_elements_ids:
            self._unique_class_elements_ids.append(attribute.class_id)
            
        self.class_attributes[attribute.unique_id] = attribute

    def add_variable(self, variable: VariableDeclaration):
        if variable.unique_id in self.variables:
            return
        self.variables[variable.unique_id] = variable

    def add_function(self, function: ClassDefinition):
        if function.unique_id in self.functions:
            return
        self.functions[function.unique_id] = function

    def add_class(self, cls: ClassDefinition):
        if cls.unique_id in self.classes:
            return
        self.classes[cls.unique_id] = cls

    def as_list_str(self) -> List[str]:
        partially_filled_classes: Dict[str, PartialClasses] = {}

        raw_elements_by_file = defaultdict(list)

        # Assuming each entry has a `.raw` (str) and `.filepath` (str) attribute
        for entry in self.imports.values():
            raw_elements_by_file["PACKAGES"].append(entry.raw)

        for entry in self.variables.values():
            raw_elements_by_file[entry.file_path].append(entry.raw)

        for entry in self.functions.values():
            raw_elements_by_file[entry.file_path].append(entry.raw)

        for entry in self.classes.values():
            raw_elements_by_file[entry.file_path].append(entry.raw)

        unique_class_elements_not_in_classes = set(self._unique_class_elements_ids) - set(self.classes.keys())
            
        for target_class in unique_class_elements_not_in_classes:
            classObj: ClassDefinition = self._cached_elements.get(target_class)
            if classObj is not None:
                partially_filled_classes[classObj.unique_id] = PartialClasses(
                    filepath=classObj.file_path,
                    class_id=classObj.unique_id,
                    class_header=classObj.raw.split("\n")[0]
                )

        for class_attribute in self.class_attributes.values():
            if class_attribute.class_id in unique_class_elements_not_in_classes:
                partially_filled_classes[classObj.unique_id].attributes.append(class_attribute.raw)

        for class_method in self.class_methods.values():
            if class_method.class_id in unique_class_elements_not_in_classes:
                if not partially_filled_classes[classObj.unique_id].methods:
                    partially_filled_classes[classObj.unique_id].methods.append("\n    ...\n")
                partially_filled_classes[classObj.unique_id].methods.append(class_method.raw)

        for partial in partially_filled_classes.values():
            raw_elements_by_file[partial.filepath].append(partial.raw)

        for requested_elemtent in self.requested_elements:
            if isinstance(requested_elemtent, (ClassAttribute, MethodDefinition)):
                classObj: ClassDefinition = self._cached_elements.get(requested_elemtent.class_id)
                requested_elemtent.raw = f"{classObj.raw.split('\n')[0]}\n    ...\n\n{requested_elemtent.raw}"

        wrapped_list = [
            wrap_content(content="\n\n".join(elements), filepath=filepath)
            for filepath, elements in raw_elements_by_file.items()
        ] + [
            wrap_content(content=requested_elemtent.raw, filepath=requested_elemtent.file_path)
            for requested_elemtent in self.requested_elements
        ]

        return wrapped_list

    @classmethod
    def from_list_of_elements(cls, elements: list, requested_element_index: List[int] = [0]) -> 'CodeContextStructure':
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

        for i, element in enumerate(elements):
            if i in requested_element_index:
                instance.requested_elements.append(element)
            elif isinstance(element, ImportStatement):
                instance.add_import(element)
            elif isinstance(element, ClassDefinition):
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

        return instance

class CodeBase(BaseModel):
    """Root model representing a complete codebase"""
    root: List[CodeFileModel] = Field(default_factory=list)
    _cached_elements: Dict[str, Any] = dict()
    global_merkle_tree: MerkleCodeTree = Field(default_factory=MerkleCodeTree)
    file_hashes: Dict[str, str] = Field(default_factory=dict)

    def _build_cached_elements(self, force_update: bool = False):
        if not self._cached_elements or force_update:
            for codeFile in self.root:
                for unique_id, element in codeFile.all_classes(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        continue
                    self._cached_elements[unique_id] = element

                    for classAttribute in element.attributes:
                        if classAttribute.unique_id in self._cached_elements:
                            continue
                        self._cached_elements[classAttribute.unique_id] = classAttribute
                    
                    for classMethod in element.methods:
                        if classMethod.unique_id in self._cached_elements:
                            continue
                        self._cached_elements[classMethod.unique_id] = classMethod
            
                for unique_id, element in codeFile.all_functions(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        continue
                    self._cached_elements[unique_id] = element

                for unique_id, element in codeFile.all_variables(as_dict=True).items():
                    if unique_id in self._cached_elements:
                        continue
                    self._cached_elements[unique_id] = element

            for codeFile in self.root:
                for unique_id, element in codeFile.all_imports(as_dict=True).items():
                    if element.definition_id and element.definition_id in self._cached_elements:
                        self._cached_elements[unique_id] = self._cached_elements[element.definition_id]
                    elif unique_id in self._cached_elements:
                        continue
                    else:
                        self._cached_elements[unique_id] = element
                
    def _list_all_unique_ids_for_property(self, property: Literal["classes", "functions", "variables", "imports"]) -> List[str]:
        return sum([
            getattr(entry, f"all_{property}")() for entry in self.root
        ], [])
    
    def all_variables(self) -> List[str]:
        return self._list_all_unique_ids_for_property("variables")
    
    def all_functions(self) -> List[str]:
        return self._list_all_unique_ids_for_property("functions")
    
    def all_classes(self) -> List[str]:
        return self._list_all_unique_ids_for_property("classes")
    
    def all_imports(self) -> List[str]:
        return self._list_all_unique_ids_for_property("imports")
    
    def get_import(self, unique_id: str) -> Optional[ImportStatement]:
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
        tree_dict = self._build_tree_dict()
        
        lines = []
        self._render_tree_node(tree_dict, "", True, lines, include_modules, include_types)
        
        return "\n".join(lines)

    def _build_tree_dict(self) -> dict:
        """Build a nested dictionary representing the directory structure."""
        tree = {}
        
        for code_file in self.root:
            if not code_file.file_path:
                continue
                
            path_parts = code_file.file_path.replace("\\", "/").split("/")
            
            current_level = tree
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    current_level[part] = {"_type": "file", "_data": code_file}
                else:
                    if part not in current_level:
                        current_level[part] = {"_type": "directory"}
                    current_level = current_level[part]
        
        return tree

    def _render_tree_node(self, node: dict, prefix: str, is_last: bool, lines: list, 
                        include_modules: bool, include_types: bool, depth: int = 0):
        """
        Recursively render a tree node with ASCII art.
        """
        items = [(k, v) for k, v in node.items() if not k.startswith("_")]
        items.sort(key=lambda x: (x[1].get("_type", "directory") == "file", x[0]))
        
        for i, (name, data) in enumerate(items):
            is_last_item = i == len(items) - 1
            
            if is_last_item:
                current_prefix = "└── "
                next_prefix = prefix + "    "
            else:
                current_prefix = "├── "
                next_prefix = prefix + "│   "
            
            display_name = name
            if include_types:
                if data.get("_type") == "file":
                    display_name = f" {name}"
                else:
                    display_name = f"{name}"
            
            lines.append(f"{prefix}{current_prefix}{display_name}")
            
            if data.get("_type") == "file" and include_modules:
                code_file = data["_data"]
                self._render_file_contents(code_file, next_prefix, lines, include_types)
            elif data.get("_type") != "file":
                self._render_tree_node(data, next_prefix, is_last_item, lines, 
                                    include_modules, include_types, depth + 1)

    def _render_file_contents(self, code_file: 'CodeFileModel', prefix: str, 
                            lines: list, include_types: bool):
        """
        Render the contents of a file in the tree.
        """
        contents = []
        
        for variable in code_file.variables:
            name = f"V {variable.name}" if include_types else variable.name
            contents.append(("variable", name, None))
        
        for function in code_file.functions:
            name = f" {function.name}" if include_types else function.name
            contents.append(("function", name, None))
        
        for class_def in code_file.classes:
            name = f"C {class_def.name}" if include_types else class_def.name
            contents.append(("class", name, class_def))
        
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
            
            if item_type == "class" and class_def:
                self._render_class_contents(class_def, next_prefix, lines, include_types)

    def _render_class_contents(self, class_def: 'ClassDefinition', prefix: str, 
                            lines: list, include_types: bool):
        """
        Render the contents of a class in the tree.
        """
        class_contents = []
        
        for attribute in class_def.attributes:
            name = f"A {attribute.name}" if include_types else attribute.name
            class_contents.append(("attribute", name))
        
        for method in class_def.methods:
            name = f"M {method.name}" if include_types else method.name
            class_contents.append(("method", name))
        
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

    def get(self, unique_id: Union[str, List[str]], degree: int = 0, as_string: bool = False, as_list_str: bool = False) -> Union[CodeContextStructure, str, List[str]]:
        if not self._cached_elements:
            self._build_cached_elements()
            
        if isinstance(unique_id, str):
            unique_id = [unique_id]

        references_ids = unique_id
        retrieved_elements = []
        retrieved_ids = []

        while True:
            new_references_ids = []
            for reference in references_ids:
                element = self._cached_elements.get(reference)
                if element is not None and (element.unique_id not in retrieved_ids):
                    retrieved_elements.append(element)
                    retrieved_ids.append(element.unique_id)

                    if hasattr(element, "references") and degree > 0:
                        new_references_ids.extend([
                            _reference.unique_id for _reference in element.references if _reference.unique_id and _reference.unique_id not in references_ids
                        ])

            if degree == 0:
                break

            references_ids = new_references_ids.copy()

            degree -= 1

        codeContext = CodeContextStructure.from_list_of_elements(retrieved_elements, requested_element_index=[i for i in range(len(unique_id))])
        codeContext._cached_elements = self._cached_elements

        if as_string:
            context = codeContext.as_list_str()
            if len(context) > 1:
                context.insert(0, CONTEXT_INTRUCTION)
                context.insert(-1, TARGET_INSTRUCTION)

            return "\n\n".join(context)
        
        elif as_list_str:
            return codeContext.as_list_str()
        
        else:
            return codeContext
        
    def serialize_cache_elements(self, indent: int = 4) -> str:
        return json.dumps(
            {
                key: value.model_dump()
                for key, value in self._cached_elements
            }
        )

    def deserialize_cache_elements(self, contents: str):
        self._cached_elements = json.loads(contents)        
        ### TODO need to handle model validates and so on
        # return json.dumps(
        #     {
        #         key: value.model_dump()
        #         for key, value in self._cached_elements
        #     }
        # )

    @property
    def unique_ids(self) -> List[str]:
        if not self._cached_elements:
            self._build_cached_elements()

        return list(self._cached_elements.keys())

    def build_global_tree(self):
        """Build a global Merkle tree across all files"""
        for file_model in self.root:
            file_model.build_merkle_tree()
            file_hash = file_model.calculate_file_hash()
            self.file_hashes[file_model.file_path] = file_hash
            
            # Add file as a node in global tree
            file_element = BaseCodeElement()
            file_element.unique_id = file_model.file_path
            file_element._hash = file_hash
            self.global_merkle_tree.add_element(file_element)
        
        self.global_merkle_tree.build_tree()
    
    def get_changed_files(self, new_file_hashes: Dict[str, str]) -> List[str]:
        """Compare file hashes to detect changes"""
        changed_files = []
        for file_path, new_hash in new_file_hashes.items():
            old_hash = self.file_hashes.get(file_path)
            if old_hash != new_hash:
                changed_files.append(file_path)
        return changed_files