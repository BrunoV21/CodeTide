from codetide.parsers.base_parser import BaseParser
from codetide.core.common import readFile
from codetide.core.models import (
    ClassAttribute, ClassDefinition, CodeBase,
    FunctionDefinition, FunctionSignature, ImportStatement,
    CodeFileModel, MethodDefinition, Parameter, VariableDeclaration
)

from concurrent.futures import ThreadPoolExecutor
from tree_sitter import Language, Parser, Node
from typing import List, Optional, Union
import tree_sitter_python as tspython
from pydantic import model_validator
from pathlib import Path
import asyncio

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
    def filepath (self) -> Optional[Union[str, Path]]:
        return self._filepath
    
    @filepath.setter
    def filepath(self, filepath: Union[str, Path]):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        self._filepath = filepath
    
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
    def _get_content(code :bytes, node: Node)->str:
        return code[node.start_byte:node.end_byte].decode('utf-8')
    
    @staticmethod
    def _skip_init_paths(file_path :Path)->str:
        file_path = str(file_path)
        if "__init__" in file_path:
            file_path = file_path.replace("\\__init__", "")
            file_path = file_path.replace("/__init__", "")
        return file_path
    
    def parse_code(self, code :bytes, file_path :Path):
        tree = self.tree_parser.parse(code)
        root_node = tree.root_node
        codeFile = CodeFileModel(
            file_path=self._skip_init_paths(file_path),
            raw=self._get_content(code, root_node)
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

    @classmethod
    def _process_import_node(cls, node: Node, code: bytes, codeFile :CodeFileModel):
        source = None
        next_is_from_import = False
        next_is_import = False
        for child in node.children:
            if child.type == "from":
                next_is_from_import = True
            elif child.type == "dotted_name" and next_is_from_import:
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
                    codeFile.add_import(
                        ImportStatement(
                            source=source,
                            name=name
                        )
                    )

    @classmethod
    def _process_aliased_import(cls, node: Node, code: bytes, codeFile :CodeFileModel, source :str):
        name = None
        for child in node.children:
            if child.type == "dotted_name":
                name = cls._get_content(code, child)
            elif child.type == "identifier":
                alias = cls._get_content(code, child)
                if source is not None:
                    codeFile.add_import(
                        ImportStatement(
                            source=source,
                            name=name,
                            alias=alias
                        )
                    )

    @classmethod
    def _process_class_node(cls, node: Node, code: bytes, codeFile: CodeFileModel):
        """Process a class definition node and add it to the code file model."""
        is_class = False
        class_name = None
        bases = []
        raw = cls._get_content(code, node)
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
        raw = cls._get_content(code, node)
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
            codeFile.classes[-1].attributes.append(
                ClassAttribute(
                    name=attribute,
                    type_hint=type_hint,
                    value=default,
                    raw=raw
                )
            )
        else:
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
        raw = cls._get_content(code, node)

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
        
        if raw is None:
            raw = cls._get_content(code, node)

        if decorators is None:
            decorators = []

        ### TODO add logic to extract modifiers i.e. async
        for child in node.children:
            if child.type == "identifier":
                definition = cls._get_content(code, child)
            elif child.type == "parameters":
                ### process parameters
                signature.parameters = cls._process_parameters(child, code)
            elif child.type == "type":
                signature.return_type = cls._get_content(code, child)
        
        if is_class_method:
            codeFile.classes[-1].methods.append(
                MethodDefinition(
                    name=definition,
                    signature=signature,
                    decorators=decorators,
                    raw=raw
                )
            )
        else:
            codeFile.add_function(
                FunctionDefinition(
                    name=definition,
                    signature=signature,
                    decorators=decorators,
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
    
    def resolve_inter_files_dependencies(self, codebase: CodeBase) -> None:
        ...

if __name__ == "__main__":
    async def main():
        parser = PythonParser()
        codeFile = await parser.parse_file(
            Path("C:/Users/GL504GS/Desktop/repos/AiCore/aicore/logger.py"),
            root_path=Path("C:/Users/GL504GS/Desktop/repos/AiCore/aicore")
        )#llm/llm.py"))
        with open("oi.json", "w") as _file:
            _file.write(codeFile.model_dump_json(indent=4))

    asyncio.run(main())