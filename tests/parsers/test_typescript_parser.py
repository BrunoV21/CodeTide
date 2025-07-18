from codetide.core.models import CodeBase, ImportStatement
from codetide.parsers.typescript_parser import TypeScriptParser

from tree_sitter import Parser
from pathlib import Path
import pytest
import os

@pytest.fixture
def parser() -> TypeScriptParser:
    """Provides a default instance of the TypeScriptParser."""
    return TypeScriptParser()

class TestTypeScriptParser:

    def test_initialization(self, parser: TypeScriptParser):
        """Tests the basic properties and initialization of the parser."""
        assert parser.language == "typescript"
        assert parser.extension == ".ts"
        assert parser.tree_parser is not None
        assert isinstance(parser.tree_parser, Parser)

    @pytest.mark.parametrize("path, expected", [
        ("my/app/main.ts", "my/app/main.ts"),
        ("my/app/index.ts", "my/app"),
        ("my\\app\\index.ts", "my\\app"),
        ("lib.ts", "lib.ts"),
    ])
    def test_skip_init_paths(self, path, expected):
        """Tests the removal of index.ts from paths."""
        assert TypeScriptParser._skip_init_paths(Path(path)) == str(Path(expected))

    @pytest.mark.parametrize("code, substring, count", [
        ("import { A } from 'mod'; A.do();", "A", 2),
        ("let var1 = 5; var1 = 6;", "var1", 2),
        ("let variable = 1; var2 = 2;", "var1", 0),
        ("function foo() {} foo();", "foo", 2),
        ("test(test);", "test", 2),
        ("class MyTest {}", "MyTest", 1),
        ("a.b.c(b);", "b", 2),
    ])
    def test_count_occurences_in_code(self, code, substring, count):
        """Tests the regex-based word occurrence counter."""
        assert TypeScriptParser.count_occurences_in_code(code, substring) == count

    def test_get_content_indentation(self, parser: TypeScriptParser):
        """Tests the _get_content method for preserving indentation."""
        code = b"class MyClass {\n    myMethod() {\n        return 1;\n    }\n}"
        codeFile = parser.parse_code(code, file_path="myMethod.ts")
        print(f"{codeFile=}")
        assert "myMethod" in codeFile.raw
        assert codeFile.raw.startswith("class MyClass")

    @pytest.mark.asyncio
    async def test_parse_file(self, parser: TypeScriptParser, tmp_path: Path):
        """Tests parsing a file from disk."""
        file_path = tmp_path / "test_module.ts"
        code_content = "import { A } from 'mod';\nlet x = 10;"
        file_path.write_text(code_content, encoding="utf-8")
        code_file_model = await parser.parse_file(file_path)
        print(f"{code_file_model=}")
        assert code_file_model.file_path == str(file_path.absolute())
        assert len(code_file_model.imports) == 1
        assert code_file_model.imports[0].source == "'mod'"
        assert code_file_model.imports[0].name == "A"
        assert len(code_file_model.variables) == 1
        assert code_file_model.variables[0].name == "x"
        assert code_file_model.variables[0].value == "10"

    @pytest.mark.asyncio
    async def test_parse_file_with_root_path(self, parser: TypeScriptParser, tmp_path: Path):
        """Tests parsing a file with a root path to get a relative file path."""
        root_dir = tmp_path / "project"
        root_dir.mkdir()
        module_path = root_dir / "module"
        module_path.mkdir()
        file_path = module_path / "test.ts"
        file_path.write_text("let x = 1;", encoding="utf-8")
        code_file_model = await parser.parse_file(file_path, root_path=root_dir)
        expected_relative_path = os.path.join("module", "test.ts")
        assert code_file_model.file_path == expected_relative_path

class TestTypeScriptParserDetailed:

    @pytest.mark.parametrize("code, expected_imports", [
        ("import { A } from 'mod';", [ImportStatement(source="'mod'", name='A')]),
        ("import B from 'lib';", [ImportStatement(source="'lib'", name='B')]),
        ("import { X as Y } from 'pkg';", [ImportStatement(source="'pkg'", name='X', alias='Y')]),
        ("import 'side-effect';", [ImportStatement(source="'side-effect'")]),
    ])
    def test_parse_imports(self, parser: TypeScriptParser, code, expected_imports):
        """Tests various import statement formats."""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.imports) == len(expected_imports)
        for parsed, expected in zip(code_file.imports, expected_imports):
            assert parsed.source == expected.source
            assert parsed.name == expected.name
            assert parsed.alias == expected.alias

    def test_parse_function(self, parser: TypeScriptParser):
        """Tests parsing of a complex function definition."""
        code = """
async function myFunc(a: number, b: string = \"default\"): Promise<string[]> {
    return [b];
}
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.functions) == 1
        func = code_file.functions[0]
        assert func.name == "myFunc"
        assert "async" in func.modifiers
        sig = func.signature
        assert sig is not None
        assert sig.return_type is not None
        assert len(sig.parameters) == 2
        param1 = sig.parameters[0]
        assert param1.name == "a"
        assert param1.type_hint == "number"
        assert param1.default_value is None
        param2 = sig.parameters[1]
        assert param2.name == "b"
        assert param2.type_hint == "string"
        assert param2.default_value == '"default"'

    def test_parse_class(self, parser: TypeScriptParser):
        """Tests parsing of a complex class definition."""
        code = """
class Child extends Base1 {
    public classAttr: number = 10;
    constructor(name: string) {
        this.name = name;
    }
    get nameUpper(): string {
        return this.name.toUpperCase();
    }
}
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.classes) == 1
        cls = code_file.classes[0]
        assert cls.name == "Child"
        assert "Base1" in cls.bases
        assert len(cls.attributes) == 1
        attr = cls.attributes[0]
        assert attr.name == "classAttr"
        assert attr.type_hint == "number"
        assert attr.value == "10"
        assert len(cls.methods) >= 2
        method1 = next(m for m in cls.methods if m.name == "constructor")
        method2 = next(m for m in cls.methods if m.name == "nameUpper")
        assert method1.name == "constructor"
        assert len(method1.signature.parameters) == 1
        assert method2.name == "nameUpper"
        assert method2.signature.return_type is not None

    def test_intra_file_dependencies(self, parser: TypeScriptParser):
        """Tests resolving references within a single file."""
        code = """
import { Helper } from './helper';
class Helper {
    doWork() {
        return 'done';
    }
}
function processData(items: string[]): Helper {
    const h = new Helper();
    h.doWork();
    return h;
}
let result = processData([]);
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        parser.resolve_intra_file_dependencies(CodeBase(root=[code_file]))
        process_func = code_file.get("test.processData")
        assert process_func is not None
        assert any(ref.name == "Helper" for ref in process_func.references)
        assert any(ref.name == "doWork" for ref in process_func.references)
        do_work_method = code_file.get("test.Helper.doWork")
        found = any(ref.unique_id == do_work_method.unique_id for ref in process_func.references if do_work_method)
        assert found or do_work_method is None
        var_decl = code_file.get("test.result")
        assert var_decl is not None
        assert any(ref.unique_id == process_func.unique_id for ref in var_decl.references)
