import asyncio
from typing import List, Dict, Any
from codetide.mcp.server import codeTideMCPServer, initCodeTide
from codetide.search.code_search import SmartCodeSearch

@codeTideMCPServer.tool(
    name="searchCode",
    description="Perform a smart search over the codebase. Returns the most relevant code files and elements for a given query."
)
async def search_code_tool(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    INSTRUCTION FOR AGENT:
    Use this tool to perform a smart search over the codebase for any code-related query (e.g., function, class, or concept).
    - Call this tool with a natural language search query and (optionally) the number of top results to return (default: 10).
    - The tool will automatically initialize the codebase context.
    - It returns a list of the most relevant code elements, each as a dictionary with:
        - 'doc_key': the file path or identifier of the code element
        - 'score': the relevance score
        - 'context': a code snippet or summary for that result
    - Use this tool when you need to locate where a concept, function, or class is defined or discussed in the codebase.
    """
    tide = await initCodeTide()
    nodes_dict = tide.codebase.compile_tree_nodes_dict()
    documents = {
        filepath: "\n".join([filepath] + elements).strip()
        for filepath, elements in nodes_dict.items()
        if (elements and len(elements) > 0)
    }
    code_search = SmartCodeSearch(documents=documents)
    await code_search.initialize_async()
    results = await code_search.search_with_context(query, top_k=top_k)
    return results
