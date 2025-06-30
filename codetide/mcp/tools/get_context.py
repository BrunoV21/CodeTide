from typing import List, Union
from ..server import codeTideMCPServer
from ..utils import initCodeTide

@codeTideMCPServer.tool
async def getContext(
    code_identifiers: Union[str, List[str]],
    context_depth: int = 1) -> str:
    """
    Retrieves code context for one or more identifiers. Returns None if invalid.

    Args:
        code_identifiers: Dot- or slash-notated identifiers, such as:
            - 'tests.module.TestClass.test_method'
            - 'package.module.Class.method_or_attr'
            - 'services.backend.Service.execute'
            - 'package/module.py'
            - Or a list of such identifiers

        context_depth: Reference depth to include:
            0 – Only the requested element(s)
            1 – Direct references (default)
            2+ – Recursive reference levels

    Returns:
        A formatted string with:
            - Declarations
            - Imports
            - Related references
            - Syntax-highlighted code
        Returns None if identifiers are not found.

    Notes:
        - Identifiers are case-sensitive
        - Use full paths for test elements and include 'test_' prefix
        - Setters: Use @property.setter format
        - Private methods: Include leading underscore
        - File paths must be forward slashes, repo-relative
        - Use getRepoTree() to explore available identifiers
    """

    tide = await initCodeTide()
    context = tide.get(code_identifiers, context_depth, as_string=True)
    return context if context else f"{code_identifiers} are not valid code_identifiers, refer to the getRepoTree tool to get a sense of the correct identifiers"