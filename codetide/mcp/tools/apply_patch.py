from .patch_code import DiffError, file_exists, open_file, process_patch, remove_file, write_file
from ..server import codeTideMCPServer
from ..utils import initCodeTide

@codeTideMCPServer.tool
async def applyPatch(patch_text: str) -> str:
    """
    Apply structured patches to the filesystem.

    Patch Format:
    - Wrap in: *** Begin Patch ... *** End Patch
    - Supports: Add, Update, Delete, Move (via Update + Move to)

    Syntax:
    - Context lines: ' '
    - Removed lines: '-'
    - Added lines: '+'
    - Change blocks: start with '@@'
    - Use '*** End of File' to update file endings
    - Relative paths only

    Key Features:
    - Fuzzy matching, CRLF normalization
    - Multiple hunks per file
    - Atomic: all or nothing
    - Validates file existence (no overwrites on Add)

    Errors:
    - FileNotFoundError: missing file for Update/Delete
    - DiffError: bad format, context mismatch, or conflict
    - DiffError: Add/Move to already-existing file

    LLM Tips:
    1. Include 2-3 context lines around changes
    2. Preserve indentation/whitespace
    3. Prefer small, isolated patches
    4. Add full content for new files (with imports/defs)
    5. Ensure move destinations exist or are creatable

    Examples:
    # Add file
    *** Begin Patch
    *** Add File: new.py
    +print("Hello")
    *** End Patch

    # Update file
    *** Begin Patch
    *** Update File: main.py
    @@ def greet():
    -print("Hi")
    +print("Hello")
    *** End Patch

    # Delete file
    *** Begin Patch
    *** Delete File: old.py
    *** End Patch

    # Move with update
    *** Begin Patch
    *** Update File: a.py
    *** Move to: b.py
    @@ def f():
    -print("x")
    +print("y")
    *** End of File
    *** End Patch
    """

    try:
        print(f"{patch_text=}")
        result = process_patch(patch_text, open_file, write_file, remove_file, file_exists)
        _ = await initCodeTide()

    except DiffError as exc:
        result = f"Error applying patch:\n{exc}"
        raise exc

    except FileNotFoundError as exc:
        result = f"Error: File not found - {exc}"
        raise exc

    except Exception as exc:
        result = f"An unexpected error occurred: {exc}"
        raise exc

    return result