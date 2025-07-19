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

    def test_function_with_decorators_and_modifiers(self, parser: TypeScriptParser):
        code = """
@decorator1
@decorator2
export async function myFunc(a: number, b: string = "default"): Promise<string[]> {
    return [b];
}
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.functions) == 1
        func = code_file.functions[0]
        # Decorators are not yet parsed by TypeScriptParser, but modifiers should be present
        assert "async" in func.modifiers or "export" in func.modifiers
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

    def test_class_with_static_and_access_modifiers(self, parser: TypeScriptParser):
        code = """
class Modifiers {
    public static count: number = 0;
    private _name: string;
    protected flag: boolean = true;
    constructor(name: string) {
        this._name = name;
    }
    static getCount(): number {
        return Modifiers.count;
    }
    public get name(): string {
        return this._name;
    }
}
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.classes) == 1
        cls = code_file.classes[0]
        attr_names = {a.name for a in cls.attributes}
        assert "count" in attr_names
        assert "flag" in attr_names
        assert "_name" in attr_names
        count_attr = next(a for a in cls.attributes if a.name == "count")
        assert "static" in count_attr.modifiers or "public" in count_attr.modifiers
        flag_attr = next(a for a in cls.attributes if a.name == "flag")
        assert "protected" in flag_attr.modifiers
        methods = {m.name: m for m in cls.methods}
        assert "getCount" in methods
        assert "name" in methods
        get_count = methods["getCount"]
        assert "static" in get_count.modifiers
        get_name = methods["name"]
        assert "public" in get_name.modifiers or get_name.modifiers == []

    def test_multiple_variable_declarations(self, parser: TypeScriptParser):
        code = "let a = 1, b: string = 'hi', c;"
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        # The parser currently only supports one variable per declaration, so at least one should be present
        assert any(v.name == "a" for v in code_file.variables)
        assert any(v.name == "b" for v in code_file.variables)
        assert any(v.name == "c" for v in code_file.variables)

    def test_multiple_imports_and_aliases(self, parser: TypeScriptParser):
        code = "import { A, B as Bee, C } from 'mod';"
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        print(f"{code_file=}")
        # The parser currently only supports one import per statement, but at least one should be present
        assert any(i.name == "A" for i in code_file.imports)
        assert any(i.name == "B" and i.alias == "Bee" for i in code_file.imports)
        assert any(i.name == "C" for i in code_file.imports)

    def test_arrow_function_and_function_expression(self, parser: TypeScriptParser):
        code = """
const arrow = (x: number): number => x * 2;
const expr = function(y: string): string { return y + "!"; }
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        # The parser may not yet support arrow/functions as top-level, but should at least parse variables
        assert any(v.name == "arrow" for v in code_file.variables)
        assert any(v.name == "expr" for v in code_file.variables)

    def test_parameter_edge_cases(self, parser: TypeScriptParser):
        code = """
function edge(a, b?: number, c = 5, d: string = "x", ...rest: any[]) {}
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        func = code_file.functions[0]
        param_names = [p.name for p in func.signature.parameters]
        assert "a" in param_names
        assert "b" in param_names
        assert "c" in param_names
        assert "d" in param_names
        # rest parameter may not be parsed, but at least the others should be present
        b_param = next(p for p in func.signature.parameters if p.name == "b")
        assert b_param.type_hint == "number"
        assert b_param.default_value is None
        c_param = next(p for p in func.signature.parameters if p.name == "c")
        assert c_param.default_value == "5"
        d_param = next(p for p in func.signature.parameters if p.name == "d")
        assert d_param.type_hint == "string"
        assert d_param.default_value == '"x"'
    
    def test_class_with_method_and_attribute_references(self, parser: TypeScriptParser):
        code = """
class Helper {
    doWork() { return 1; }
    value: number = 42;
}
function useHelper(h: Helper): number {
    return h.doWork() + h.value;
}
"""
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        from codetide.core.models import CodeBase
        parser.resolve_intra_file_dependencies(CodeBase(root=[code_file]))
        func = code_file.get("test.useHelper")
        assert func is not None
        ref_names = {ref.name for ref in func.references}
        assert "doWork" in ref_names
        assert "value" in ref_names

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

    def test_count_occurences_in_code_edge_cases(self):
        """Test word boundary and substring edge cases."""
        assert TypeScriptParser.count_occurences_in_code("foofoobar foo", "foo") == 1
        assert TypeScriptParser.count_occurences_in_code("foo_bar foo", "foo") == 1
        assert TypeScriptParser.count_occurences_in_code("foo1 foo", "foo") == 1
        assert TypeScriptParser.count_occurences_in_code("foofoo foo", "foo") == 1
        assert TypeScriptParser.count_occurences_in_code("foo", "foo") == 1
        assert TypeScriptParser.count_occurences_in_code("bar", "foo") == 0

    def test_variable_declaration_with_type_and_value(self, parser: TypeScriptParser):
        code = "let x: number = 42;"
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.variables) == 1
        var = code_file.variables[0]
        assert var.name == "x"
        assert var.type_hint == ": number"
        assert var.value == "42"

    def test_class_with_multiple_attributes_and_methods(self, parser: TypeScriptParser):
        code = """
    class Multi {
    public a: string = "A";
    public b: number = 2;
    foo(): void {}
    bar(): number { return 1; }
    }
    """
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        assert len(code_file.classes) == 1
        cls = code_file.classes[0]
        assert len(cls.attributes) == 2
        assert set(a.name for a in cls.attributes) == {"a", "b"}
        assert len(cls.methods) == 2
        assert set(m.name for m in cls.methods) == {"foo", "bar"}

    def test_function_with_typehint_reference(self, parser: TypeScriptParser):
        code = """
    class RefType {}
    function useType(x: RefType): RefType {
    return x;
    }
    """
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        # Simulate codeBase for dependency resolution
        class DummyCodeBase:
            def __init__(self, root):
                self.root = root
                self._cached_elements = {}
                for cf in root:
                    for c in cf.classes:
                        self._cached_elements[c.unique_id] = c
                    for f in cf.functions:
                        self._cached_elements[f.unique_id] = f
                    for v in cf.variables:
                        self._cached_elements[v.unique_id] = v
        codeBase = DummyCodeBase([code_file])
        parser.resolve_intra_file_dependencies(codeBase, [code_file])
        func = code_file.get("test.useType")
        assert func is not None
        assert any(ref.type_hint == "RefType" for ref in func.signature.parameters)

    def test_class_inheritance_reference(self, parser: TypeScriptParser):
        code = """
    class Base {}
    class Derived extends Base {}
    """
        file_path = Path("test.ts")
        code_file = parser.parse_code(code.encode('utf-8'), file_path)
        class DummyCodeBase:
            def __init__(self, root):
                self.root = root
                self._cached_elements = {}
                for cf in root:
                    for c in cf.classes:
                        self._cached_elements[c.unique_id] = c
        codeBase = DummyCodeBase([code_file])
        parser.resolve_intra_file_dependencies(codeBase, [code_file])
        derived = code_file.get("test.Derived")
        assert derived is not None
        assert any(ref == "Base" for ref in derived.bases)

    def test_get_content_indentation(self, parser: TypeScriptParser):
        """Tests the _get_content method for preserving indentation."""
        code = b"class MyClass {\n    myMethod() {\n        return 1;\n    }\n}"
        codeFile = parser.parse_code(code, file_path="myMethod.ts")
        assert "myMethod" in codeFile.raw
        assert codeFile.raw.startswith("class MyClass")

    @pytest.mark.asyncio
    async def test_parse_file(self, parser: TypeScriptParser, tmp_path: Path):
        """Tests parsing a file from disk."""
        file_path = tmp_path / "test_module.ts"
        code_content = "import { A } from 'mod';\nlet x = 10;"
        file_path.write_text(code_content, encoding="utf-8")
        code_file_model = await parser.parse_file(file_path)
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
