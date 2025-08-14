
from .models import DiffError, Patch, Commit, ActionType
from .parser import Parser, patch_to_commit
from ....core.common import writeFile

from typing import Dict, Optional, Tuple, List, Callable
import pathlib
import re
import os

BREAKLINE_TOKEN = "<n>"
MULTILINE_BREAKLINE_TOKEN = "<N>"

RAW_BREAKLINE_PER_FILE_TYPE = {
    ".md": r"\n",
    ".py": r"\n"
}

BREAKLINE_PER_FILE_TYPE = {
    ".md": "\n",
    ".py": "\n"
}

COMMENTS_PER_FILE_TYPE = {
    ".py": "#"
}

# --------------------------------------------------------------------------- #
#  User-facing API
# --------------------------------------------------------------------------- #
def text_to_patch(text: str, orig: Dict[str, str]) -> Tuple[Patch, int]:
    """High-level function to parse patch text against original file content."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(("@", "***")):
            if  line.startswith("@@") and lines[i+1].startswith("+"):
                lines.insert(i+1, line.replace("@@", ""))
            
            elif line.startswith("@") and not line.startswith("@@"):
                lines[i] = f" {line}"

            continue

        elif (line.startswith("---") and len(line)==3) or not line.startswith(("+", "-", " ", )):
            lines[i] = f" {line}"

        elif line.startswith(("+", "-")) and i < len(lines) and lines[i+1].startswith(" "):
            lines[i] = f" {line}"
    
    # print(f"\n\n{lines[-2:]=}")
    writeFile("\n".join(lines), "lines.txt")
    writeFile("\n".join(list(orig.values())), "orig.txt")

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

def handle_uneven_quotes_in_comments(text, comment_identifier="#"):
    """
    Process lines with comment identifiers to handle uneven quotes.
    If a line has uneven quotes after the comment identifier,
    replace the first quote found after the comment with a special token.
    """
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        if comment_identifier in line:
            # Find the position of the comment identifier
            comment_pos = line.find(comment_identifier)
            
            # Get the part after the comment identifier
            after_comment = line[comment_pos + len(comment_identifier):]
            
            # Count quotes in the part after comment
            single_quote_count = after_comment.count("'")
            double_quote_count = after_comment.count('"')
            
            # Check if either quote type has uneven count
            if single_quote_count % 2 == 1 or double_quote_count % 2 == 1:
                # Find the first quote after the comment identifier
                first_single = after_comment.find("'")
                first_double = after_comment.find('"')
                
                # Determine which quote comes first
                if first_single != -1 and (first_double == -1 or first_single < first_double):
                    # Single quote comes first
                    replacement_pos = comment_pos + len(comment_identifier) + first_single
                    line = line[:replacement_pos] + "**APOSTROPHE**" + line[replacement_pos + 1:]
                elif first_double != -1:
                    # Double quote comes first
                    replacement_pos = comment_pos + len(comment_identifier) + first_double
                    line = line[:replacement_pos] + "**QUOTE**" + line[replacement_pos + 1:]
        
        processed_lines.append(line)
    
    return '\n'.join(processed_lines)

def restore_special_quote_tokens(text):
    """
    Restore the special quote tokens back to their original characters.
    """
    return text.replace("**APOSTROPHE**", "'").replace("**QUOTE**", '"')

def replace_newlines_in_quotes_regex(text, breakline_token=BREAKLINE_TOKEN):
    """
    Alternative implementation using regex approach.
    Replace \n with breakline_token when found inside quote pairs on the same line.
    """
    def process_match(match):
        # Get the full match including quotes
        full_match = match.group(0)
        quote_char = full_match[0]
        content = full_match[1:-1]  # Content between quotes
        
        # Replace both \n and actual newlines with <n> in the content
        processed_content = content.replace('\\n', breakline_token).replace('\n', breakline_token)
        
        return quote_char + processed_content + quote_char
    
    # Regex pattern explanation:
    # (['"]) - Capture the opening quote (group 1)
    # (?: - Start non-capturing group
    #   \\. - Match escaped character (backslash followed by any char)
    #   | - OR
    #   [^\1] - Match any character that's not the same quote character
    # )* - Zero or more of the above
    # \1 - Match the same quote character that opened
    
    pattern = r'([\'"])((?:\\.|[^\1])*?)\1'
    
    return re.sub(pattern, process_match, text)

def replace_newline_in_quotes(text, token=BREAKLINE_TOKEN, escape_backslashes :bool=True, comments_symbol :Optional[bool]=False):
    
    if comments_symbol is not None:
        text = handle_uneven_quotes_in_comments(text, comments_symbol)

    triple_quote_placeholders = []
    
    # Find all triple-quoted strings (both ''' and """)
    triple_pattern = r'(""".*?"""|\'\'\'.*?\'\'\')'
    
    def store_triple_quote(match):
        placeholder = f"__TRIPLE_QUOTE_{len(triple_quote_placeholders)}__"
        triple_quote_placeholders.append(match.group(1))
        return placeholder
    
    # Temporarily replace triple quotes with placeholders
    result = re.sub(triple_pattern, store_triple_quote, text, flags=re.DOTALL)

    # result = text
    if escape_backslashes:
        result = result.replace("\\", "\\\\")
    result = replace_newlines_in_quotes_regex(result, token)
       
    # Restore the triple-quoted strings
    for i, triple_quote in enumerate(triple_quote_placeholders):
        placeholder = f"__TRIPLE_QUOTE_{i}__"
        result = result.replace(placeholder, triple_quote)

    if comments_symbol is not None:
        result = restore_special_quote_tokens(result)
    
    return result

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
    
    # FIX: Check for existence of files to be added before parsing.
    paths_to_add = identify_files_added(text)
    for p in paths_to_add:
        if exists_fn(p):
            raise DiffError(f"Add File Error - file already exists: {p}")

    paths_needed = identify_files_needed(text)
    # TODO prepare this to receive list of unique extensions in the future
    ext = [os.path.splitext(path)[1] for path in paths_needed][0]
    text = replace_newline_in_quotes(text, comments_symbol=COMMENTS_PER_FILE_TYPE.get(ext))

    # TODO cann add autocomplete with cached paths from tide here to validate if required
    orig_files = load_files(paths_needed, open_fn)
    
    patch, _fuzz = text_to_patch(text, orig_files)
    commit = patch_to_commit(patch, orig_files)
    
    apply_commit(commit, write_fn, remove_fn, exists_fn)
    return "Patch applied successfully."

# --------------------------------------------------------------------------- #
#  Default FS wrappers
# --------------------------------------------------------------------------- #
def open_file(path: str) -> str:    
    _, ext = os.path.splitext(path)
    with open(path, "rt", encoding="utf-8") as fh:
        return replace_newline_in_quotes(fh.read(), escape_backslashes=False, comments_symbol=COMMENTS_PER_FILE_TYPE.get(ext))

def write_file(path: str, content: str) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _, ext = os.path.splitext(target)
    with target.open("wt", encoding="utf-8", newline="\n") as fh:
        fh.write(content.replace(
            BREAKLINE_TOKEN, 
            RAW_BREAKLINE_PER_FILE_TYPE.get(ext, r"\n").replace(
                MULTILINE_BREAKLINE_TOKEN, BREAKLINE_PER_FILE_TYPE.get(ext, "\n")
            )
        ))


def remove_file(path: str) -> None:
    p = pathlib.Path(path)
    if p.exists():
        p.unlink()


def file_exists(path: str) -> bool:
    return pathlib.Path(path).exists()