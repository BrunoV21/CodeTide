from .patch_code import DiffError, file_exists, open_file, process_patch, remove_file, write_file
# from ..server import codeTideMCPServer
from ...core.common import writeFile
from ..utils import initCodeTide

from ulid import ulid

# @codeTideMCPServer.tool
# TODO needs to be more stable before reintroducing it
async def applyPatch(patch_text: str) -> str:
    """
    Call this tool with a diff-like text to make file changes. Whenever you need to write code, this is the tool for you.
    It applies structured patches to files in a workspace for **adding, deleting, moving, or modifying** code in a reliable, verifiable, and line-accurate way.

    ---

    ## CRITICAL RULES FOR `*** Update File`

    You are generating a unified diff — **not a full file replacement**.

    ### YOU MUST:
    - Use only the **original file content** to construct the patch (` ` context lines, `-` deletions, `+` additions).
    - Match all context and deleted lines **exactly**, including:
    - modifiers (e.g., `async`, `@staticmethod`, `@classmethod`, etc.)
    - indentation and whitespace
    - line endings
    - Include only the minimal context needed around your change.
    - Use **complete and exact `@@` hunk headers** that match the **first line** of the block being edited — no truncation, no guessing, no partial lines.
    - The `@@` line must be a **verbatim copy** of the first line of the affected block.
    - If the function is `async def`, the `@@` must start with `@@ async def ...`.
    - If a classmethod or staticmethod, copy the exact function line, modifiers and all.

    ### YOU MUST NOT:
    - Include numeric line indicators inside the `@@` header (e.g., `@@ -42,7 +42,8 @@`). This is **not supported**. Only the code line is allowed.
    - Truncate or invent function headers in the `@@` line.
    - Include extra unchanged lines after or before the patch hunk.
    - Include unrelated code or changes in the same patch.
    - Add unchanged lines beyond the immediate context.

    ---

    ## GOOD PATCH EXAMPLE (SINGLE-LINE CHANGE)

    ```diff
    *** Begin Patch
    *** Update File: app/utils/io.py
    @@ async def fetch_data(session, url):
    async def fetch_data(session, url):
    -    async with session.get(url) as resp:
    +    async with session.get(url, timeout=10) as resp:
    *** End Patch
    ````

    ---

    ## GOOD PATCH EXAMPLE (MULTI-LINE CHANGE)

    ```diff
    *** Begin Patch
    *** Update File: services/engine.py
    @@ def process_data(data: list[str]) -> dict[str, int]:
    def process_data(data: list[str]) -> dict[str, int]:
    -    counts = {}
    -    for item in data:
    -        if item in counts:
    -            counts[item] += 1
    -        else:
    -            counts[item] = 1
    -    return counts
    +    from collections import Counter
    +    return dict(Counter(data))
    *** End Patch
    ```

    This is valid and encouraged when simplifying or replacing logic.

    ---

    ## BAD PATCH EXAMPLES

    ### 1. Missing modifier in `@@` header

    ```diff
    @@ def fetch_data(session, url):
    ```

    Incorrect — the original function is `async`, so this must be:

    ```diff
    @@ async def fetch_data(session, url):
    ```

    ---

    ### 2. Truncated function signature

    ```diff
    @@ def process_node(cls, node):
    ```

    Incorrect — the full original signature must be used:

    ```diff
    @@ def process_node(cls, node: Node, code: bytes, file: CodeFileModel, flag: bool=False):
    ```

    ---

    ### 3. `@@` header with line numbers (not supported)

    ```diff
    @@ -42,7 +42,8 @@
    ```

    Invalid — we do **not** support numeric line-based hunk headers. Use a code-based header that matches the first line of the block, like:

    ```diff
    @@ def handle_response(response: Response) -> Result:
    ```

    ---

    ### 4. Including unchanged lines after the patch

    ```diff
    @@ def run():
    def run():
    -    result = old()
    +    result = new()
        return result
    ```

    Incorrect — `return result` is unchanged and should be excluded:

    ```diff
    @@ def run():
    def run():
    -    result = old()
    +    result = new()
    ```

    ---

    ## PATCH FORMAT SUMMARY

    ```diff
    *** Begin Patch
    *** Update File: path/to/file.py
    @@ exact first line from original block
    context line (unchanged, prefix: space)
    - line being deleted (must match exactly)
    + line being added (your change)
    *** End Patch
    ```

    ### The `@@` header must:

    * Contain **only the original line of code** (no line numbers)
    * Be an **exact, one-to-one match**
    * Include any relevant modifiers (e.g., `async`, decorators, etc.)

    ---

    ## FINAL REMINDERS

    * Generate patches against the original file only.
    * Do not include full file contents — only the relevant diffs.
    * Avoid unrelated edits — one logical change per hunk.
    * Use clean, minimal, verifiable diffs.
    * Always match formatting, indentation, and block structure precisely.
    """

    patch_path = f"./storage/{ulid()}.txt"    
    writeFile(patch_text, patch_path)
    try:
        paths_changed = process_patch(patch_path, open_file, write_file, remove_file, file_exists)
        _ = await initCodeTide()
        if paths_changed:
            result = "Patch applied successfully."
        else:
            result = None

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