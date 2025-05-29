from codetide import CodeTide
from codetide.core.common import writeFile
from dotenv import load_dotenv
import asyncio
import os

async def main():
    tide = await CodeTide.from_path(os.getenv("AICORE_REPO_PATH"))
    tide.serialize()

    print(tide.codebase.get_tree_view(include_modules=True))

    tide.codebase._build_cached_elements()
    output = tide.codebase.get(["aicore.llm.llm.Llm.acomplete", "aicore.llm.providers.base_provider.LlmBaseProvider.acomplete"], degree=1, as_string=True)

    writeFile(output, "./storage/context.txt")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
