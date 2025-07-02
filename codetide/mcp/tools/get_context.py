from ..server import codeTideMCPServer
from ..utils import initCodeTide

from typing import List

@codeTideMCPServer.tool
async def getContext(
    code_identifiers: List[str],
    context_depth: int = 1) -> str:
    """
    Retrieve code context for one or more identifiers.

    Args:
        code_identifiers: List of dot- or slash-form identifiers, e.g.:
            - 'package.module.Class.method'
            - 'tests.module.TestClass.test_method'
            - 'package/module.py'
        Prefer batching multiple identifiers in a single call for better
        cross-referencing and performance.

        context_depth (int): Reference depth:
            0 – Only requested elements
            1 – + Direct references (default)
            2+ – + Recursive references

    Returns:
        str: Formatted context including:
            - Declarations
            - Imports
            - Related references
            - Syntax-highlighted code
        Returns None if no matching identifiers found.

    Guidelines:
        - Identifiers are case-sensitive
        - Use full test paths with `test_` prefix
        - For setters: use @property.setter format
        - Include underscores for private members
        - File paths must use forward slashes, repo-relative
        - Use getRepoTree() to discover valid identifiers

    Note:
        To analyze related code, retrieve all needed identifiers in a single call to
        getContext. This ensures better performance and richer, linked context.
    """

    tide = await initCodeTide()
    context = tide.get(code_identifiers, context_depth, as_string=True)
    return context if context else f"{code_identifiers} are not valid code_identifiers, refer to the getRepoTree tool to get a sense of the correct identifiers"