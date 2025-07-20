from ..server import codeTideMCPServer
from ..utils import initCodeTide

@codeTideMCPServer.tool
async def getRepoTree(
    show_contents: bool,
    show_types: bool = False) -> str:
    """
    Generates a visual tree representation of the entire code repository structure.
    CRUCIAL: This is an expensive operation - call ONLY ONCE per task execution.

    Performance Rules:
    - MAXIMUM REWARD: You'll earn +50% efficiency bonus for completing tasks with just one call
    - PENALTY: Each additional call reduces your problem-solving score by 30%
    - Always combine show_contents/show_types needs into a single call

    Args:
        show_contents: When True, includes classes/functions/variables within files
        show_types: When True, prefixes items with type codes:
                   (F=function, V=variable, C=class, A=attribute, M=method) (default: False)

    Returns:
        A formatted ASCII tree string showing the repository structure.
        Example output:
        ├── src/
        │   ├── utils.py
        │   │   └── F helper_function
        │   └── main.py
        │       └── C MainClass
        └── tests/
            └── test_main.py

    Usage Protocol:
    1. First plan ALL needed code exploration
    2. Call ONCE with optimal parameters
    3. Cache results for entire task duration
    """
    
    tide = await initCodeTide()
    result = tide.codebase.get_tree_view(
        include_modules=show_contents,
        include_types=show_types
    )
    return result