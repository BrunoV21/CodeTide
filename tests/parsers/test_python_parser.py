from codetide.core.models import CodeBase, ImportStatement
from codetide.parsers.python_parser import PythonParser

from tree_sitter import Parser
from pathlib import Path
import pytest
import os


@pytest.fixture
def parser() -> PythonParser:
    """Provides a default instance of the PythonParser."""
    return PythonParser()

class TestPythonParser:

    @pytest.mark.parametrize("content,expected", [
        ('"""This is a docstring"""', True),
        ("'''This is a docstring'''", True),
        ('"""Multiline\ndocstring"""', True),
        ("'''Multiline\ndocstring'''", True),
        ('"Not a docstring"', False),
        ("'Not a docstring'", False),
        ("", False),
        (None, False),
        ('"""Unclosed docstring', False),
        ("'''Unclosed docstring", False),
        ('"""   """', True),
        ("'''   '''", True),
        ('"""', False),
        ("'''", False),
    ])
    def test_is_docstring(self, content, expected):
        assert PythonParser.is_docstring(content) == expected

    @pytest.mark.parametrize("raw,docstring,expected", [
        ("def f():\n    pass", None, None),
        ("def f():\n    \"\"\"Docstring\"\"\"", '"""Docstring"""', "def f():\n    \"\"\"Docstring\"\"\""),
        ("def f():\n    '''Docstring'''", "'''Docstring'''", "def f():\n    '''Docstring'''"),
        ("def f():\n    pass", "", None),
        ("def f():\n    not a docstring", "not a docstring", "def f():\n    not a docstring"),
        ("def f():\n    \"\"\"Multi\nLine\"\"\"", '"""Multi\nLine"""', "def f():\n    \"\"\"Multi\nLine\"\"\""),
    ])
    def test_compile_docstring(self, raw, docstring, expected):
        assert PythonParser.compile_docstring(raw, docstring) == expected
        
    @pytest.mark.parametrize("code, expected_docstring", [
        (
            '''
def foo():
    """This is a function docstring."""
    return 1
''',
            '"""This is a function docstring."""'
        ),
        (
            """
def bar():
    '''
    Multiline
    docstring
    '''
    return 2
""",
            "'''\n    Multiline\n    docstring\n    '''"
        ),
        (
            '''
def no_doc():
    return 3
''',
            None
        ),
        (
            '''
def empty_doc():
    """   """
    return 4
''',
            '"""   """'
        ),
    ])
    def test_parse_function_docstring(self, parser: PythonParser, code, expected_docstring):
        file_path = Path("test.py")
        code_file = parser.parse_code(code.encode("utf-8"), file_path)
        func = code_file.functions[0]
        if expected_docstring is None:
            assert func.docstring is None
        else:
            assert expected_docstring in func.docstring

    @pytest.mark.parametrize("code, expected_docstring", [
        (
            '''
class Foo:
    """Class docstring."""
    x = 1
''',
            '"""Class docstring."""'
        ),
        (
            """
class Bar:
    '''
    Multiline
    class docstring
    '''
    y = 2
""",
            "'''\n    Multiline\n    class docstring\n    '''"
        ),
        (
            '''
class NoDoc:
    z = 3
''',
            None
        ),
        (
            '''
class EmptyDoc:
    """   """
    a = 4
''',
            '"""   """'
        ),
    ])
    def test_parse_class_docstring(self, parser: PythonParser, code, expected_docstring):
        file_path = Path("test.py")
        code_file = parser.parse_code(code.encode("utf-8"), file_path)
        cls = code_file.classes[0]
        if expected_docstring is None:
            assert cls.docstring is None
        else:
            assert expected_docstring in cls.docstring

    @pytest.mark.parametrize("import_stmt, expected", [
        (ImportStatement(source="os"), "import os"),
        (ImportStatement(name="numpy", alias="np"), "import numpy as np"),
        (ImportStatement(source="pathlib", name="Path"), "from pathlib import Path"),
        (ImportStatement(source="collections", name="deque", alias="dq"), "from collections import deque as dq"),
        (ImportStatement(source="typing"), "import typing"),
    ])
    def test_import_statement_template(self, import_stmt, expected):
        assert PythonParser.import_statement_template(import_stmt) == expected

    def test_relative_import_parsing(self, parser: PythonParser):
        code = "from .submodule import foo"
        file_path = Path("pkg/__init__.py")
        code_file = parser.parse_code(code.encode("utf-8"), file_path)
        assert len(code_file.imports) == 1
        imp = code_file.imports[0]
        assert imp.import_type == "relative"
        assert imp.source is not None
        assert "submodule" in imp.source

    def test_initialization(self, parser: PythonParser):
        """Tests the basic properties and initialization of the parser."""
        assert parser.language == "python"
        assert parser.extension == ".py"
        assert parser.tree_parser is not None
        assert isinstance(parser.tree_parser, Parser)

    @pytest.mark.parametrize("path, expected", [
        ("my/app/main.py", "my/app/main.py"),
        ("my/app/__init__.py", "my/app"),
        ("my\\app\\__init__.py", "my\\app"),
        ("lib.py", "lib.py"),
    ])
    def test_skip_init_paths(self, path, expected):
        """Tests the removal of __init__.py from paths."""
        assert PythonParser._skip_init_paths(Path(path)) == str(Path(expected))

    @pytest.mark.parametrize("code, substring, count", [
        ("import os; os.getcwd()", "os", 2),
        ("var = my_var", "var", 1),
        ("variable = my_var", "var", 0),
        ("def func():\n  pass\nfunc()", "func", 2),
        ("test(test)", "test", 2),
        ("class MyTest: pass", "MyTest", 1),
        ("a.b.c(b)", "b", 2),
    ])
    def test_count_occurences_in_code(self, code, substring, count):
        """Tests the regex-based word occurrence counter."""
        assert PythonParser.count_occurences_in_code(code, substring) == count

    def test_get_content_indentation(self, parser: PythonParser):
        """Tests the _get_content method for preserving indentation."""
        code = b"class MyClass:\n    def method(self):\n        pass"
        tree = parser.tree_parser.parse(code)
        # function_definition node
        method_node = tree.root_node.children[0].children[-1].children[0]
        
        content_no_indent = parser._get_content(code, method_node, preserve_indentation=False)
        assert content_no_indent == "def method(self):\n        pass"

        content_with_indent = parser._get_content(code, method_node, preserve_indentation=True)
        assert content_with_indent == "    def method(self):\n        pass"

    @pytest.mark.asyncio
    async def test_parse_file(self, parser: PythonParser, tmp_path: Path):
        """Tests parsing a file from disk."""
        file_path = tmp_path / "test_module.py"
        code_content = "import os\n\nx = 10"
        file_path.write_text(code_content, encoding="utf-8")

        code_file_model = await parser.parse_file(file_path)

        assert code_file_model.file_path == str(file_path.absolute())
        assert len(code_file_model.imports) == 1
        assert code_file_model.imports[0].source == "os"
        assert len(code_file_model.variables) == 1
        assert code_file_model.variables[0].name == "x"
        assert code_file_model.variables[0].value == "10"
        
    @pytest.mark.asyncio
    async def test_parse_file_with_root_path(self, parser: PythonParser, tmp_path: Path):
        """Tests parsing a file with a root path to get a relative file path."""
        root_dir = tmp_path / "project"
        root_dir.mkdir()
        module_path = root_dir / "module"
        module_path.mkdir()
        file_path = module_path / "test.py"
        file_path.write_text("x = 1", encoding="utf-8")

        code_file_model = await parser.parse_file(file_path, root_path=root_dir)
        
        # Should be relative to root_dir
        expected_relative_path = os.path.join("module", "test.py")
        assert code_file_model.file_path == expected_relative_path

class TestPythonParserDetailed:

    @pytest.mark.parametrize("code, expected_imports", [
        ("import os", [ImportStatement(source='os')]),
        ("import numpy as np", [ImportStatement(name='numpy', alias='np')]),
        ("from pathlib import Path", [ImportStatement(source='pathlib', name='Path')]),
        ("from collections import deque, defaultdict", [
             ImportStatement(source='collections', name='deque'),
             ImportStatement(source='collections', name='defaultdict')
        ]),
        ("from typing import List as L", [ImportStatement(source='typing', name='List', alias='L')]),
    ])
    def test_parse_imports(self, parser: PythonParser, code, expected_imports):
        """Tests various import statement formats."""
        file_path = Path("test.py")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        print(f"{code_file.imports=}")
        assert len(code_file.imports) == len(expected_imports)
        for parsed, expected in zip(code_file.imports, expected_imports):
            assert parsed.source == expected.source
            assert parsed.name == expected.name
            assert parsed.alias == expected.alias

    def test_parse_function(self, parser: PythonParser):
        """Tests parsing of a complex function definition."""
        code = """
@decorator1
@decorator2
async def my_func(a: int, b: str = "default") -> List[str]:
    '''docstring'''
    return [b] * a
"""
        file_path = Path("test.py")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)

        assert len(code_file.functions) == 1
        func = code_file.functions[0]

        assert func.name == "my_func"
        assert func.decorators == ["@decorator1", "@decorator2"]
        assert func.modifiers == ["async"]
        
        sig = func.signature
        assert sig is not None
        assert sig.return_type == "List[str]"
        assert len(sig.parameters) == 2

        param1 = sig.parameters[0]
        assert param1.name == "a"
        assert param1.type_hint == "int"
        assert param1.default_value is None

        param2 = sig.parameters[1]
        assert param2.name == "b"
        assert param2.type_hint == "str"
        assert param2.default_value == '"default"'

    def test_parse_class(self, parser: PythonParser):
        """Tests parsing of a complex class definition."""
        code = """
class Child(Base1, Base2):
    class_attr: int = 10

    def __init__(self, name: str):
        self.name = name

    @property
    def name_upper(self) -> str:
        return self.name.upper()
"""
        file_path = Path("test.py")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.classes) == 1
        cls = code_file.classes[0]

        assert cls.name == "Child"
        assert "Base1" in cls.bases
        assert "Base2" in cls.bases
        
        assert len(cls.attributes) == 1
        attr = cls.attributes[0]
        assert attr.name == "class_attr"
        assert attr.type_hint == "int"
        assert attr.value == "10"

        assert len(cls.methods) == 2
        method1 = next(m for m in cls.methods if m.name == "__init__")
        method2 = next(m for m in cls.methods if m.name == "name_upper")

        assert method1.name == "__init__"
        assert len(method1.signature.parameters) == 1 # name
        assert method1.decorators == []
        
        assert method2.name == "name_upper"
        assert method2.signature.return_type == "str"
        assert method2.decorators == ["@property"]

    def test_intra_file_dependencies(self, parser: PythonParser):
        """Tests resolving references within a single file."""
        code = """
from typing import List

class Helper:
    def do_work(self):
        return "done"

def process_data(items: List[str]) -> Helper:
    h = Helper()
    h.do_work()
    return h

var = process_data([])
"""
        file_path = Path("test.py")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        parser.resolve_intra_file_dependencies(CodeBase(root=[code_file]))
        
        # process_data should reference List and Helper
        process_func = code_file.get("test.process_data")
        assert len(process_func.references) == 3 
        ref_names = {ref.name for ref in process_func.references}
        assert "List" in ref_names
        assert "do_work" in ref_names

        # Class Helper method `do_work` is referenced
        do_work_method = code_file.get("test.Helper.do_work")
        # Assert that `process_data` references `do_work`
        found = any(ref.unique_id == do_work_method.unique_id for ref in process_func.references)
        assert found
        assert "h.do_work" in process_func.raw # Simple check

        # var should reference process_data
        var_decl = code_file.get("test.var")
        assert len(var_decl.references) == 1
        assert var_decl.references[0].unique_id == process_func.unique_id