from typing import List, Dict, Optional, Tuple, Union
from pathlib import Path
import re
from pydantic import model_validator
from tqdm import tqdm
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython

from codetide.core.defaults import DEFAULT_ENCODING
from codetide.parsers.base_parser import BaseParser
from codetide.core.models import (
    CodeBase, CodeFile, Import, Function,
    Class, Variable, DependencyType
)



class PythonParser(BaseParser):
    """
    Python-specific implementation of the BaseParser using tree-sitter.
    """
    language: str = "python"
    _tree_parser: Optional[Parser] = None
    
    @property
    def tree_parser(self) -> Union[Parser, None]:
        return self._tree_parser
    
    @tree_parser.setter
    def tree_parser(self, parser: Parser):
        self._tree_parser = parser
    
    @model_validator(mode="after")
    def init_tree_parser(self) -> "PythonParser":
        """Initialize the tree-sitter parser."""
        self._tree_parser = Parser(Language(tspython.language()))
        return self
    
    def parse_file(self, file_path: Path, content: str, rootpath :Optional[Path]=None) -> Tuple[CodeFile, Dict[str, List[Union[Import, 
    Function, Class, Variable]]]]:
        """Parse a Python file and extract its components."""
        elements = self.extract_all_elements(file_path, content, rootpath)
        
        code_file = CodeFile(
            file_path=file_path.relative_to(rootpath) if rootpath is not None else file_path,
            language=self.language,
            content=content,
            imports=[imp.id for imp in elements["imports"]],
            classes=[cls.id for cls in elements["classes"]],
            functions=[func.id for func in elements["functions"]],
            variables=[var.id for var in elements["variables"]]
        )
        
        return code_file, elements
    
    def extract_imports(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Import]:
        """Extract import statements from Python code."""
        if not self.tree_parser:
            self.init_tree_parser()
            
        # Parse the code with tree-sitter
        tree = self.tree_parser.parse(content.encode(DEFAULT_ENCODING))
        root_node = tree.root_node
        
        imports = []
        self._traverse_for_imports(
            node=root_node,
            code=content.encode(DEFAULT_ENCODING),
            imports=imports,
            file_path=file_path,
            rootpath=rootpath
        )
        
        return imports
    
    def _traverse_for_imports(self, node: Node, code: bytes, imports: List[Import], file_path: Path, rootpath :Optional[Path]=None) -> None:
        """Helper method to traverse the tree for import statements."""
        if node.type in ('import_statement', 'import_from_statement'):
            import_details = self._process_import_node(node, code, file_path, rootpath)
            if import_details:
                if isinstance(import_details, list):
                    imports.extend(import_details)
                else:
                    imports.append(import_details)
                
        for child in node.children:
            self._traverse_for_imports(child, code, imports, file_path, rootpath)
    
    def _process_import_node(self, node: Node, code: bytes, file_path: Path, rootpath :Optional[Path]=None) -> Optional[Import]:
        """Process an import node and convert it to an Import model."""
        start_line = node.start_point[0] + 1  # 0-indexed to 1-indexed
        end_line = node.end_point[0] + 1
        start_col = node.start_point[1]
        end_col = node.end_point[1]
        content = code[node.start_byte:node.end_byte].decode(DEFAULT_ENCODING)
        
        if node.type == 'import_statement':
            # For a standard import statement like: import os, sys as s
            modules = []
            imported_names = []
            aliases = {}
            
            for child in node.children:
                if child.type in ('import', ','):
                    continue
                elif child.type == 'dotted_name':
                    module_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
                    modules.append(module_name)
                    # For regular imports, the imported name is the last part of the dotted name
                    imported_names.append(module_name.split('.')[-1])
                elif child.type == 'alias':
                    # Process alias
                    name_parts = []
                    alias_name = None
                    for sub in child.children:
                        if sub.type == 'dotted_name':
                            module_name = code[sub.start_byte:sub.end_byte].decode(DEFAULT_ENCODING)
                            name_parts.append(module_name)
                        elif sub.type == 'identifier':
                            alias_name = code[sub.start_byte:sub.end_byte].decode(DEFAULT_ENCODING)
                    
                    if name_parts and alias_name:
                        full_name = '.'.join(name_parts)
                        modules.append(full_name)
                        imported_names.append(full_name.split('.')[-1])
                        aliases[full_name.split('.')[-1]] = alias_name
            
            for module_name in modules:
                import_id = self.generate_element_id("import", file_path, module_name, start_line, rootpath)
                element_type, import_id = self._get_import_type(import_id, rootpath, module_name)
                return Import(
                    id=import_id,
                    name=module_name,
                    element_type=element_type,
                    language=self.language,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    start_col=start_col,
                    end_col=end_col,
                    content=content,
                    is_from_import=False,
                    module_name=module_name,
                    imported_names=imported_names,
                    aliases=aliases
                )
                
        elif node.type == 'import_from_statement':
            # For from-import statement like: from collections import deque as dq
            from_module = None
            imported_names = []
            aliases = {}
            # print(f"\n{node.children=}")
            
            for child in node.children:
                if child.type == 'dotted_name':# and from_module is None:
                    child_module = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
                    if from_module is None:
                        from_module = child_module
                    else:
                        imported_names.append(child_module)
                    # print(f"{from_module=}")
                elif child.type == 'import_statement':
                    # Process imported names within the from-import
                    for sub_child in child.children:
                        if sub_child.type == 'dotted_name':
                            name = code[sub_child.start_byte:sub_child.end_byte].decode(DEFAULT_ENCODING)
                            imported_names.append(name)
                        elif sub_child.type == 'alias':
                            # Process alias for imports
                            original_name = None
                            alias_name = None
                            for sub_sub in sub_child.children:
                                if sub_sub.type == 'identifier':
                                    if original_name is None:
                                        original_name = code[sub_sub.start_byte:sub_sub.end_byte].decode(DEFAULT_ENCODING)
                                    else:
                                        alias_name = code[sub_sub.start_byte:sub_sub.end_byte].decode(DEFAULT_ENCODING)
                                elif sub_sub.type == 'dotted_name':
                                    original_name = code[sub_sub.start_byte:sub_sub.end_byte].decode(DEFAULT_ENCODING)
                            
                            if original_name:
                                imported_names.append(original_name)
                                if alias_name:
                                    aliases[original_name] = alias_name
                elif child.type == 'star':
                    # Handle "from module import *"
                    imported_names.append('*')
            
            if from_module:
                impots_list = []
                for imported_name in imported_names:
                    import_id = self.generate_element_id("import", file_path, from_module, start_line, rootpath)
                    ###
                    # TODO handle inits jere
                    # TODO handle is module or is pacakge heres
                    element_type, import_id = self._get_import_type(import_id, rootpath, imported_name)
                    ###
                    impots_list.append(Import(
                        id=import_id,
                        name=imported_name,
                        element_type=element_type,
                        language=self.language,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        start_col=start_col,
                        end_col=end_col,
                        content=content,
                        is_from_import=True,
                        module_name=from_module,
                        imported_names=imported_names,
                        aliases=aliases
                    ))
                return impots_list
        
        return None
    
    @staticmethod
    def _get_import_type(import_id :str, rootpath :Path, module_name :Optional[str]=None)->Tuple[str, str]:

        # corrected_import_id = import_id
        if rootpath is None:
            element_type = "import"
        elif rootpath.name in import_id:
            element_type = "import_module"
        else:
            element_type = "import_package"
            # corrected_import_id =
        corrected_import_id = import_id.split(":")
        corrected_import_id = [element_type, corrected_import_id[-2]]
        if module_name:
            corrected_import_id.append(module_name)
        corrected_import_id = ":".join(corrected_import_id)

        return element_type, corrected_import_id
    
    def extract_classes(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Class]:
        """Extract class definitions from Python code."""
        if not self.tree_parser:
            self.init_tree_parser()
            
        # Parse the code with tree-sitter
        tree = self.tree_parser.parse(content.encode(DEFAULT_ENCODING))
        root_node = tree.root_node
        
        classes = []
        self._traverse_for_classes(
            node=root_node,
            code=content.encode(DEFAULT_ENCODING),
            classes=classes,
            file_path=file_path,
            rootpath=rootpath
        )
        
        return classes
    
    def _traverse_for_classes(self, node: Node, code: bytes, classes: List[Class], file_path: Path, rootpath :Optional[Path]=None) -> None:
        """Helper method to traverse the tree for class definitions."""
        if node.type == 'class_definition':
            class_details = self._process_class_node(node, code, file_path, rootpath)
            if class_details:
                classes.append(class_details)
                
        for child in node.children:
            self._traverse_for_classes(child, code, classes, file_path, rootpath)
    
    def _process_class_node(self, node: Node, code: bytes, file_path: Path, rootpath :Optional[Path]=None) -> Optional[Class]:
        """Process a class node and convert it to a Class model."""
        # Extract class name
        class_name = None
        base_classes = []
        methods = []
        decorators = []
        
        start_line = node.start_point[0] + 1  # 0-indexed to 1-indexed
        end_line = node.end_point[0] + 1
        start_col = node.start_point[1]
        end_col = node.end_point[1]
        content = code[node.start_byte:node.end_byte].decode(DEFAULT_ENCODING)
        
        for child in node.children:
            if child.type == 'identifier':
                class_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
            elif child.type == 'argument_list':
                # Extract base classes
                for arg_child in child.children:
                    if arg_child.type not in ('(', ')', ','):
                        base_class = code[arg_child.start_byte:arg_child.end_byte].decode(DEFAULT_ENCODING)
                        base_classes.append(base_class)
            elif child.type == 'decorator':
                # Extract decorators
                for dec_child in child.children:
                    if dec_child.type == 'dotted_name':
                        decorator = code[dec_child.start_byte:dec_child.end_byte].decode(DEFAULT_ENCODING)
                        decorators.append(decorator)
            elif child.type == 'block':
                # Extract methods within the class
                for block_child in child.children:
                    if block_child.type == 'function_definition':
                        # Find method name
                        for method_child in block_child.children:
                            #TODO check if this can be removed due to redundancy
                            if method_child.type == 'identifier':
                                method_name = code[method_child.start_byte:method_child.end_byte].decode(DEFAULT_ENCODING)
                                method_id = self.generate_element_id(
                                    "method", file_path, method_name, block_child.start_point[0] + 1, rootpath
                                )
                                methods.append(method_id)
                                break
        
        if class_name:
            class_id = self.generate_element_id("class", file_path, class_name, start_line, rootpath)
            return Class(
                id=class_id,
                name=class_name,
                element_type="class",
                language=self.language,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                start_col=start_col,
                end_col=end_col,
                content=content,
                base_classes=base_classes,
                methods=methods,
                fields=[],  # Will be populated during dependency resolution
                decorators=decorators
            )
        
        return None
    
    def extract_functions(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Function]:
        """Extract function definitions from Python code."""
        if not self.tree_parser:
            self.init_tree_parser()
            
        # Parse the code with tree-sitter
        tree = self.tree_parser.parse(content.encode(DEFAULT_ENCODING))
        root_node = tree.root_node
        
        functions = []
        self._traverse_for_functions(
            node=root_node,
            code=content.encode(DEFAULT_ENCODING),
            functions=functions,
            file_path=file_path,
            scope="global",
            parent_class=None,
            rootpath=rootpath
        )
        
        return functions
    
    def _traverse_for_functions(self, node: Node, code: bytes, functions: List[Function], 
                               file_path: Path, scope :str, parent_class: Optional[str], rootpath :Optional[Path]=None) -> None:
        """Helper method to traverse the tree for function definitions."""
        if node.type == 'class_definition':
            # Update parent_class for methods within this class
            class_name = None
            for child in node.children:
                if child.type == 'identifier':
                    class_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
                    break
            
            if class_name:
                class_id = self.generate_element_id("class", file_path, class_name, node.start_point[0] + 1, rootpath)
                
                # Process methods within the class block
                for child in node.children:
                    if child.type == 'block':
                        self._traverse_for_functions(child, code, functions, file_path, "class", class_id, rootpath)
        
        elif scope == "class" and node.type == 'function_definition':
            func_details = self._process_function_node(node, code, file_path, "method", parent_class, rootpath)
            if func_details:
                functions.append(func_details)
        elif node.type == 'function_definition':
            func_details = self._process_function_node(node, code, file_path, "function", parent_class, rootpath)
            if func_details:
                functions.append(func_details)
        else:
            # Continue traversing for other nodes
            for child in node.children:
                self._traverse_for_functions(child, code, functions, file_path, scope, parent_class, rootpath)
    
    def _process_function_node(self, node: Node, code: bytes, file_path: Path, 
                              scope :str, parent_class: Optional[str], rootpath :Optional[Path]=None) -> Optional[Function]:
        """Process a function node and convert it to a Function model."""
        ### do not process class methods        
        # Extract function name and parameters
        func_name = None
        parameters = []
        decorators = []
        return_type = None
        
        start_line = node.start_point[0] + 1  # 0-indexed to 1-indexed
        end_line = node.end_point[0] + 1
        start_col = node.start_point[1]
        end_col = node.end_point[1]
        content = code[node.start_byte:node.end_byte].decode(DEFAULT_ENCODING)
        
        for child in node.children:
            if child.type == 'identifier':
                func_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
            elif child.type == 'parameters':
                # Extract parameters
                for param_child in child.children:
                    if param_child.type == 'identifier':
                        param_name = code[param_child.start_byte:param_child.end_byte].decode(DEFAULT_ENCODING)
                        parameters.append(param_name)
            elif child.type == 'decorator':
                # Extract decorators
                for dec_child in child.children:
                    if dec_child.type == 'dotted_name':
                        decorator = code[dec_child.start_byte:dec_child.end_byte].decode(DEFAULT_ENCODING)
                        decorators.append(decorator)
            elif child.type == 'type':
                # Extract return type annotation
                return_type = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
        
        if func_name:
            # Determine if this is a method
            is_method = parent_class is not None
            
            # Check for self parameter if it's a method
            if is_method and parameters and parameters[0] == 'self':
                # It's an instance method
                pass
            scope = "function" if scope != "method" else scope
            func_id = self.generate_element_id(scope, file_path, func_name, start_line, rootpath)
            return Function(
                id=func_id,
                name=func_name,
                element_type="function",
                language=self.language,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                start_col=start_col,
                end_col=end_col,
                content=content,
                is_method=is_method,
                parameters=parameters,
                return_type=return_type,
                decorators=decorators,
                parent_class=parent_class
            )
        
        return None
        
    def extract_variables(self, content: str, file_path: Path, rootpath :Optional[Path]=None) -> List[Variable]:
        """Extract variable declarations from Python code."""
        if not self.tree_parser:
            self.init_tree_parser()
            
        # Parse the code with tree-sitter
        tree = self.tree_parser.parse(content.encode(DEFAULT_ENCODING))
        root_node = tree.root_node
        
        variables = []
        self._traverse_for_variables(
            node=root_node,
            code=content.encode(DEFAULT_ENCODING),
            variables=variables,
            file_path=file_path,
            scope="global",  # Start with global scope
            parent_id=None,
            rootpath=rootpath
        )
        
        return variables

    def _traverse_for_variables(self, node: Node, code: bytes, variables: List[Variable], 
                            file_path: Path, scope: str, parent_id: Optional[str], rootpath :Optional[Path]=None) -> None:
        """Helper method to traverse the tree for variable declarations."""
        # Process this node if it's an assignment and we're in global scope
        if node.type == 'assignment' and scope == "global":
            var_details = self._process_variable_node(node, code, file_path, scope, parent_id, rootpath)
            if var_details:
                variables.append(var_details)
        
        # Continue traversing, but track when we enter and exit classes/functions
        # to maintain proper scope information
        
        if node.type == 'class_definition':
            # When we enter a class, we're no longer in global scope
            class_name = None
            for child in node.children:
                if child.type == 'identifier':
                    class_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
                    break
            
            if class_name:
                class_id = self.generate_element_id("class", file_path, class_name, node.start_point[0] + 1)
                
                # Process children with class scope
                for child in node.children:
                    if child.type == 'block':
                        self._traverse_for_variables(child, code, variables, file_path, "class", class_id, rootpath)
                        
        elif node.type == 'function_definition':
            # When we enter a function, we're no longer in global scope
            func_name = None
            for child in node.children:
                if child.type == 'identifier':
                    func_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
                    break
            
            if func_name:
                func_id = self.generate_element_id("function", file_path, func_name, node.start_point[0] + 1, rootpath)
                
                # Process children with function scope
                for child in node.children:
                    if child.type == 'block':
                        self._traverse_for_variables(child, code, variables, file_path, "function", func_id, rootpath)
        else:
            # For all other node types, continue traversing with the same scope
            for child in node.children:
                self._traverse_for_variables(child, code, variables, file_path, scope, parent_id, rootpath)

    def _process_variable_node(self, node: Node, code: bytes, file_path: Path, 
                            scope: str, parent_id: Optional[str], rootpath :Optional[Path]=None) -> Optional[Variable]:
        """Process a variable assignment node and convert it to a Variable model."""
        # Only process global variable assignments
        if scope != "global":
            return None
            
        var_name = None
        var_type = None
        value = None
        is_constant = False
        
        start_line = node.start_point[0] + 1  # 0-indexed to 1-indexed
        end_line = node.end_point[0] + 1
        start_col = node.start_point[1]
        end_col = node.end_point[1]
        content = code[node.start_byte:node.end_byte].decode(DEFAULT_ENCODING)
        
        # Extract variable name from left side of assignment
        for child in node.children:
            if child.type in ('identifier', 'identifier_pattern'):
                var_name = code[child.start_byte:child.end_byte].decode(DEFAULT_ENCODING)
                # Check if it's a constant (all uppercase)
                is_constant = var_name.isupper()
                break
            elif child.type == 'pattern_list' or child.type == 'expression_list':
                # Handle multiple assignments like x, y = 1, 2
                for subchild in child.children:
                    if subchild.type == 'identifier':
                        var_name = code[subchild.start_byte:subchild.end_byte].decode(DEFAULT_ENCODING)
                        is_constant = var_name.isupper()
                        break
                if var_name:
                    break
        
        # Extract value from right side of assignment
        for i, child in enumerate(node.children):
            if child.type == '=':
                # The value is in the next child
                if i + 1 < len(node.children):
                    value_node = node.children[i + 1]
                    value = code[value_node.start_byte:value_node.end_byte].decode(DEFAULT_ENCODING)
                break
        
        if var_name:
            var_id = self.generate_element_id("variable", file_path, var_name, start_line, rootpath)
            return Variable(
                id=var_id,
                name=var_name,
                element_type="variable",
                language=self.language,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                start_col=start_col,
                end_col=end_col,
                content=content,
                var_type=var_type,
                is_constant=is_constant,
                value=value,
                scope=scope,
                parent_id=parent_id
            )
        
        return None

    def resolve_dependencies(self, codebase: CodeBase) -> None:
        """
        Analyze the codebase to identify and establish dependencies between elements.
        
        This method scans through all code elements to find references to other elements
        and establishes dependency relationships between them.
        
        Args:
            codebase: CodeBase object containing all parsed elements
        """
        # First, build a lookup map of element names for faster dependency resolution
        name_to_id_map = {}
        for element_id, element in tqdm(codebase.elements.root.items()):
            if hasattr(element, 'name'):
                # Simple name-based lookup
                name_to_id_map[element.name] = element_id
                
                # Handle special cases like from-imports
                if getattr(element, 'element_type', None) == 'import' and getattr(element, 'is_from_import', False):
                    module = getattr(element, 'module_name', '')
                    for imported_name in getattr(element, 'imported_names', []):
                        if imported_name != '*':
                            qualified_name = f"{module}.{imported_name}"
                            name_to_id_map[imported_name] = element_id  # Direct name
                            name_to_id_map[qualified_name] = element_id  # Qualified name
        
        # Now process each element to find dependencies
        for element_id, element in tqdm(codebase.elements.root.items()):
            if not hasattr(element, 'element_type'):
                continue
                
            # Process different types of elements
            if element.element_type == 'class':
                # Add inheritance dependencies
                for base_class in getattr(element, 'base_classes', []):
                    if base_class in name_to_id_map:
                        element.add_dependency(DependencyType.INHERITANCE, name_to_id_map[base_class])
                
            elif element.element_type == 'function':
                # Add class reference for methods
                parent_class = getattr(element, 'parent_class', None)
                if parent_class:
                    element.add_dependency(DependencyType.CLASS_REFERENCE, parent_class)
                
                # Analyze function body for references to other functions, variables, etc.
                self._find_references_in_code(element, element.content, name_to_id_map, codebase.root_path)
                
            elif element.element_type == 'variable':
                # If the variable references other elements in its value
                value = getattr(element, 'value', '')
                if value:
                    self._find_references_in_code(element, value, name_to_id_map, codebase.root_path)
    
    def _find_references_in_code(self, element, code: str, name_to_id_map: Dict[str, str], rootpath :Path) -> None:
        """
        Find references to other elements in a block of code.
        
        Args:
            element: The element containing the code
            code: The code to analyze
            name_to_id_map: Mapping of element names to their IDs
        """
        # This is a simplified approach. In a real implementation, you'd use tree-sitter
        # or another parser to accurately identify references
        
        # For each name in our map, check if it appears in the code
        for name, target_id in name_to_id_map.items():
            # Simple pattern matching - would need more sophistication in real use
            # This checks for word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(name) + r'\b'
            if re.search(pattern, code):
                # The type of dependency depends on the target element type
                target_element = element.dependencies.get(target_id)
                if target_element:
                    if target_element.element_type == 'class':
                        element.add_dependency(DependencyType.CLASS_REFERENCE, target_id)
                    elif target_element.element_type == 'function':
                        element.add_dependency(DependencyType.FUNCTION_CALL, target_id)
                    elif target_element.element_type == 'variable':
                        element.add_dependency(DependencyType.VARIABLE_USE, target_id)
                    elif target_element.element_type == 'import_module':
                            element.add_dependency(DependencyType.IMPORT_MODULE, target_id)
                    elif target_element.element_type == 'import_package':
                        element.add_dependency(DependencyType.IMPORT_PACKAGE, target_id)
                    elif target_element.element_type == 'import':
                        element.add_dependency(DependencyType.IMPORT, target_id)