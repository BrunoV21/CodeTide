from codetide.search.code_search import SmartCodeSearch
from codetide import CodeTide
import os

FILE_TEMPLATE = """{FILENAME}

{CONTENT}
"""

async def main():
    tide = await CodeTide.from_path(os.getenv("CODETIDE_REPO_PATH"))
    search = SmartCodeSearch(
        documents={
            codefile.file_path: codefile.file_path 
            # FILE_TEMPLATE.format(CONTENT=codefile.raw, FILENAME=codefile.file_path)
            for codefile in tide.codebase.root
        },
    )
    await search.initialize_async()
    search_queries = ["Add me a smooth transition effect to the expansor in ReasoningMessage.jsx"]

    for query in search_queries:
        print(f"\n--- Searching for: '{query}' ---")
        results = await search.search_smart(query, top_k=5)
        
        for doc_key, score in results:
            print(f"  {score:.3f}: {doc_key}")

    searchV1 = SmartCodeSearch(
        documents={
            codefile.file_path: codefile.file_path 
            # FILE_TEMPLATE.format(CONTENT=codefile.raw, FILENAME=codefile.file_path)
            for codefile in tide.codebase.root
        }
    )
    await searchV1.initialize_async()
    search_queries = ["Add me a smooth transition effect to the expansor in ReasoningMessage.jsx"]

    for query in search_queries:
        print(f"\n--- Searching for: '{query}' ---")
        results = await searchV1.search_smart(query, top_k=5)
        
        for doc_key, score in results:
            print(f"  {score:.3f}: {doc_key}")

    nodes_dict = tide.codebase.compile_tree_nodes_dict()
    nodes_dict = {
        filepath: contents for filepath, elements in nodes_dict.items()
        if (contents := "\n".join([filepath] + elements).strip())
    }

    searchV2 = SmartCodeSearch(documents=nodes_dict)
    await searchV2.initialize_async()
    search_queries = ["Add me a smooth transition effect to the expansor in ReasoningMessage.jsx"]

    for query in search_queries:
        print(f"\n--- Searching for: '{query}' ---")
        results = await searchV2.search_smart(query, top_k=5)
        
        for doc_key, score in results:
            print(f"  {score:.3f}: {doc_key}")

    tide.codebase._build_tree_dict(filter_paths=[doc_key for doc_key, score in results])
    print(tide.codebase.get_tree_view(include_modules=True))


if __name__ == "__main__":
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    asyncio.run(main())


