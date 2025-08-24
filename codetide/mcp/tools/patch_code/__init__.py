from .models import DiffError, Patch, Commit, ActionType
from ....core.defaults import DEFAULT_ENCODING
from .parser import Parser, patch_to_commit
# from ....core.common import writeFile

from typing import Dict, Tuple, List, Callable
import pathlib
import os

# --------------------------------------------------------------------------- #
#  User-facing API
# --------------------------------------------------------------------------- #
def text_to_patch(text: str, orig: Dict[str, str]) -> Tuple[Patch, int]:
    """Improved version with better splitlines handling."""
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if line.startswith(("@", "***")):
            if line.startswith("@@") and i + 1 < len(lines) and lines[i+1].startswith("+"):
                lines.insert(i+1, line.replace("@@", ""))
            elif line.startswith("@") and not line.startswith("@@"):
                lines[i] = f" {line}"
            continue

        elif (line.startswith("---") and len(line) == 3) or not line.startswith(("+", "-", " ")):
            lines[i] = f" {line}"

        elif line.startswith(("+", "-")) and i + 1 < len(lines) and lines[i+1].startswith(" "):
            lines[i] = f" {line}"
    
    # Debug output
    # writeFile("\n".join(lines), "lines_processed.txt")
    # writeFile("\n".join(list(orig.values())), "lines_orig.txt")

    if not lines or not Parser._norm(lines[0]).startswith("*** Begin Patch"):
        raise DiffError(f"Invalid patch text - must start with '*** Begin Patch'. Found: '{lines[0] if lines else 'empty'}'")
    if not lines or not Parser._norm(lines[-1]) == "*** End Patch":
        raise DiffError(f"Invalid patch text - must end with '*** End Patch'. Found: '{lines[-1] if lines else 'empty'}'")

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

def process_patch(
    patch_path: str,
    open_fn: Callable[[str], str],
    write_fn: Callable[[str, str], None],
    remove_fn: Callable[[str], None],
    exists_fn: Callable[[str], bool]
) -> List[str]:
    """The main entrypoint function to process a patch from text to filesystem."""
    if not os.path.exists(patch_path):
        raise DiffError("Patch path {patch_path} does not exist.")
    
    # Normalize line endings before processing
    text = open_fn(patch_path)
    
    # FIX: Check for existence of files to be added before parsing.
    paths_to_add = identify_files_added(text)
    for p in paths_to_add:
        if exists_fn(p):
            raise DiffError(f"Add File Error - file already exists: {p}")

    paths_needed = identify_files_needed(text)

    # Load files with normalized line endings
    orig_files = {}
    for path in paths_needed:
        orig_files[path] = open_fn(path)
    
    patch, _fuzz = text_to_patch(text, orig_files)
    commit = patch_to_commit(patch, orig_files)
    
    apply_commit(commit, write_fn, remove_fn, exists_fn)

    remove_fn(patch_path)
    return paths_needed

# --------------------------------------------------------------------------- #
#  Default FS wrappers
# --------------------------------------------------------------------------- #
def open_file(path: str) -> str:    
    _, ext = os.path.splitext(path)
    with open(path, "rt", encoding=DEFAULT_ENCODING) as fh:
        return fh.read()

def write_file(path: str, content: str) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wt", encoding=DEFAULT_ENCODING, newline="\n") as fh:
        fh.write(content)

def remove_file(path: str) -> None:
    p = pathlib.Path(path)
    if p.exists():
        p.unlink()


def file_exists(path: str) -> bool:
    return pathlib.Path(path).exists()