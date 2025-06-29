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
        code_identifiers: One or more unique code element IDs or file paths to get context for.
                         Examples: 'my_module.ClassName', 'path/to/file.py', ['mod.func1', 'mod.func2']
        context_depth: How many levels of related references to include (1=direct references only)

    Returns:
        Formatted string containing the requested code context with surrounding relevant code,
        or None if identifiers don't exist.
    """

    tide = await initCodeTide()
    context = await tide.get(code_identifiers, context_depth, as_string=True)
    return context