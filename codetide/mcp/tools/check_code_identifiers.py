from ...autocomplete import AutoComplete
from ..utils import initCodeTide
# from ..server import codeTideMCPServer

from typing import List
import orjson

# @codeTideMCPServer.tool
# incorporated into get_code_context tool
async def checkCodeIdentifiers(code_identifiers: List[str]) -> str:
    """
    Validates code identifiers against cached repository entries and suggests corrections.

    ---

    STRICT USAGE FLOW:
        1. getRepoTree(show_contents=True, show_types=True)
        2. check_code_identifiers() [REQUIRED GATE]
        3. getCodeContext() ← Only after green validation

    ---

    Args:
        code_identifiers: List of identifiers in dot or slash notation, such as:
            - 'tests.module.TestClass.test_method'
            - 'package.module.Class.method_or_attr'
            - 'services.module.Service.execute'
            - 'package/module.py'

    Returns:
        List of dictionaries:
            - code_identifier (str): The identifier checked
            - is_valid (bool): True if valid
            - matching_identifiers (List[str]): Up to 5 similar entries if invalid

        Example:
        [
            {
                "code_identifier": "core.models.ImportStatement",
                "is_valid": True,
                "matching_identifiers": []
            },
            {
                "code_identifier": "core.models.ImportStatment",
                "is_valid": False,
                "matching_identifiers": [
                    "core.models.ImportStatement",
                    "core.models.FunctionStatement",
                    "core.models.ClassStatement"
                ]
            }
        ]

    Notes:
        - Identifiers are case-sensitive
        - Similarity ranked by relevance (fuzzy + sequence match)
        - Setters use @property.setter syntax
        - File paths must be forward slashed and repo-relative
        - Use getRepoTree() to explore valid identifiers
    """

    tide = await initCodeTide()
    
    # Initialize AutoComplete
    autocomplete = AutoComplete(tide.cached_ids)
    
    # Validate each code identifier
    results = []
    for code_id in code_identifiers:
        result = autocomplete.validate_code_identifier(code_id)
        results.append(result)
    
    return str(orjson.dumps(results, option=orjson.OPT_INDENT_2))