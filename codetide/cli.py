from codetide.core.defaults import DEFAULT_SERIALIZATION_PATH, DEFAULT_ENCODING
from codetide import CodeTide

from pathlib import Path
import argparse
import asyncio
import time

def safe_print(string :str):
    try:
        # First try printing directly
        print(string)
    except (UnicodeEncodeError, UnicodeError):
        try:
            # Try with UTF-8 encoding
            import sys
            if sys.stdout.encoding != DEFAULT_ENCODING:
                sys.stdout.reconfigure(encoding=DEFAULT_ENCODING)  # Python 3.7+
            print(string)
        except Exception:
            # Fallback to ASCII-safe output
            print(string.encode('ascii', 'replace').decode('ascii'))

async def init_project(args, force_build: bool = False, flush: bool = False) -> CodeTide:
    storagePath = Path(args.project_path) / DEFAULT_SERIALIZATION_PATH
    try:
        if force_build:
            raise FileNotFoundError()
        
        tide = CodeTide.deserialize(storagePath)
        await tide.check_for_updates(serialize=True, include_cached_ids=True)
        if flush:
            safe_print(f"[INIT] Initialized from cache: {storagePath}")
    
    except FileNotFoundError:
        st = time.time()
        tide = await CodeTide.from_path(rootpath=args.project_path)
        tide.serialize(storagePath, include_cached_ids=True)
        if flush:
            safe_print(f"[INIT] Fresh parse of {args.project_path}: {len(tide.codebase.root)} files in {time.time()-st:.2f}s")
    return tide

async def handle_get(args):
    tide = await init_project(args)
    result = tide.get(args.ids, context_depth=args.degree, as_string=True)
    if result:
        safe_print(result)
    else:
        safe_print(f"[GET] No matches found for {args.ids}")

async def handle_tree(args):
    tide = await init_project(args)
    result = tide.codebase.get_tree_view(args.include_modules, args.include_types)
    safe_print(result)

async def handle_reset(args):
    tide = await init_project(args)
    await tide._reset()
    tide.serialize(include_cached_ids=True)
    safe_print(f"reseted project in {args.project_path}")

def main():
    parser = argparse.ArgumentParser(description="CLI for VSCode Extension")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_project = subparsers.add_parser("project", help="Initialize project parser")
    parser_project.add_argument("project_path", help="Path to the current workspace/project")
    parser_project.set_defaults(func=init_project, force_build=True, flush=True)

    parser_get = subparsers.add_parser("get", help="Get one or more items by ID")
    parser_get.add_argument("project_path", help="Path to the current workspace/project")
    parser_get.add_argument("ids", nargs="+", help="List of item IDs to get")
    parser_get.add_argument("--degree", type=int, default=1, help="Depth of retrieval")
    parser_get.set_defaults(func=handle_get)

    parser_tree = subparsers.add_parser("tree", help="Get tree view of the codebase")
    parser_tree.add_argument("project_path", help="Path to the current workspace/project")
    parser_tree.add_argument("--include-modules", action="store_true", help="Include modules in tree view")
    parser_tree.add_argument("--include-types", action="store_true", help="Include types in tree view")
    parser_tree.set_defaults(func=handle_tree)

    parser_parse = subparsers.add_parser("refresh", help="Refresh a tide project by reseting it")
    parser_parse.add_argument("project_path", help="Path to the current workspace/project")
    parser_parse.set_defaults(func=handle_reset)

    args = parser.parse_args()
    asyncio.run(args.func(args))

if __name__ == "__main__":
    ### TODO if copy to clipboard  pass compact_mode = true to handle_get
   main()