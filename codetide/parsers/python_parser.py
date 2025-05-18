from typing import Optional, Union
from pathlib import Path
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython
from pydantic import model_validator
from codetide.core.models import (
    ImportStatement, CodeFileModel
)
from codetide.parsers.base_parser import BaseParser

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

    def parse_file(self, file_path: Union[str, Path], root_path: Optional[Union[str, Path]]=None) -> CodeFileModel:
        """
        Parse a Python source file and return a CodeFileModel.
        """
        file_path = Path(file_path).absolute()
        with open(file_path, 'rb') as _file:
            code = _file.read()
        
        if root_path is not None:
            file_path = file_path.relative_to(Path(root_path))

        tree = self.tree_parser.parse(code)
        root_node = tree.root_node

        codeFile = CodeFileModel(file_path=str(file_path))
        self._process_node(root_node, code, codeFile)

        print(codeFile.imports)

        return codeFile
    
    @classmethod
    def _process_node(cls, node: Node, code: bytes, codeFile :CodeFileModel):
    
        for child in node.children:
            content = cls._get_content(code, child)
            print("\n", child.type, content)
            if child.type.startswith("import"):# == "import_from_statement":
                cls._process_import_from_node(child, code, codeFile)
            # elif child.type == "import":


    @classmethod
    def _process_import_from_node(cls, node: Node, code: bytes, codeFile :CodeFileModel):
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
                    codeFile.imports.append(
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
                    codeFile.imports.append(
                        ImportStatement(
                            source=source,
                            name=name,
                            alias=alias
                        )
                    )
