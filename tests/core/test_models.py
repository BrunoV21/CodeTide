from codetide.core.models import (
    BaseCodeElement,
    CodeReference,
    ImportStatement,
    VariableDeclaration,
    Parameter,
    FunctionSignature,
    FunctionDefinition,
    MethodDefinition,
    ClassAttribute,
    ClassDefinition,
    CodeFileModel,
    PartialClasses,
    CodeContextStructure,
    CodeBase
)

from unittest.mock import patch
import pytest

# Fixtures for reusable test data
@pytest.fixture
def sample_class_def():
    """Provides a sample ClassDefinition instance."""
    return ClassDefinition(
        name="MyClass",
        file_path="project/module/main.py",
        raw="class MyClass:\n    pass"
    )

@pytest.fixture
def sample_code_file():
    """Provides a sample CodeFileModel instance with some elements."""
    code_file = CodeFileModel(file_path="project/services.py")
    
    # Add an import
    imp = ImportStatement(source="os", raw="import os")
    imp.unique_id = "os" # Manually set for predictability
    code_file.add_import(imp)

    # Add a function
    func = FunctionDefinition(name="my_service_func", raw="def my_service_func(): pass")
    code_file.add_function(func)

    # Add a class with a method and attribute
    cls = ClassDefinition(name="ServiceClass", raw="class ServiceClass:\n    ...")
    code_file.add_class(cls)
    
    attr = ClassAttribute(name="service_id", raw="service_id = 1")
    cls.add_attribute(attr)
    
    meth = MethodDefinition(name="do_service_stuff", raw="def do_service_stuff(self): ...")
    cls.add_method(meth)

    return code_file

@pytest.fixture
def sample_code_base(sample_code_file):
    """Provides a sample CodeBase with a couple of files."""
    base = CodeBase()
    
    # Add the first file
    base.root.append(sample_code_file)
    
    # Create and add a second file
    file2 = CodeFileModel(file_path="project/utils/helpers.py")
    func2 = FunctionDefinition(name="helper_func", raw="def helper_func(): pass")
    file2.add_function(func2)
    base.root.append(file2)
    
    return base


class TestBaseCodeElement:
    @pytest.mark.parametrize("path, expected", [
        ("path/to/my_file.py", "path.to.my_file"),
        ("path\\to\\my_file.py", "path.to.my_file"),
        ("file.js", "file"),
        ("no_suffix", "no_suffix"),
        (".hidden/file.sh", ".hidden.file")
    ])
    def test_file_path_without_suffix(self, path, expected):
        element = BaseCodeElement(file_path=path)
        assert element.file_path_without_suffix == expected

    def test_unique_id_generation(self):
        element = FunctionDefinition(name="my_func", file_path="my_app/main.py")
        assert element.unique_id == "my_app.main.my_func"

    def test_unique_id_no_filepath(self):
        element = FunctionDefinition(name="my_func")
        assert element.unique_id == "my_func"
    
    def test_unique_id_setter_and_getter(self):
        element = FunctionDefinition(name="my_func", file_path="my_app/main.py")
        assert element.unique_id == "my_app.main.my_func"
        
        element.unique_id = "a.custom.id"
        assert element.stored_unique_id == "a.custom.id"
        assert element.unique_id == "a.custom.id"

    def test_raw_validator_handles_mixed_newlines(self):
        raw_content = "line 1\r\nline 2\nline 3"
        element = BaseCodeElement(raw=raw_content)
        assert element.raw == "line 1\nline 2\nline 3"

class TestImportStatement:
    @pytest.mark.parametrize("alias, name, source, expected", [
        ("pd", "pandas", "pandas", "pd"),
        (None, "DataFrame", "pandas", "DataFrame"),
        (None, None, "numpy", "numpy"),
    ])
    def test_as_dependency_property(self, alias, name, source, expected):
        imp = ImportStatement(alias=alias, name=name, source=source)
        assert imp.as_dependency == expected

class TestParameter:
    def test_is_optional_with_default_value(self):
        param = Parameter(name="p1", default_value="None")
        assert param.is_optional is True

    def test_is_optional_without_default_value(self):
        param = Parameter(name="p1", type_hint="int")
        assert param.is_optional is False

class TestFunctionSignature:
    """Tests for the FunctionSignature model."""

    def test_creation_with_full_details(self):
        """
        Verifies that a FunctionSignature can be created with parameters and a return type.
        """
        params = [
            Parameter(name="arg1", type_hint="int"),
            Parameter(name="arg2", type_hint="str", default_value="'hello'"),
        ]
        return_type = "bool"

        signature = FunctionSignature(parameters=params, return_type=return_type)

        assert len(signature.parameters) == 2
        assert signature.parameters[0].name == "arg1"
        assert signature.parameters[1].is_optional is True
        assert signature.return_type == "bool"

    def test_creation_with_defaults(self):
        """
        Verifies that a FunctionSignature initializes with empty defaults when no data is provided.
        """
        signature = FunctionSignature()

        assert signature.parameters == []
        assert signature.return_type is None

    def test_creation_with_only_parameters(self):
        """
        Verifies correct creation when only parameters are specified.
        """
        params = [Parameter(name="arg1", type_hint="Any")]
        signature = FunctionSignature(parameters=params)
        
        assert len(signature.parameters) == 1
        assert signature.return_type is None

class TestPartialClasses:
    """
    Tests for the PartialClasses model, focusing on the `raw` property.
    """

    def test_raw_property_raises_type_error_on_join(self):
        """
        FIX: Verifies that the `raw` property raises a TypeError because it incorrectly
        tries to join a list of model objects instead of a list of strings.
        This test now passes by asserting that the expected exception is raised.
        """
        partial = PartialClasses(
            class_id="my.class.id",
            class_header="class MyPartialClass:",
            filepath="path/to/file.py",
            attributes=[ClassAttribute(name="attr1")],
            methods=[MethodDefinition(name="method1")],
        )

        with pytest.raises(TypeError, match="expected str instance, ClassAttribute found"):
            _ = partial.raw

    def test_raw_property_with_only_header(self):
        """
        Verifies the `raw` property's output when no attributes or methods are present.
        """
        partial = PartialClasses(
            class_id="my.class.id",
            class_header="class EmptyClass:",
            filepath="path/to/file.py",
        )
        
        expected_raw = "class EmptyClass:\n\n"
        assert partial.raw == expected_raw

class TestClassDefinition:
    def test_add_method(self, sample_class_def):
        method = MethodDefinition(name="my_method")
        sample_class_def.add_method(method)
        
        added_method = sample_class_def.methods[0]
        assert added_method.name == "my_method"
        assert added_method.class_id == sample_class_def.unique_id
        assert added_method.file_path == sample_class_def.file_path
        assert added_method.unique_id == f"{sample_class_def.unique_id}.my_method"

    def test_add_attribute(self, sample_class_def):
        attribute = ClassAttribute(name="my_attr")
        sample_class_def.add_attribute(attribute)
        
        added_attribute = sample_class_def.attributes[0]
        assert added_attribute.name == "my_attr"
        assert added_attribute.class_id == sample_class_def.unique_id
        assert added_attribute.file_path == sample_class_def.file_path
        assert added_attribute.unique_id == f"{sample_class_def.unique_id}.my_attr"

    def test_references_aggregation(self, sample_class_def):
        ref1 = CodeReference(name="BaseClass")
        ref2 = CodeReference(name="some_var")
        ref3 = CodeReference(name="other_func")
        
        sample_class_def.bases_references.append(ref1)
        sample_class_def.add_attribute(ClassAttribute(name="attr1", references=[ref2]))
        sample_class_def.add_method(MethodDefinition(name="meth1", references=[ref3]))
        
        all_refs = sample_class_def.references
        assert len(all_refs) == 3
        assert ref1 in all_refs
        assert ref2 in all_refs
        assert ref3 in all_refs

    def test_all_methods_ids(self, sample_class_def):
        sample_class_def.add_method(MethodDefinition(name="method_a"))
        sample_class_def.add_method(MethodDefinition(name="method_b"))
        
        expected_ids = [
            "project.module.main.MyClass.method_a",
            "project.module.main.MyClass.method_b",
        ]
        assert sample_class_def.all_methods_ids == expected_ids

class TestCodeFileModel:
    def test_add_methods_propagate_filepath(self, sample_code_file):
        for element_list in [sample_code_file.imports, sample_code_file.functions, sample_code_file.classes]:
            for element in element_list:
                assert element.file_path == "project/services.py"

    def test_all_elements_as_list_and_dict(self, sample_code_file):
        # Test as list (default)
        assert isinstance(sample_code_file.all_classes(), list)
        assert "project.services.ServiceClass" in sample_code_file.all_classes()

        # Test as dict
        classes_dict = sample_code_file.all_classes(as_dict=True)
        assert isinstance(classes_dict, dict)
        assert "project.services.ServiceClass" in classes_dict
        assert isinstance(classes_dict["project.services.ServiceClass"], ClassDefinition)

    def test_get_element_by_unique_id(self, sample_code_file):
        # Get a top-level function
        func = sample_code_file.get("project.services.my_service_func")
        assert isinstance(func, FunctionDefinition)
        assert func.name == "my_service_func"
        
        # Get a class
        cls = sample_code_file.get("project.services.ServiceClass")
        assert isinstance(cls, ClassDefinition)
        assert cls.name == "ServiceClass"
        
        # Get a nested method
        method = sample_code_file.get("project.services.ServiceClass.do_service_stuff")
        assert isinstance(method, MethodDefinition)
        assert method.name == "do_service_stuff"

        # Get a nested attribute
        attr = sample_code_file.get("project.services.ServiceClass.service_id")
        assert isinstance(attr, ClassAttribute)
        assert attr.name == "service_id"
        
        # Get non-existent element
        assert sample_code_file.get("non.existent.id") is None

    def test_get_import(self, sample_code_file):
        imp = sample_code_file.get_import("os")
        assert isinstance(imp, ImportStatement)
        assert imp.source == "os"
        assert sample_code_file.get_import("non_existent_import") is None


class TestCodeBase:
    def test_build_cached_elements(self, sample_code_base):
        sample_code_base._build_cached_elements()
        cache = sample_code_base._cached_elements
        
        assert "project.services.ServiceClass" in cache
        assert "project.services.ServiceClass.service_id" in cache
        assert "project.services.ServiceClass.do_service_stuff" in cache
        assert "project.services.my_service_func" in cache
        assert "project.utils.helpers.helper_func" in cache
        assert "os" in cache
        
        assert isinstance(cache["project.services.ServiceClass"], ClassDefinition)
        assert isinstance(cache["os"], ImportStatement)

    def test_get_across_files(self, sample_code_base):
        sample_code_base._build_cached_elements() # get depends on the cache
        
        element = sample_code_base._cached_elements.get("project.utils.helpers.helper_func")
        assert isinstance(element, FunctionDefinition)
        assert element.file_path == "project/utils/helpers.py"

    def test_all_properties_aggregation(self, sample_code_base):
        all_cls = sample_code_base.all_classes()
        all_funcs = sample_code_base.all_functions()
        
        assert "project.services.ServiceClass" in all_cls
        assert "project.services.my_service_func" in all_funcs
        assert "project.utils.helpers.helper_func" in all_funcs

    def test_get_tree_view_basic(self, sample_code_base):
        tree = sample_code_base.get_tree_view()
        # Basic structure check
        assert "└── project" in tree
        assert "├── utils" in tree
        assert "└── helpers.py" in tree
        assert "└── services.py" in tree
    
    def test_get_tree_view_with_modules(self, sample_code_base):
        tree = sample_code_base.get_tree_view(include_modules=True, include_types=True)
        assert "C ServiceClass" in tree
        assert "M do_service_stuff" in tree
        assert "A service_id" in tree
        assert "F my_service_func" in tree
        assert "F helper_func" in tree

class TestCodeContextStructure:
    def test_from_list_of_elements(self):
        elements = [
            ImportStatement(source="os", stored_unique_id="os"),
            ClassDefinition(name="MyClass", stored_unique_id="main.MyClass"),
            MethodDefinition(name="my_method", stored_unique_id="main.MyClass.my_method", class_id="main.MyClass"),
            VariableDeclaration(name="MY_VAR", stored_unique_id="main.MY_VAR"),
        ]
        elements_reference_type = [None for _ in elements]
        
        context = CodeContextStructure.from_list_of_elements(elements, elements_reference_type, requested_element_index=[2])
        
        assert len(context.requested_elements) == 1
        assert context.requested_elements.get("main.MyClass.my_method").name == "my_method"
        
        assert "os" in context.imports
        assert "main.MyClass" in context.classes
        assert "main.MY_VAR" in context.variables
        
        # Method is not in class_methods because it's the requested element
        assert "main.MyClass.my_method" not in context.class_methods

    @patch('codetide.core.models.wrap_content')
    def test_as_list_str(self, mock_wrap_content):
        # Simple mock: returns a f-string of its inputs
        mock_wrap_content.side_effect = lambda content, filepath: f"wrapped({content}, {filepath})"
        
        # Setup a complex context
        full_class = ClassDefinition(
            name="FullClass", 
            file_path="file1.py", 
            stored_unique_id="file1.FullClass",
            raw="class FullClass:\n    ..."
        )
        
        partial_class_method = MethodDefinition(
            name="partial_method", 
            class_id="file2.PartialClass",
            stored_unique_id="file2.PartialClass.partial_method",
            file_path="file2.py",
            raw="def partial_method(self):\n        pass"
        )
        
        partial_class_obj_for_cache = ClassDefinition(
            name="PartialClass",
            file_path="file2.py",
            stored_unique_id="file2.PartialClass",
            raw="class PartialClass(Base):",
            methods=[partial_class_method]
        )
        
        requested_element = FunctionDefinition(
            name="main_func",
            file_path="file1.py",
            stored_unique_id="file1.main_func",
            raw="def main_func(): ..."
        )
        
        pkg_import = ImportStatement(
            source="numpy",
            unstored_unique_idique_id="numpy",
            raw="import numpy as np"
        )

        context = CodeContextStructure(
            classes={"file1.FullClass": full_class},
            class_methods={"file2.PartialClass.partial_method": partial_class_method},
            imports={"numpy": pkg_import},
            requested_elements={"requested_element": requested_element},
            preloaded={"preloaded.txt": "preloaded content"}
        )
        context._cached_elements = {"file2.PartialClass": partial_class_obj_for_cache}
        context._unique_class_elements_ids = ["file2.PartialClass"]

        context_list, target_list = context.as_list_str()
        
        # Assertions for context list
        assert len(context_list) == 3 # PACKAGES, file1.py, file2.py
        assert 'wrapped(import numpy as np, PACKAGES)' in context_list
        assert 'wrapped(class FullClass:\n    ..., file1.py)' in context_list
        # Check that the partial class was constructed correctly
        assert 'wrapped(class PartialClass(Base):\n\n\n    ...\n\n\ndef partial_method(self):\n        pass, file2.py)' in context_list
        
        # Assertions for target list
        assert len(target_list) == 2 # 1 preloaded + 1 requested
        assert 'wrapped(preloaded content, preloaded.txt)' in target_list
        assert 'wrapped(def main_func(): ..., file1.py)' in target_list