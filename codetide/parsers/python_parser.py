from .base_parser import BaseParser
from ..core.common import readFile
from ..core.models import (
    ClassAttribute, ClassDefinition, CodeBase, CodeReference,
    FunctionDefinition, FunctionSignature, ImportStatement,
    CodeFileModel, MethodDefinition, Parameter, VariableDeclaration
)

from typing import List, Literal, Optional, Union
from concurrent.futures import ThreadPoolExecutor
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython
from pydantic import model_validator
from pathlib import Path
import asyncio
import re
import os
class PythonParser(BaseParser):
    """
    Python-specific implementation of the BaseParser using tree-sitter.
    """
    _tree_parser: Optional[Parser] = None
    _filepath: Optional[Union[str, Path]] = None

    @property
    def language(self) -> str:
        return "python"
    
    @property
    def extension(self) -> str:
        return ".py"
    
    @property
    def filepath (self) -> Optional[Union[str, Path]]:
        return self._filepath
    
    @filepath.setter
    def filepath(self, filepath: Union[str, Path]):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        self._filepath = filepath

    @staticmethod
    def import_statement_template(importSatement :ImportStatement)->str:
        statement = f"import {importSatement.source or importSatement.name}"
        if importSatement.source and importSatement.name:
            statement = f"from {importSatement.source} import {importSatement.name}"
        elif importSatement.source:
            statement = f"import {importSatement.source}"

        if importSatement.alias:
            statement = f"{statement} as {importSatement.alias}"

        return statement
    
    @property
    def tree_parser(self) -> Optional[Parser]:
        return self._tree_parser
    
    @tree_parser.setter
    def tree_parser(self, parser: Parser):
        self._tree_parser = parser
    
    @model_validator(mode="after")
    def init_tree_parser(self) -> "PythonParser":
        """Initialize the tree-sitter parser."""
        self._tree_parser = Parser(Language(tspython.language()))
        return self
    
    @staticmethod
    def _get_content(code: bytes, node: Node, preserve_indentation: bool = False) -> str:
        if not preserve_indentation:
            return code[node.start_byte:node.end_byte].decode('utf-8')

        if preserve_indentation:
            # Go back to the start of the line to include indentation
            line_start = node.start_byte
            while line_start > 0 and code[line_start - 1] not in (10, 13):
                line_start -= 1

        return code[line_start:node.end_byte].decode('utf-8')

    
    @staticmethod
    def _skip_init_paths(file_path :Path)->str:
        file_path = str(file_path)
        if "__init__" in file_path:
            file_path = file_path.replace("\\__init__.py", "")
            file_path = file_path.replace("/__init__.py", "")
        return file_path
    
    def parse_code(self, code :bytes, file_path :Path):
        tree = self.tree_parser.parse(code)
        root_node = tree.root_node
        codeFile = CodeFileModel(
            file_path=str(file_path), #self._skip_init_paths(file_path),
            raw=self._get_content(code, root_node, preserve_indentation=True)
        )
        self._process_node(root_node, code, codeFile)
        return codeFile

    async def parse_file(self, file_path: Union[str, Path], root_path: Optional[Union[str, Path]]=None) -> CodeFileModel:
        """
        Parse a Python source file and return a CodeFileModel.
        """
        file_path = Path(file_path).absolute()
        
        # Use aiofiles or run synchronous file IO in executor
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            code = await loop.run_in_executor(pool, readFile, file_path, "rb")
            
            if root_path is not None:
                file_path = file_path.relative_to(Path(root_path))

            codeFile = await loop.run_in_executor(pool, self.parse_code, code, file_path)

        return codeFile
    
    @classmethod
    def _process_node(cls, node: Node, code: bytes, codeFile :CodeFileModel):    
        for child in node.children:
            if child.type.startswith("import"):
                cls._process_import_node(child, code, codeFile)
            elif child.type == "class_definition":
                cls._process_class_node(child, code, codeFile)
            elif child.type == "decorated_definition":
                cls._process_decorated_definition(child, code, codeFile)
            elif child.type == "function_definition":
                cls._process_function_definition(child, code, codeFile)
            elif child.type == "expression_statement":
                cls._process_expression_statement(child, code, codeFile)
            # elif child.type == "assignment": # <- class attribute
            #     cls._process_assignment(child, code, codeFile)

    @staticmethod
    def _rebuild_source_from_relative(relative_import_source :str, relative_import_name :str, filepath :str)->str:
            relative_location_index = relative_import_source.count(".")
            source_location = Path(filepath).parent
            for _ in range(1, relative_location_index):
                source_location = Path(source_location).parent
            source_id = str(source_location).replace(os.path.sep, ".")
            return f"{source_id}.{relative_import_name}"

    @classmethod
    def _process_relative_import_node(cls, node: Node, code: bytes, codeFile :CodeFileModel):
        source = None
        relative_import_source = None
        relative_import_name = None
        for child in node.children:
            if child.type == "import_prefix":
                relative_import_source = cls._get_content(code, child)
            elif child.type == "dotted_name":
                relative_import_name = cls._get_content(code, child)
        if relative_import_source and relative_import_name:
            source = cls._rebuild_source_from_relative(
                relative_import_source=relative_import_source,
                relative_import_name=relative_import_name,
                filepath=codeFile.file_path
            )
        return source

    @classmethod
    def _process_import_node(cls, node: Node, code: bytes, codeFile :CodeFileModel):
        source = None
        next_is_from_import = False
        next_is_import = False
        is_relative = False
        for child in node.children:
            if child.type == "from":
                next_is_from_import = True
            elif child.type == "relative_import":
                source = cls._process_relative_import_node(child, code, codeFile)
                is_relative = True
            elif child.type == "dotted_name" and next_is_from_import and not is_relative:
                next_is_from_import = False
                source = cls._get_content(code, child)
            elif child.type == "import":
                next_is_import = True
            elif child.type == "aliased_import":
                cls._process_aliased_import(child, code, codeFile, source)
            elif child.type == "dotted_name" and next_is_import:
                name = cls._get_content(code, child)
                if source is None:
                    source = name
                    name = None

                if source is not None:
                    importStatement = ImportStatement(
                            source=source,
                            name=name
                        )
                    if is_relative:
                        importStatement.import_type = "relative"
                    codeFile.add_import(importStatement)
                    cls._generate_unique_import_id(codeFile.imports[-1])

    @classmethod
    def _process_aliased_import(cls, node: Node, code: bytes, codeFile :CodeFileModel, source :str):
        name = None
        for child in node.children:
            if child.type == "dotted_name":
                name = cls._get_content(code, child)
            elif child.type == "identifier":
                alias = cls._get_content(code, child)

                importStatement = ImportStatement(
                        source=source,
                        name=name,
                        alias=alias
                    )
                codeFile.add_import(importStatement)
                cls._generate_unique_import_id(codeFile.imports[-1])

    @classmethod
    def _process_class_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        """Process a class definition node and add it to the code file model."""
        is_class = False
        class_name = None
        bases = []
        raw = cls._get_content(code, node, preserve_indentation=True)
        for child in node.children: 
            if child.type == "class":
                is_class = True
            elif is_class and child.type == "identifier":
                class_name = cls._get_content(code, child)
            elif class_name and child.type == "arguments_list":
                bases.append(cls._get_content(code, child).replace("(", "").replace(")", ""))
            elif child.type == "block":
                codeFile.add_class(
                    ClassDefinition(
                        name=class_name,
                        bases=bases,
                        raw=raw
                    )
                )
                cls._process_block(node, code, codeFile)

    @classmethod
    def _process_block(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        """Process a block of code and extract methods, attributes, and variables."""
        for child in node.children:
            for block_child in child.children:
                if block_child.type == "identifier":
                    base = cls._get_content(code, block_child)
                    codeFile.classes[-1].bases.append(base)
                elif block_child.type == "expression_statement":
                    cls._process_expression_statement(block_child, code, codeFile, is_class_attribute=True)
                elif block_child.type == "decorated_definition":
                    """process decorated definiion"""
                    cls._process_decorated_definition(block_child, code, codeFile, is_class_method=True)
                elif block_child.type == "function_definition":
                    """process_function_definition into class method"""
                    cls._process_function_definition(block_child, code, codeFile, is_class_method=True)

    @classmethod
    def _process_expression_statement(cls, node: Node, code: bytes, codeFile: CodeFileModel, is_class_attribute :bool=False):
        """Process an expression statement and extract variables."""
        for child in node.children:
            if child.type == "assignment": # <- class attribute
                cls._process_assignment(child, code, codeFile, is_class_attribute)
            elif child.type == "string": # <- docstring
                ...

    @classmethod
    def _process_assignment(cls, node: Node, code: bytes, codeFile: CodeFileModel, is_class_attribute :bool=False):
        """Process an assignment expression and extract variable names and values."""
        attribute = None
        type_hint = None
        default = None
        next_is_default = None
        for child in node.children:
            if child.type == "identifier" and attribute is None:
                attribute = cls._get_content(code, child)
            elif child.type == "type":
                type_hint = cls._get_content(code, child)
            elif child.type == "=" and next_is_default is None:
                next_is_default = True
            elif default is None and next_is_default:
                default =  cls._get_content(code, child)
                next_is_default = None
        
        if is_class_attribute:
            raw = cls._get_content(code, node, preserve_indentation=True)
            codeFile.classes[-1].add_attribute(
                ClassAttribute(
                    name=attribute,
                    type_hint=type_hint,
                    value=default,
                    raw=raw
                )
            )
        else:
            raw = cls._get_content(code, node)
            codeFile.add_variable(
                VariableDeclaration(
                    name=attribute,
                    type_hint=type_hint,
                    value=default,
                    raw=raw
                )
            )

    @classmethod
    def _process_decorated_definition(cls, node: Node, code: bytes, codeFile: CodeFileModel, is_class_method :bool=False):
        decorators = []
        raw = cls._get_content(code, node, preserve_indentation=True)
        # print(f"{raw=}")

        for child in node.children:
            if child.type == "decorator":
                decorators.append(cls._get_content(code, child))
            elif child.type == "function_definition":
                cls._process_function_definition(child, code, codeFile, is_class_method=is_class_method, decorators=decorators, raw=raw)

    @classmethod
    def _process_function_definition(cls, node: Node, code: bytes, codeFile: CodeFileModel, is_class_method :bool=False, decorators :Optional[List[str]]=None, raw :Optional[str]=None):
        # print(node.type, cls._get_content(code, node))
        definition = None
        signature = FunctionSignature()
        modifiers = []
        

        if decorators is None:
            decorators = []

        ### TODO add logic to extract modifiers i.e. async
        for child in node.children:
            if child.type == "identifier":
                definition = cls._get_content(code, child)
            elif child.type == "async":
                modifiers.append(cls._get_content(code, child))
            elif child.type == "parameters":
                ### process parameters
                signature.parameters = cls._process_parameters(child, code)
            elif child.type == "type":
                signature.return_type = cls._get_content(code, child)
        
        if is_class_method:
            if raw is None:
                raw = cls._get_content(code, node, preserve_indentation=True)
            
            codeFile.classes[-1].add_method(MethodDefinition(
                    name=definition,
                    signature=signature,
                    decorators=decorators,
                    modifiers=modifiers,
                    raw=raw
                )
            )
            currentMethod = codeFile.classes[-1].methods[-1]
            if currentMethod.unique_id in codeFile.classes[-1].all_methods_ids[:-1] and currentMethod.decorators:
                currentMethod.unique_id = f"{currentMethod.unique_id}{''.join(currentMethod.decorators)}"

        else:
            if raw is None:
                raw = cls._get_content(code, node)
            codeFile.add_function(
                FunctionDefinition(
                    name=definition,
                    signature=signature,
                    decorators=decorators,
                    modifiers=modifiers,
                    raw=raw
                )
            )

    @classmethod
    def _process_parameters(cls, node: Node, code: bytes)->List[Parameter]:
        parameters = []
        for child in node.children:
            if child.type in ["typed_parameter", "typed_default_parameter"]:
                param = cls._process_type_parameter(child, code)
                if param is not None:
                    parameters.append(param)
        return parameters

    @classmethod
    def _process_type_parameter(cls, node: Node, code :bytes)->Parameter:
        next_is_default = False
        parameter = None
        type_hint = None
        default = None
        for child in node.children:
            if child.type == "identifier" and parameter is None:
                parameter = cls._get_content(code, child)
            elif child.type == "type":
                type_hint = cls._get_content(code, child) 
            elif child.type == "=":
                next_is_default = True
            elif next_is_default:
                default = cls._get_content(code, child)
        
        if parameter:
            return Parameter(
                name=parameter,
                type_hint=type_hint,
                default_value=default
            )
    
    @classmethod
    def _default_unique_import_id(cls, importModel :ImportStatement)->str:
        if importModel.source and importModel.name:
            unique_id = f"{importModel.source}.{importModel.name}"
        else:
            unique_id = f"{importModel.source or importModel.name}"
        unique_id = cls._skip_init_paths(unique_id)
        return unique_id

    @classmethod
    def _generate_unique_import_id(cls, importModel :ImportStatement):
        """Generate a unique ID for the function definition"""
        unique_id = cls._default_unique_import_id(importModel)

        if "__init__" in importModel.file_path:
            # if Path(importModel.file_path).with_suffix("") == Path(importModel.file_path):
            ### it is an init file need to map prefill definiton_id which will be usde for mapping
            importModel.definition_id = unique_id
            importModel.unique_id = ".".join([
                entry for entry in unique_id.split(".")
                if entry in importModel.file_path or entry in [importModel.name, importModel.source]
            ])

        else:
            
            # print(f"\n{unique_id=}->>>>>>>>>>>>>>>>>")
            importModel.unique_id = unique_id
            importModel.definition_id = unique_id
            
        importModel.raw = cls.import_statement_template(importModel)
    
    @classmethod
    def resolve_inter_files_dependencies(cls, codeBase: CodeBase, codeFiles :Optional[List[CodeFileModel]]=None) -> None:
        ### for codeFile in codeBase search through imports and if defition_id matches an id from a class, a function or a variable  let it be
        ### otherwise check if it matches a unique_id from imports, if so map dfeiniton_id to import unique id 
        ### othewise map to None and is a package
        ### this should handle all imports across file
        if codeFiles is None:
            codeFiles = codeBase.root
        
        all_imports = codeBase.all_imports()
        all_elements = codeBase.all_classes() + codeBase.all_functions() + codeBase.all_variables()
        for codeFile in codeFiles:
            global_imports_minus_current = [
                importId for importId in all_imports
                if importId not in codeFile.all_imports()
            ]
            for importStatement in codeFile.imports:
                definitionId = importStatement.definition_id
                if definitionId not in all_elements:
                    if definitionId in global_imports_minus_current:
                        matchingImport = codeBase.get_import(definitionId)
                        importStatement.definition_id = matchingImport.definition_id
                        continue

                    importStatement.definition_id = None
                    importStatement.unique_id = cls._default_unique_import_id(importStatement)

    @staticmethod
    def count_occurences_in_code(code: str, substring: str) -> int:
        # Pattern explanation:
        # (?<![a-zA-Z0-9_]) - negative lookbehind: not preceded by any word character
        # (?![a-zA-Z0-9_])  - negative lookahead: not followed by any word character
        # This ensures we only match at true word boundaries
        
        pattern = r"(?<![a-zA-Z0-9_])" + re.escape(substring) + r"(?![a-zA-Z0-9_])"
        
        matches = re.findall(pattern, code)
        return len(matches)

    def resolve_intra_file_dependencies(self, codeFiles: List[CodeFileModel]) -> None:
        for codeFile in codeFiles:
            if not codeFile.file_path.endswith(self.extension):
                continue
            
            non_import_ids = codeFile.all_classes() + codeFile.all_functions() + codeFile.all_variables()
            raw_contents = codeFile.list_raw_contents
            raw_contents_str = "\n".join(raw_contents)

            ### find importStatement
            for importStatement in codeFile.imports:
                importAsDependency = importStatement.as_dependency
                importCounts = self.count_occurences_in_code(raw_contents_str, importAsDependency)
                if not importCounts:
                    continue
                
                self._find_references(
                    non_import_ids=non_import_ids,
                    raw_contents=raw_contents,
                    matches_count=importCounts,
                    codeFile=codeFile,
                    unique_id=importStatement.unique_id,
                    reference_name=importAsDependency
                )
            
            for elemen_type in ["variables", "functions", "classes"]:
                self._find_elements_references(
                    element_type=elemen_type,
                    non_import_ids=non_import_ids,
                    raw_contents=raw_contents,
                    codeFile=codeFile
                )

    @classmethod
    def _find_elements_references(cls,
        element_type :Literal["variables", "functions", "classes"],
        non_import_ids :List[str],
        raw_contents :List[str],
        codeFile :CodeFileModel):
        for element in getattr(codeFile, element_type):
            ### broken for class defintion as we need to search through methods and attributes
            if element_type == "classes":
                for classAttribute in element.attributes:
                    elementCounts = cls._get_element_count(raw_contents, classAttribute)

                    if elementCounts <= 0:
                        continue

                    cls._find_references(
                        non_import_ids=non_import_ids,
                        raw_contents=raw_contents,
                        matches_count=elementCounts,
                        codeFile=codeFile,
                        unique_id=classAttribute.unique_id,
                        reference_name=classAttribute.name
                    )

                for classMethod in element.methods:
                    # print(f"{classMethod.name=}")
                    elementCounts = cls._get_element_count(raw_contents, classMethod)

                    if elementCounts <= 0:
                        continue

                    cls._find_references(
                        non_import_ids=non_import_ids,
                        raw_contents=raw_contents,
                        matches_count=elementCounts,
                        codeFile=codeFile,
                        unique_id=classMethod.unique_id,
                        reference_name=classMethod.name
                    )
            
            else:
                elementCounts = cls._get_element_count(raw_contents, element)

                if elementCounts <= 0:
                    continue
                
                cls._find_references(
                    non_import_ids=non_import_ids,
                    raw_contents=raw_contents,
                    matches_count=elementCounts,
                    codeFile=codeFile,
                    unique_id=element.unique_id,
                    reference_name=element.name
                )

    @classmethod
    def _get_element_count(cls, raw_contents :List[str], element):
        elementCounts = cls.count_occurences_in_code("\n".join(raw_contents), element.name)
        elementCounts -= 1
        return elementCounts

    @staticmethod
    def _find_references(
        non_import_ids :List[str],
        raw_contents :List[str],
        matches_count :int,
        codeFile :CodeFileModel,
        unique_id :str,
        reference_name :str):
        
        matches_found = 0
        for _id, raw_content in zip(non_import_ids, raw_contents):
            if reference_name in raw_content:
                codeElement = codeFile.get(_id)
                ### TODO check why getting counts occurence in codeElement.raw is resulting in misfilling
                counts = 1 #self.count_occurences_in_code(codeElement.raw, reference_name)
                if isinstance(codeElement, (VariableDeclaration, FunctionDefinition)):
                    codeElement.references.append(
                        CodeReference(
                            unique_id=unique_id,
                            name=reference_name
                        )
                    )
                    matches_found += counts

                elif isinstance(codeElement, (ClassDefinition)):
                    for method in codeElement.methods:
                        if reference_name in method.raw:
                            method.references.append(
                                CodeReference(
                                    unique_id=unique_id,
                                    name=reference_name
                                )
                            )
                            matches_found += counts
                            if matches_found >= matches_count:
                                break
                    
                    for attribute in codeElement.attributes:
                        if reference_name in attribute.raw:
                            attribute.references.append(
                                CodeReference(
                                    unique_id=unique_id,
                                    name=reference_name
                                )
                            )
                            matches_found += counts
                            if matches_found >= matches_count:
                                break

                    if reference_name in codeElement.bases:
                        codeElement.bases_references.append(
                            CodeReference(
                                unique_id=unique_id,
                                name=reference_name
                            )
                        )
                
                if matches_found > matches_count:
                    break