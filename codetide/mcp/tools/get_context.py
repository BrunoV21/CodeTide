from typing import List, Optional, Union
from ..server import codeTideMCPServer
from ..utils import initCodeTide

@codeTideMCPServer.tool
async def getContext(
    code_identifiers: Union[str, List[str]],
    context_depth: int = 1) -> Optional[str]:
    """
    Retrieves relevant code context for the given code element identifiers.
    Returns None if identifiers are invalid.

    Args:
        code_identifiers: One or more identifiers in dot notation representing:
                         - Test classes: 'tests.module.test_class.TestClass'
                         - Test methods: 'tests.module.test_class.TestClass.test_method'
                         - Core classes: 'package.module.ClassName'
                         - Class attributes: 'package.module.ClassName.attribute'
                         - Methods: 'package.module.ClassName.method'
                         - Setters: 'package.module.ClassName.property@property.setter'
                         - Services: 'package.services.ServiceName'
                         - Service methods: 'package.services.ServiceName.execute'
                         - File paths: 'package/module.py' (forward slashes)
                         
                         Common patterns:
                         - Package.Class: 'package.module.ClassName'
                         - Package.Class.method: 'package.module.ClassName.method_name'
                         - Package.Class.attribute: 'package.module.ClassName.attribute_name'
                         - TestPackage.TestClass.test_method: 'tests.module.TestClass.test_feature'
                         - ServicePackage.Service.method: 'services.backend.Service.process'

                         Examples:
                         - Single test method: 'tests.parser.test_parser.TestParser.test_file_processing'
                         - Class with attributes: 'core.models.ImportStatement'
                         - Multiple elements: [
                             'core.models.FunctionDefinition',
                             'tests.parser.test_parser.TestParser.test_imports'
                           ]

        context_depth: How many reference levels to include:
                      0 = Only the requested element(s) (no references)
                      1 = Direct references only (default)
                      2 = References of references
                      n = n-level deep reference chain

    Returns:
        Formatted string containing:
        - The requested code elements
        - Their declarations
        - Related imports
        - Reference implementations
        - Syntax-highlighted source code
        or None if identifiers don't exist.

    Notes:
        - For test classes/methods: Use full test path including 'test_' prefix
        - For setters: Use @property.setter notation
        - Private methods: Include underscore prefix (e.g., '_internal_method')
        - File paths must use forward slashes and be relative to repo root
        - Case sensitive matching
        - When unsure, use getRepoTree() first to discover available identifiers
    """

    tide = await initCodeTide()
    context = await tide.get(code_identifiers, context_depth, as_string=True)
    return context