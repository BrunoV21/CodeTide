from .patch_code import DiffError, file_exists, open_file, process_patch, remove_file, write_file
from ..server import codeTideMCPServer
from ...core.common import writeFile
from ..utils import initCodeTide

from ulid import ulid
import os

@codeTideMCPServer.tool
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
    - leading modifiers (e.g., `async`, `@staticmethod`, etc.)
    - indentation and whitespace
    - line endings
    - Include **only what changed**, and minimal surrounding context to anchor the diff.
    - Use **complete `@@` hunk headers**, exactly matching the **entire first line** of the block being changed.
    - If the block is a function or method, the `@@` header must include all modifiers (e.g., `async def`, `@classmethod def`, etc.) and match the original line exactly.

    ### YOU MUST NOT:
    - Truncate or invent function headers in `@@` lines.
    - Include extra unchanged code beyond the diff area.
    - Guess or partially reconstruct lines — **copy the original exactly**.
    - Leave `@@` headers incomplete (this will cause the patch to fail).
    - Include unrelated changes in the same patch block.

    ---

    ## GOOD PATCH EXAMPLE

    ```diff
    *** Begin Patch
    *** Update File: app/utils/io.py
    @@ async def fetch_data(session, url):
    async def fetch_data(session, url):
    -    async with session.get(url) as resp:
    +    async with session.get(url, timeout=10) as resp:
    *** End Patch
    ````

    This is correct because:

    * The `@@` header includes the full original line, including the `async` modifier.
    * Only the changed line is included.
    * No extra or unrelated code is added.

    ---

    ## BAD PATCH EXAMPLES

    ### Missing modifier in `@@` header

    ```diff
    @@ def fetch_data(session, url):
    ```

    Incorrect — the original line starts with `async def`. The `@@` header must match exactly:

    ```diff
    @@ async def fetch_data(session, url):
    ```

    ---

    ### Truncated `@@` header

    ```diff
    @@ def process_node(cls, node):
    ```

    Incorrect — this is only part of the signature. You must include the full original line:

    ```diff
    @@ def process_node(cls, node: Node, code: bytes, file: CodeFileModel, flag: bool=False):
    ```

    ---

    ### Extra unchanged lines

    ```diff
    @@ def run():
    def run():
    -    result = old()
    +    result = new()
        return result
    ```

    Incorrect — `return result` is unchanged and should not appear. Correct:

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
    @@ full, original line from code block
    context line (unchanged, prefix: space)
    - line being deleted
    + line being added
    *** End Patch
    ```

    * The `@@` line must match the **entire first line of the block**, including any modifiers like `async`.
    * Do not shorten, guess, or reformat the line — copy it exactly from the original.

    ---

    ## FINAL REMINDERS

    * Only generate diffs against the file's original content.
    * Avoid including unrelated or unchanged code.
    * Match indentation, whitespace, and modifiers exactly.
    * Keep each patch as small, accurate, and focused as possible.
    * One logical change per patch.
    """

    patch_path = f"./storage/{ulid()}.txt"
    try:
        patch_text = patch_text.replace("\'", "'")
        patch_text = patch_text.replace('\"', '"')
        writeFile(patch_text, patch_path)
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

    if "exc" not in locals():
        os.remove(patch_path)

    return result