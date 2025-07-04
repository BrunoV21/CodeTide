from ..server import codeTideMCPServer
from ..utils import initCodeTide

from typing import List

@codeTideMCPServer.tool
async def getCodeContext(
    code_identifiers: List[str],
    context_depth: int = 1) -> str:
    """
    Retrieve all required code context in a single call.

    This function must be called only once per user task. To ensure efficient and consistent reasoning:
    - Always batch all necessary `code_identifiers` into a single `getContext(...)` call.
    - Never issue multiple `getContext` calls for the same request unless new, unresolved symbols are introduced.

    Arguments:
        code_identifiers (List[str]):
            A list of dot- or slash-form identifiers to retrieve, e.g.:
            - 'package.module.Class.method'
            - 'tests/module/TestClass/test_method'
            - 'src/module.py'
            Use full paths and correct casing. Prefer batching for performance and cross-reference resolution.

        context_depth (int):
            Controls how deeply to follow references:
            - 0: Only the specified symbol(s)
            - 1: + Direct references (default)
            - 2+: + Recursive references

    Returns:
        str: Formatted, syntax-highlighted code context, including:
            - Declarations
            - Imports
            - Related symbols

    Guidelines:
    - Use `getRepoTree(show_contents=True)` to discover identifiers.
    - Identifiers are case-sensitive and repo-relative.
    - Always use forward slashes in file paths.
    - For property setters, use the `@property.setter` syntax.

    Reminder:
    → Only one `getCodeContext` call is allowed per user task. Collect all symbols beforehand.
    """

    tide = await initCodeTide()
    context = tide.get(code_identifiers, context_depth, as_string=True)
    return context if context else f"{code_identifiers} are not valid code_identifiers, refer to the getRepoTree tool to get a sense of the correct identifiers"