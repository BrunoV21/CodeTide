from .models import DiffError, Patch, Commit, ActionType
from ....core.defaults import DEFAULT_ENCODING
from .parser import Parser, patch_to_commit
# from ....core.common import writeFile

from typing import Dict, Optional, Tuple, List, Callable, Union
import pathlib
import re
import os

def parse_patch_blocks(text: str, multiple: bool = True) -> Union[str, List[str], None]:
    """
    Extract content between *** Begin Patch and *** End Patch markers (inclusive),
    ensuring that both markers are at zero indentation (start of line, no leading spaces).
    
    If only one identifier is present:
    - If only "Begin Patch" exists: returns from Begin Patch to end of text
    - If only "End Patch" exists: returns from start of text to End Patch

    Args:
        text: Full input text containing one or more patch blocks.
        multiple: If True, return a list of all patch blocks. If False, return the first match.

    Returns:
        A string (single patch), list of strings (multiple patches), or None if not found.
    """
    
    # First, try to find complete blocks (both Begin and End markers)
    complete_pattern = r"(?m)^(\*\*\* Begin Patch[\s\S]*?^\*\*\* End Patch)$"
    complete_matches = re.findall(complete_pattern, text)
    
    # If we found complete matches, return them (preserving original behavior)
    if complete_matches:
        return complete_matches if multiple else complete_matches[0]
    
    # If no complete matches, look for partial identifiers
    begin_pattern = r"(?m)^(\*\*\* Begin Patch).*$"
    end_pattern = r"(?m)^(\*\*\* End Patch).*$"
    
    begin_matches = list(re.finditer(begin_pattern, text))
    end_matches = list(re.finditer(end_pattern, text))
    
    partial_matches = []
    
    # Handle cases with only Begin markers (from Begin to end of text)
    if begin_matches and not end_matches:
        for match in begin_matches:
            start_pos = match.start()
            partial_content = text[start_pos:]
            partial_matches.append(partial_content)
    
    # Handle cases with only End markers (from start of text to End)
    elif end_matches and not begin_matches:
        for match in end_matches:
            end_pos = match.end()
            partial_content = text[:end_pos]
            partial_matches.append(partial_content)
    
    # Handle mixed cases (some begins without ends, some ends without begins)
    elif begin_matches or end_matches:
        # Get all Begin positions
        begin_positions = [m.start() for m in begin_matches]
        end_positions = [m.end() for m in end_matches]
        
        # For each Begin, try to find corresponding End
        for begin_pos in begin_positions:
            corresponding_end = None
            for end_pos in end_positions:
                if end_pos > begin_pos:
                    corresponding_end = end_pos
                    break
            
            if corresponding_end:
                # Complete pair found
                partial_content = text[begin_pos:corresponding_end]
            else:
                # Begin without End - go to end of text
                partial_content = text[begin_pos:]
            
            partial_matches.append(partial_content)
        
        # Handle orphaned End markers (Ends that don't have corresponding Begins)
        for end_pos in end_positions:
            has_corresponding_begin = any(begin_pos < end_pos for begin_pos in begin_positions)
            if not has_corresponding_begin:
                # End without Begin - from start of text
                partial_content = text[:end_pos]
                partial_matches.append(partial_content)
    
    if not partial_matches:
        return None
    
    return partial_matches if multiple else partial_matches[0]

# --------------------------------------------------------------------------- #
#  User-facing API
# --------------------------------------------------------------------------- #
def text_to_patch(text: str, orig: Dict[str, str], rootpath: Optional[pathlib.Path]=None) -> Tuple[Patch, int]:
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

        elif line.startswith(("+", "-")) and 1 < i + 1 < len(lines) and lines[i+1].startswith(" ") and not lines[i-1].startswith(("+", "-")) and lines[i+1].strip():
            lines[i] = f" {line}"
    
    # Debug output
    # writeFile("\n".join(lines), "lines_processed.txt")
    # writeFile("\n".join(list(orig.values())), "lines_orig.txt")

    if not lines or not Parser._norm(lines[0]).startswith("*** Begin Patch"):
        raise DiffError(f"Invalid patch text - must start with '*** Begin Patch'. Found: '{lines[0] if lines else 'empty'}'")
    if not lines or not Parser._norm(lines[-1]) == "*** End Patch":
        raise DiffError(f"Invalid patch text - must end with '*** End Patch'. Found: '{lines[-1] if lines else 'empty'}'")

    parser = Parser(current_files=orig, lines=lines, index=1, rootpath=rootpath)
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
    exists_fn: Callable[[str], bool],
    root_path: Optional[Union[str, pathlib.Path]]=None
) -> List[str]:
    """The main entrypoint function to process a patch from text to filesystem."""
    if not os.path.exists(patch_path):
        raise DiffError("Patch path {patch_path} does not exist.")
    
    ### TODO might need to update this to process multiple patches in line
    
    if root_path is not None:
        root_path = pathlib.Path(root_path)
    
    # Normalize line endings before processing
    patches_text = open_fn(patch_path)
    print(f"{patches_text=}")
    patches = parse_patch_blocks(patches_text)#or [""]
    print(f"{patches=}")

    all_paths_needed = []
    for text in patches:
        # FIX: Check for existence of files to be added before parsing.
        paths_to_add = identify_files_added(text)
        for p in paths_to_add:
            if root_path is not None:
                p = str(root_path / p)
            if exists_fn(p):
                raise DiffError(f"Add File Error - file already exists: {p}")

        paths_needed = identify_files_needed(text)
        all_paths_needed.extend(paths_to_add)
        all_paths_needed.extend(paths_needed)

        # Load files with normalized line endings
        orig_files = {}
        for path in paths_needed:
            if root_path is not None:
                path = str(root_path / path)
            orig_files[path] = open_fn(path)
        
        patch, _fuzz = text_to_patch(text, orig_files, rootpath=root_path)
        commit = patch_to_commit(patch, orig_files)
        
        apply_commit(commit, write_fn, remove_fn, exists_fn)

        remove_fn(patch_path)

    return all_paths_needed

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