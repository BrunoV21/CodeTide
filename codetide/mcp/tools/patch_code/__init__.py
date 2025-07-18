from .models import DiffError, Patch, Commit, ActionType
from .parser import Parser, patch_to_commit

from typing import Dict, Tuple, List, Callable
import pathlib
import re
import os

BREAKLINE_TOKEN = "<n>"

BREAKLINE_PER_FILE_TYPE = {
    ".md": "\n",
    ".py": r"\n"
}

# --------------------------------------------------------------------------- #
#  User-facing API
# --------------------------------------------------------------------------- #
def text_to_patch(text: str, orig: Dict[str, str]) -> Tuple[Patch, int]:
    """High-level function to parse patch text against original file content."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(("@", "***")):
            continue

        elif line.startswith("---") or not line.startswith(("+", "-", " ")):
            lines[i] = f" {line}"
    
    # print(f"\n\n{lines[-2:]=}")

    if not lines or not Parser._norm(lines[0]).startswith("*** Begin Patch"):
        raise DiffError("Invalid patch text - must start with '*** Begin Patch'.")
    if not Parser._norm(lines[-1]) == "*** End Patch":
        raise DiffError("Invalid patch text - must end with '*** End Patch'.")

    parser = Parser(current_files=orig, lines=lines, index=1)
    parser.parse()
    return parser.patch, parser.fuzz


def identify_files_needed(text: str) -> List[str]:
    """Scans patch text to find which files need to be read."""
    lines = text.splitlines()
    files = []
    for line in lines:
        norm_line = Parser._norm(line)
        if norm_line.startswith("*** Update File: "):
            files.append(line[len("*** Update File: ") :])
        elif norm_line.startswith("*** Delete File: "):
            files.append(line[len("*** Delete File: ") :])
    return files


def identify_files_added(text: str) -> List[str]:
    """Scans patch text to find which files will be created."""
    lines = text.splitlines()
    return [
        line[len("*** Add File: ") :]
        for line in lines
        if Parser._norm(line).startswith("*** Add File: ")
    ]


# --------------------------------------------------------------------------- #
#  File-system I/O
# --------------------------------------------------------------------------- #
def load_files(paths: List[str], open_fn: Callable[[str], str]) -> Dict[str, str]:
    """Loads a list of files into a dictionary."""
    return {path: open_fn(path) for path in paths}


def apply_commit(
    commit: Commit,
    write_fn: Callable[[str, str], None],
    remove_fn: Callable[[str], None],
    exists_fn: Callable[[str], bool]
) -> None:
    """Applies a commit to a filesystem using provided I/O functions."""
    # Check for move/rename collisions before applying any changes
    for path, change in commit.changes.items():
        if change.move_path and exists_fn(change.move_path):
            if not commit.changes.get(change.move_path, None):
                 raise DiffError(f"Cannot move '{path}' to '{change.move_path}' because the target file already exists.")

    for path, change in commit.changes.items():
        if change.type is ActionType.DELETE:
            remove_fn(path)
        elif change.type is ActionType.ADD:
            if change.new_content is None:
                raise DiffError(f"ADD change for '{path}' has no content")
            write_fn(path, change.new_content)
        elif change.type is ActionType.UPDATE:
            if change.new_content is None:
                raise DiffError(f"UPDATE change for '{path}' has no new content")
            
            target_path = change.move_path or path
            write_fn(target_path, change.new_content)
            
            if change.move_path and target_path != path:
                remove_fn(path)

def replace_newline_in_quotes(text, token=BREAKLINE_TOKEN):
    pattern = r'''
        (?<!['"])      # Negative lookbehind: avoid triple quotes
        (['"])         # Group 1: single or double quote
        (              # Group 2: content inside the quote
            (?:        # non-capturing group
                \\\1   # escaped quote like \' or \"
                |      # or
                (?!\1).  # any char that's not the same quote
            )*?
        )
        \1             # Closing quote, must match opening
        (?!\1)         # Negative lookahead: avoid triple quotes
    '''

    def replacer(match):
        quote = match.group(1)
        content = match.group(2)
        # Replace both literal \n and actual newlines
        replaced = content.replace(r'\n', token).replace('\n', token)
        return f'{quote}{replaced}{quote}'

    return re.sub(pattern, replacer, text, flags=re.VERBOSE | re.DOTALL)

def process_patch(
    text: str,
    open_fn: Callable[[str], str],
    write_fn: Callable[[str, str], None],
    remove_fn: Callable[[str], None],
    exists_fn: Callable[[str], bool]
) -> str:
    """The main entrypoint function to process a patch from text to filesystem."""
    if not text.strip():
        raise DiffError("Patch text is empty.")
    
    text = replace_newline_in_quotes(text)
    # FIX: Check for existence of files to be added before parsing.
    paths_to_add = identify_files_added(text)
    for p in paths_to_add:
        if exists_fn(p):
            raise DiffError(f"Add File Error - file already exists: {p}")

    paths_needed = identify_files_needed(text)
    orig_files = load_files(paths_needed, open_fn)
    
    patch, _fuzz = text_to_patch(text, orig_files)
    commit = patch_to_commit(patch, orig_files)
    
    apply_commit(commit, write_fn, remove_fn, exists_fn)
    return "Patch applied successfully."

# --------------------------------------------------------------------------- #
#  Default FS wrappers
# --------------------------------------------------------------------------- #
def open_file(path: str) -> str:
    with open(path, "rt", encoding="utf-8") as fh:
        return replace_newline_in_quotes(fh.read())


def write_file(path: str, content: str) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _, ext = os.path.splitext(target)
    with target.open("wt", encoding="utf-8", newline="\n") as fh:
        fh.write(content.replace(BREAKLINE_TOKEN, BREAKLINE_PER_FILE_TYPE.get(ext, r"\n")))


def remove_file(path: str) -> None:
    p = pathlib.Path(path)
    if p.exists():
        p.unlink()


def file_exists(path: str) -> bool:
    return pathlib.Path(path).exists()