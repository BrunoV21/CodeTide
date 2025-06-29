from ..server import codeTideMCPServer
from ..utils import initCodeTide

@codeTideMCPServer.tool
async def getRepoTree(
    show_contents: bool,
    show_types: bool = False) -> str:
    """
    Generates a visual tree representation of the entire code repository structure.
    Useful for understanding the project layout and navigating between files.

    Args:
        show_contents: When True, includes classes/functions/variables within files (default: False)
        show_types: When True, prefixes items with type codes:
                   (F=function, V=variable, C=class, A=attribute, M=method) (default: False)

    Returns:
        A formatted ASCII tree string showing the repository structure with optional details.
        Example output:
        ├── src/
        │   ├── utils.py
        │   │   └── F helper_function
        │   └── main.py
        │       └── C MainClass
        └── tests/
            └── test_main.py

    Usage Example:
        - Basic structure: getRepoTree()
        - With contents: getRepoTree(show_contents=True)
        - With type markers: getRepoTree(show_types=True)
        - Full detail: getRepoTree(show_contents=True, show_types=True)
    """
    
    tide = await initCodeTide()
    result = tide.codebase.get_tree_view(
        include_modules=show_contents,
        include_types=show_types
    )
    return result