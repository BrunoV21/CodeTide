from .base_parser import BaseParser
from ..core.common import readFile
from ..core.models import (
    ImportStatement, CodeFileModel, ClassDefinition, ClassAttribute,
    VariableDeclaration, FunctionDefinition, MethodDefinition,
    FunctionSignature, Parameter, CodeBase, CodeReference
)

from typing import Optional, Tuple, Union, List, Literal
from concurrent.futures import ThreadPoolExecutor
from tree_sitter import Parser, Language, Node
import tree_sitter_typescript as tsts
from pydantic import model_validator
from pathlib import Path
import asyncio
import re


class TypeScriptParser(BaseParser):
    """
    TypeScript-specific implementation of the BaseParser using tree-sitter.
    """
    _tree_parser: Optional[Parser] = None
    _filepath: Optional[Union[str, Path]] = None

    @property
    def language(self) -> str:
        return "typescript"

    @property
    def extension(self) -> str:
        return ".ts"

    @property
    def filepath(self) -> Optional[Union[str, Path]]:
        return self._filepath

    @filepath.setter
    def filepath(self, filepath: Union[str, Path]):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        self._filepath = filepath

    @staticmethod
    def import_statement_template(importSatement: ImportStatement) -> str:
        statement = f"import {{ {importSatement.name} }} from '{importSatement.source}'"
        if importSatement.source and not importSatement.name:
            statement = f"import '{importSatement.source}'"
        if importSatement.alias:
            statement = f"import {{ {importSatement.name} as {importSatement.alias} }} from '{importSatement.source}'"
        return statement

    @property
    def tree_parser(self) -> Optional[Parser]:
        return self._tree_parser

    @tree_parser.setter
    def tree_parser(self, parser: Parser):
        self._tree_parser = parser

    @model_validator(mode="after")
    def init_tree_parser(self) -> "TypeScriptParser":
        self._tree_parser = Parser(Language(tsts.language_typescript())) ### TODO check difference for typescript and typsecriptX
        return self

    @staticmethod
    def _get_content(code: bytes, node: Node, preserve_indentation: bool = False) -> str:
        if not preserve_indentation:
            return code[node.start_byte:node.end_byte].decode('utf-8')
        line_start = node.start_byte
        while line_start > 0 and code[line_start - 1] not in (10, 13):
            line_start -= 1
        return code[line_start:node.end_byte].decode('utf-8')

    @staticmethod
    def _skip_init_paths(file_path: Path) -> str:
        file_path = str(file_path)
        if "index" in file_path:
            file_path = file_path.replace("\\index.ts", "")
            file_path = file_path.replace("/index.ts", "")
        return file_path

    def parse_code(self, code: bytes, file_path: Path):
        tree = self.tree_parser.parse(code)
        root_node = tree.root_node
        codeFile = CodeFileModel(
            file_path=str(file_path),
            raw=self._get_content(code, root_node)
        )
        self._process_node(root_node, code, codeFile)
        return codeFile

    async def parse_file(self, file_path: Union[str, Path], root_path: Optional[Union[str, Path]] = None) -> CodeFileModel:
        file_path = Path(file_path).absolute()
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            code = await loop.run_in_executor(pool, readFile, file_path, "rb")
            if root_path is not None:
                file_path = file_path.relative_to(Path(root_path))
            codeFile = await loop.run_in_executor(pool, self.parse_code, code, file_path)
        return codeFile

    @classmethod
    def _process_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        for child in node.children:
            if child.type == "import_statement":
                cls._process_import_node(child, code, codeFile)
            elif child.type == "class_declaration":
                cls._process_class_node(child, code, codeFile)
            elif child.type == "function_declaration":
                cls._process_function_definition(child, code, codeFile)
            elif child.type == "lexical_declaration":
                cls._process_variable_declaration(child, code, codeFile)
            elif child.type == "expression_statement":
                cls._process_expression_statement(child, code, codeFile)

    @classmethod
    def _process_import_clause_node(cls, node: Node, code: bytes)->Tuple[Optional[str], Optional[str]]:
        alias = None
        next_is_alias = False
        for child in node.children:
            if child.type == "named_imports":
                for import_child in child.children:
                    if import_child.type == "import_specifier":
                        for alias_child in import_child.children:
                            if alias_child.type == "identifier" and not next_is_alias:
                                name = cls._get_content(code, alias_child)
                            elif alias_child.type == "as":
                                next_is_alias = True
                            elif alias_child.type == "identifier" and next_is_alias:
                                alias = cls._get_content(code, alias_child)
                                next_is_alias = False

                            if name and alias:
                                return name, alias

                        name = cls._get_content(code, import_child)
                        return name, alias
                    
            elif child.type == "identifier":
                name = cls._get_content(code, child)
                return name, alias
            
        return None, None

    @classmethod
    def _process_import_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        source = None
        name = None
        alias = None
        # is_relative = False
        next_is_from_import = False
        next_is_import = False
        for child in node.children:
            if child.type == "import":
                next_is_import = True
            elif child.type == "import_clause" and next_is_import:
                name, alias = cls._process_import_clause_node(child, code)
                next_is_import = False
            elif next_is_import:
                source = cls._get_content(code, child)
                next_is_import = False
            elif child.type == "from":
                next_is_from_import = True
            elif child.type == "string" and next_is_from_import:
                source = cls._get_content(code, child)

        if name and source is None:
            source = name
            name = None

        if source:
            importStatement = ImportStatement(
                source=source,
                name=name,
                alias=alias
            )

            codeFile.add_import(importStatement)
            cls._generate_unique_import_id(codeFile.imports[-1])        

    @classmethod
    def _process_class_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        class_name = None
        bases = []
        raw = cls._get_content(code, node)
        for child in node.children:
            if child.type == "type_identifier" and class_name is None:
                class_name = cls._get_content(code, child)
            elif child.type == "class_heritage":
                for base_child in child.children:
                    if base_child.type == "extends_clause":
                        for expr_child in base_child.children:
                            if expr_child.type == "identifier":
                                bases.append(cls._get_content(code, expr_child))
            elif child.type == "class_body":
                class_def = ClassDefinition(
                    name=class_name,
                    bases=bases,
                    raw=raw
                )
                codeFile.add_class(class_def)
                cls._process_class_body(child, code, codeFile)

    @classmethod
    def _process_class_body(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        for child in node.children:
            if child.type == "method_definition":
                cls._process_function_definition(child, code, codeFile, is_method=True)
            elif child.type == "public_field_definition":
                cls._process_class_attribute(child, code, codeFile)

    @classmethod
    def _process_class_attribute(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        attribute = None
        type_hint = None
        value = None
        modifiers = []
        next_is_assignment = False
        raw = cls._get_content(code, node)
        for child in node.children:
            if child.type == "property_identifier" and attribute is None:
                attribute = cls._get_content(code, child)
            elif child.type == "type_annotation":
                type_hint = cls._get_content(code, child).replace(": ", "")
            elif child.type == "accessibility_modifier":
                modifiers.append(cls._get_content(code, child))
            elif child.type == "=":
                next_is_assignment = True
            elif next_is_assignment:
                value = cls._get_content(code, child)
                next_is_assignment = False
            elif child.type == "assignment_expression":
                for assign_child in child.children:
                    if assign_child.type == "expression":
                        value = cls._get_content(code, assign_child)
        codeFile.classes[-1].add_attribute(ClassAttribute(
            name=attribute,
            type_hint=type_hint,
            modifiers=modifiers,
            value=value,
            raw=raw
        ))

    @classmethod
    def _process_function_definition(cls, node: Node, code: bytes, codeFile: CodeFileModel, is_method :bool=False):
        definition = None
        signature = FunctionSignature()
        modifiers = []
        decorators = []
        raw = cls._get_content(code, node)
        for child in node.children:
            if child.type == "identifier" and definition is None:
                definition = cls._get_content(code, child)
            elif child.type == "property_identifier" and definition is None:
                definition = cls._get_content(code, child)
            elif child.type == "formal_parameters":
                signature.parameters = cls._process_parameters(child, code)
            elif child.type == "type_annotation":
                signature.return_type = cls._get_content(code, child).replace(": ", "")
            elif child.type == "async":
                modifiers.append("async")
            elif child.type == "decorator":
                decorators.append(cls._get_content(code, child))
            elif child.type == "public":
                modifiers.append("public")
            elif child.type == "private":
                modifiers.append("private")
            elif child.type == "protected":
                modifiers.append("protected")
            elif child.type == "static":
                modifiers.append("static")
            elif child.type == "async":
                modifiers.append("async")
        if not is_method: 
            codeFile.add_function(FunctionDefinition(
                name=definition,
                signature=signature,
                decorators=decorators,
                modifiers=modifiers,
                raw=raw
            ))
        else:
            codeFile.classes[-1].add_method(MethodDefinition(
                name=definition,
                signature=signature,
                decorators=decorators,
                modifiers=modifiers,
                raw=raw
            ))


    @classmethod
    def _process_variable_declaration(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        for child in node.children:
            if child.type == "variable_declarator":
                cls._process_variable_declarator(child, code, codeFile)

    @classmethod
    def _process_variable_declarator(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        name = None
        type_hint = None
        value = None
        next_is_value = False
        raw = cls._get_content(code, node)
        for child in node.children:
            if child.type == "identifier" and name is None:
                name = cls._get_content(code, child)
            elif child.type == "type_annotation":
                type_hint = cls._get_content(code, child)
            elif child.type == "=":
                next_is_value = True
            elif next_is_value:
                value = cls._get_content(code, child)
                next_is_value = False
        codeFile.add_variable(VariableDeclaration(
            name=name,
            type_hint=type_hint,
            value=value,
            raw=raw
        ))

    @classmethod
    def _process_expression_statement(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        # TypeScript expression statements can be variable assignments, function calls, etc.
        # For now, we do not extract anything here.
        pass

    @classmethod
    def _process_parameters(cls, node: Node, code: bytes) -> List[Parameter]:
        parameters = []
        for child in node.children:
            if child.type == "required_parameter" or child.type == "optional_parameter":
                param = cls._process_type_parameter(child, code)
                if param is not None:
                    parameters.append(param)
        return parameters

    @classmethod
    def _process_type_parameter(cls, node: Node, code: bytes) -> Parameter:
        parameter = None
        type_hint = None
        default = None        
        next_is_assignment = False
        for child in node.children:
            if child.type == "identifier" and parameter is None:
                parameter = cls._get_content(code, child)
            elif child.type == "type_annotation":
                next_is_type = False
                for type_child in child.children:
                    if type_child.type == ":":
                        next_is_type = True
                    elif next_is_type:
                        type_hint = cls._get_content(code, type_child)
                        next_is_type = False
            elif child.type == "=":
                next_is_assignment = True
            elif next_is_assignment:
                default = cls._get_content(code, child)
                next_is_assignment = False
            elif child.type == "assignment_expression":
                for assign_child in child.children:
                    if assign_child.type == "expression":
                        default = cls._get_content(code, assign_child)
        if parameter:
            return Parameter(
                name=parameter,
                type_hint=type_hint,
                default_value=default
            )

    @classmethod
    def _default_unique_import_id(cls, importModel: ImportStatement) -> str:
        if importModel.source and importModel.name:
            unique_id = f"{importModel.source}.{importModel.name}"
        else:
            unique_id = f"{importModel.source or importModel.name}"
        unique_id = cls._skip_init_paths(unique_id)
        return unique_id

    @classmethod
    def _generate_unique_import_id(cls, importModel: ImportStatement):
        unique_id = cls._default_unique_import_id(importModel)
        if "index" in importModel.file_path:
            importModel.definition_id = unique_id
            importModel.unique_id = ".".join([
                entry for entry in unique_id.split(".")
                if entry in importModel.file_path or entry in [importModel.name, importModel.source]
            ])
        else:
            importModel.unique_id = unique_id
            importModel.definition_id = unique_id
        importModel.raw = cls.import_statement_template(importModel)

    @classmethod
    def resolve_inter_files_dependencies(cls, codeBase: CodeBase, codeFiles: Optional[List[CodeFileModel]] = None) -> None:
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
        element_type: Literal["variables", "functions", "classes"],
        non_import_ids: List[str],
        raw_contents: List[str],
        codeFile: CodeFileModel):
        for element in getattr(codeFile, element_type):
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
    def _get_element_count(cls, raw_contents: List[str], element):
        elementCounts = cls.count_occurences_in_code("\n".join(raw_contents), element.name)
        elementCounts -= 1
        return elementCounts

    @staticmethod
    def _find_references(
        non_import_ids: List[str],
        raw_contents: List[str],
        matches_count: int,
        codeFile: CodeFileModel,
        unique_id: str,
        reference_name: str):
        matches_found = 0
        for _id, raw_content in zip(non_import_ids, raw_contents):
            if reference_name in raw_content:
                codeElement = codeFile.get(_id)
                counts = 1
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
