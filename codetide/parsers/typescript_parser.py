from codetide.core.models import (
    ImportStatement, CodeFileModel, ClassDefinition, ClassAttribute, VariableDeclaration,
    FunctionDefinition, FunctionSignature, MethodDefinition, Parameter, CodeBase, CodeReference
)
from codetide.parsers.base_parser import BaseParser

from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Union, List, Literal
from tree_sitter import Parser, Language, Node
import tree_sitter_typescript as tstypescript
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
        if importSatement.alias:
            return f"import {{ {importSatement.name} as {importSatement.alias} }} from '{importSatement.source}'"
        elif importSatement.name:
            return f"import {{ {importSatement.name} }} from '{importSatement.source}'"
        else:
            return f"import '{importSatement.source}'"

    @property
    def tree_parser(self) -> Optional[Parser]:
        return self._tree_parser
    
    @tree_parser.setter
    def tree_parser(self, parser: Parser):
        self._tree_parser = parser

    @model_validator(mode="after")
    def init_tree_parser(self) -> "TypeScriptParser":
        # You must have a tree-sitter-typescript language binding available as 'tstypescript'
        self._tree_parser = Parser(Language(tstypescript.language()))
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
        if "index.ts" in file_path:
            file_path = file_path.replace("\\index.ts", "")
            file_path = file_path.replace("/index.ts", "")
        return file_path

    def parse_code(self, code: bytes, file_path: Path):
        tree = self.tree_parser.parse(code)
        root_node = tree.root_node
        codeFile = CodeFileModel(
            file_path=str(file_path),
            raw=self._get_content(code, root_node, preserve_indentation=True)
        )
        self._process_node(root_node, code, codeFile)
        return codeFile

    async def parse_file(self, file_path: Union[str, Path], root_path: Optional[Union[str, Path]] = None) -> CodeFileModel:
        file_path = Path(file_path).absolute()
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            from codetide.core.common import readFile
            code = await loop.run_in_executor(pool, readFile, file_path, "rb")
            if root_path is not None:
                file_path = file_path.relative_to(Path(root_path))
            codeFile = await loop.run_in_executor(pool, self.parse_code, code, file_path)
        return codeFile

    @classmethod
    def _process_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        for child in node.children:
            if child.type.startswith("import"):
                cls._process_import_node(child, code, codeFile)
            elif child.type == "class_declaration":
                cls._process_class_node(child, code, codeFile)
            elif child.type == "function_declaration":
                cls._process_function_definition(child, code, codeFile)
            elif child.type == "lexical_declaration":
                cls._process_variable_statement(child, code, codeFile)
            # Add more TypeScript-specific node types as needed

    @classmethod
    def _process_import_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        # TypeScript import parsing logic
        # Handles: import { X } from 'Y'; import X from 'Y'; import * as X from 'Y'; import 'Y';
        source = None
        name = None
        alias = None
        for child in node.children:
            if child.type == "string":
                source = cls._get_content(code, child).strip("'\"")
            elif child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "named_imports":
                        # import { X, Y as Z } from 'Y';
                        for named in clause_child.children:
                            if named.type == "import_specifier":
                                spec_name = None
                                spec_alias = None
                                for spec_child in named.children:
                                    if spec_child.type == "identifier":
                                        if spec_name is None:
                                            spec_name = cls._get_content(code, spec_child)
                                        else:
                                            spec_alias = cls._get_content(code, spec_child)
                                importStatement = ImportStatement(
                                    source=source,
                                    name=spec_name,
                                    alias=spec_alias
                                )
                                codeFile.add_import(importStatement)
                    elif clause_child.type == "identifier":
                        # import X from 'Y';
                        name = cls._get_content(code, clause_child)
                        importStatement = ImportStatement(
                            source=source,
                            name=name
                        )
                        codeFile.add_import(importStatement)
                    elif clause_child.type == "namespace_import":
                        # import * as X from 'Y';
                        for ns_child in clause_child.children:
                            if ns_child.type == "identifier":
                                alias = cls._get_content(code, ns_child)
                        importStatement = ImportStatement(
                            source=source,
                            name="*",
                            alias=alias
                        )
                        codeFile.add_import(importStatement)
            elif child.type == "string":
                source = cls._get_content(code, child).strip("'\"")
                importStatement = ImportStatement(
                    source=source
                )
                codeFile.add_import(importStatement)

    @classmethod
    def _process_class_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        class_name = None
        bases = []
        raw = cls._get_content(code, node, preserve_indentation=True)
        for child in node.children:
            if child.type == "identifier" and class_name is None:
                class_name = cls._get_content(code, child)
            elif child.type == "heritage_clause":
                for base_child in child.children:
                    if base_child.type == "expression_with_type_arguments":
                        base_name = None
                        for expr_child in base_child.children:
                            if expr_child.type == "identifier":
                                base_name = cls._get_content(code, expr_child)
                        if base_name:
                            bases.append(base_name)
            elif child.type == "class_body":
                codeFile.add_class(
                    ClassDefinition(
                        name=class_name,
                        bases=bases,
                        raw=raw
                    )
                )
                cls._process_block(child, code, codeFile)

    @classmethod
    def _process_block(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        for child in node.children:
            if child.type == "method_definition":
                cls._process_method_definition(child, code, codeFile)
            elif child.type == "public_field_definition":
                cls._process_class_attribute(child, code, codeFile)

    @classmethod
    def _process_method_definition(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        method_name = None
        signature = FunctionSignature()
        modifiers = []
        decorators = []
        raw = cls._get_content(code, node, preserve_indentation=True)
        for child in node.children:
            if child.type == "identifier" and method_name is None:
                method_name = cls._get_content(code, child)
            elif child.type == "formal_parameters":
                signature.parameters = cls._process_parameters(child, code)
            elif child.type == "type_annotation":
                signature.return_type = cls._get_content(code, child)
            elif child.type == "decorator":
                decorators.append(cls._get_content(code, child))
            elif child.type in ["public", "private", "protected", "static", "async"]:
                modifiers.append(cls._get_content(code, child))
        codeFile.classes[-1].add_method(MethodDefinition(
            name=method_name,
            signature=signature,
            decorators=decorators,
            modifiers=modifiers,
            raw=raw
        ))

    @classmethod
    def _process_class_attribute(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        attribute = None
        type_hint = None
        default = None
        visibility = "public"
        raw = cls._get_content(code, node, preserve_indentation=True)
        for child in node.children:
            if child.type == "identifier" and attribute is None:
                attribute = cls._get_content(code, child)
            elif child.type == "type_annotation":
                type_hint = cls._get_content(code, child)
            elif child.type == "public":
                visibility = "public"
            elif child.type == "private":
                visibility = "private"
            elif child.type == "protected":
                visibility = "protected"
            elif child.type == "initializer":
                default = cls._get_content(code, child)
        codeFile.classes[-1].add_attribute(ClassAttribute(
            name=attribute,
            type_hint=type_hint,
            value=default,
            visibility=visibility,
            raw=raw
        ))

    @classmethod
    def _process_variable_statement(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        for child in node.children:
            if child.type == "variable_declaration":
                cls._process_variable_declaration(child, code, codeFile)

    @classmethod
    def _process_variable_declaration(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        name = None
        type_hint = None
        value = None
        modifiers = []
        raw = cls._get_content(code, node, preserve_indentation=True)
        for child in node.children:
            if child.type == "identifier" and name is None:
                name = cls._get_content(code, child)
            elif child.type == "type_annotation":
                type_hint = cls._get_content(code, child)
            elif child.type == "initializer":
                value = cls._get_content(code, child)
        codeFile.add_variable(VariableDeclaration(
            name=name,
            type_hint=type_hint,
            value=value,
            modifiers=modifiers,
            raw=raw
        ))

    @classmethod
    def _process_function_definition(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        definition = None
        signature = FunctionSignature()
        modifiers = []
        decorators = []
        raw = cls._get_content(code, node, preserve_indentation=True)
        for child in node.children:
            if child.type == "identifier" and definition is None:
                definition = cls._get_content(code, child)
            elif child.type == "formal_parameters":
                signature.parameters = cls._process_parameters(child, code)
            elif child.type == "type_annotation":
                signature.return_type = cls._get_content(code, child)
            elif child.type == "decorator":
                decorators.append(cls._get_content(code, child))
            elif child.type in ["async"]:
                modifiers.append(cls._get_content(code, child))
        codeFile.add_function(FunctionDefinition(
            name=definition,
            signature=signature,
            decorators=decorators,
            modifiers=modifiers,
            raw=raw
        ))

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
        for child in node.children:
            if child.type == "identifier" and parameter is None:
                parameter = cls._get_content(code, child)
            elif child.type == "type_annotation":
                type_hint = cls._get_content(code, child)
            elif child.type == "initializer":
                default = cls._get_content(code, child)
        if parameter:
            return Parameter(
                name=parameter,
                type_hint=type_hint,
                default_value=default
            )

    @classmethod
    def _default_unique_import_id(cls, importModel: ImportStatement) -> str:
        if importModel.name:
            unique_id = f"{importModel.source}.{importModel.name}"
        else:
            unique_id = f"{importModel.source}"
        unique_id = cls._skip_init_paths(unique_id)
        return unique_id

    @classmethod
    def _generate_unique_import_id(cls, importModel: ImportStatement):
        unique_id = cls._default_unique_import_id(importModel)
        if "index.ts" in importModel.file_path:
            importModel.definition_id = unique_id
            importModel.unique_id = ".".join([
                entry for entry in unique_id.split(".")
                if entry in importModel.file_path or entry in [importModel.name, importModel.source]
            ])
        else:
            importModel.unique_id = unique_id
            importModel.definition_id = unique_id
        importModel.raw = cls.import_statement_template(importModel)

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
                if matches_found >= matches_count:
                    break

    def resolve_inter_files_dependencies(self, codeBase: CodeBase, codeFiles: Optional[List[CodeFileModel]] = None) -> None:
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
                    importStatement.unique_id = self._default_unique_import_id(importStatement)
