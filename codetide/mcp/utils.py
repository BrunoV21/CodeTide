from ..core.defaults import DEFAULT_SERIALIZATION_PATH
from codetide import CodeTide

from typing import Optional
from pathlib import Path
import time
import os

def getWorkspace()->Path:
    """Retrieves and validates the workspace path from CODETIDE_WORKSPACE environment variable."""

    workspace = os.getenv("CODETIDE_WORKSPACE")
    if not workspace:
        raise EnvironmentError("codeTideMCPServer requires `CODETIDE_WORKSPACE` env var to be set to your project working directory")
    
    return Path(workspace)

def safe_print(string :str):
    """Prints string with multiple fallback encodings to handle Unicode errors gracefully."""

    try:
        # First try printing directly
        print(string)
    except (UnicodeEncodeError, UnicodeError):
        try:
            # Try with UTF-8 encoding
            import sys
            if sys.stdout.encoding != 'utf-8':
                sys.stdout.reconfigure(encoding='utf-8')  # Python 3.7+
            print(string)
        except Exception:
            # Fallback to ASCII-safe output
            print(string.encode('ascii', 'replace').decode('ascii'))

async def initCodeTide(force_build: bool = False, flush: bool = False, workspace :Optional[Path]=None)->CodeTide:
    """Initializes CodeTide instance either from cache or fresh parse, with serialization options."""
    
    if not workspace:
        workspace = getWorkspace()
    
    storagePath =  workspace / DEFAULT_SERIALIZATION_PATH
    try:
        if force_build:
            raise FileNotFoundError()
        
        tide = CodeTide.deserialize(storagePath)
        await tide.check_for_updates(serialize=True, include_cached_ids=True)
        if flush:
            safe_print(f"[INIT] Initialized from cache: {storagePath}")
    
    except FileNotFoundError:
        st = time.time()
        tide = await CodeTide.from_path(rootpath=workspace)
        tide.serialize(storagePath, include_cached_ids=True)
        if flush:
            safe_print(f"[INIT] Fresh parse of {workspace}: {len(tide.codebase.root)} files in {time.time()-st:.2f}s")
    return tide