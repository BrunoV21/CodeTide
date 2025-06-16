from codetide import CodeTide
from codetide.core.common import writeFile
from dotenv import load_dotenv
import asyncio
import time
import os

async def main():
    st = time.time()
    # tide = await CodeTide.from_path(os.getenv("CODETIDE_REPO_PATH"))
    # tide.serialize()

    tide = CodeTide.deserialize(rootpath=os.getenv("CODETIDE_REPO_PATH"))
    tide.serialize(include_cached_ids=True)
    tide.codebase._build_cached_elements()
    await tide.check_for_updates(include_cached_ids=True)
    output = tide.get(["codetide.parsers.python_parser.PythonParser"], degree=1, as_string=True)

    writeFile(output, "./storage/context.txt")
    print(f"took {time.time()-st:.2f}s")
    # print(output)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())