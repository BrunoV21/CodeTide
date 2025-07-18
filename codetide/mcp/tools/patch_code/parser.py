from .models import Patch, DiffError, PatchAction, ActionType,  FileChange, Commit, Chunk

from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
#  Helper functions for parsing update chunks
# --------------------------------------------------------------------------- #
def find_context_core(
    lines: List[str], context: List[str], start: int
) -> Tuple[int, int]:
    """Core fuzzy matching logic."""
    if not context:
        return start, 0

    # Exact match
    for i in range(start, len(lines) - len(context) + 1):
        if lines[i : i + len(context)] == context:
            return i, 0
            
    # Match ignoring trailing whitespace
    norm_context = [s.rstrip() for s in context]
    for i in range(start, len(lines) - len(context) + 1):
        if [s.rstrip() for s in lines[i : i + len(context)]] == norm_context:
            return i, 1
            
    # Match ignoring all leading/trailing whitespace
    strip_context = [s.strip() for s in context]
    for i in range(start, len(lines) - len(context) + 1):
        if [s.strip() for s in lines[i : i + len(context)]] == strip_context:
            return i, 100
            
    return -1, 0


def find_context(
    lines: List[str], context: List[str], start: int, eof: bool
) -> Tuple[int, int]:
    """Finds the location of a context block, allowing for fuzziness."""
    # if eof and context:
    #     end_start_idx = len(lines) - len(context)
    #     if end_start_idx >= 0:
    #         new_index, fuzz = find_context_core(lines, context, end_start_idx)
    #         if new_index == end_start_idx:
    #             return new_index, fuzz
    #     return -1, 0
        
    return find_context_core(lines, context, start)


def peek_next_section(
    lines: List[str], index: int
) -> Tuple[List[str], List[Chunk], int, bool]:
    """
    Scans a block of changes within an 'Update File' section.
    """
    context_lines: List[str] = []
    del_lines: List[str] = []
    ins_lines: List[str] = []
    chunks: List[Chunk] = []
    mode = "keep"
    pending_keep_lines: List[str] = []  # Buffer for keep lines that might be at the end
    has_had_changes = False  # Track if we've seen any add/delete operations

    while index < len(lines):
        norm_s = Parser._norm(lines[index])
        if norm_s.startswith(
            (
                "@@",
                "*** End Patch",
                "*** Update File:",
                "*** Delete File:",
                "*** Add File:",
                "*** End of File",
            )
        ):
            break

        s = lines[index]
        index += 1
        
        last_mode = mode
        prefix = s[0] if s else ' '
        
        if prefix == "+":
            mode = "add"
        elif prefix == "-":
            mode = "delete"
        elif prefix == " ":
            mode = "keep"
        else:
            raise DiffError(f"Invalid line in update section (must start with '+', '-', or ' '): {s}")
        
        content = s[1:]

        if mode == "keep" and last_mode != "keep":
            if ins_lines or del_lines:
                chunks.append(
                    Chunk(
                        orig_index=len(context_lines) - len(del_lines),
                        del_lines=del_lines,
                        ins_lines=ins_lines,
                    )
                )
            del_lines, ins_lines = [], []

        if mode == "delete":
            has_had_changes = True
            # Add any pending keep lines before processing delete lines
            if pending_keep_lines:
                context_lines.extend(pending_keep_lines)
                pending_keep_lines = []
            
            del_lines.append(content)
            context_lines.append(content)
        elif mode == "add":
            has_had_changes = True
            # Add any pending keep lines before processing add lines
            if pending_keep_lines:
                context_lines.extend(pending_keep_lines)
                pending_keep_lines = []
            
            ins_lines.append(content)
        elif mode == "keep":
            if has_had_changes:
                # We've seen changes, so these keep lines could be trailing context
                # Buffer them in case they're the final block
                pending_keep_lines.append(content)
            else:
                # No changes seen yet, so these are leading context - add them directly
                context_lines.append(content)

    if ins_lines or del_lines:
        # There are pending changes, so add any pending keep lines as they're part of the context
        if pending_keep_lines:
            context_lines.extend(pending_keep_lines)
            pending_keep_lines = []
        
        chunks.append(
            Chunk(
                orig_index=len(context_lines) - len(del_lines),
                del_lines=del_lines,
                ins_lines=ins_lines,
            )
        )
    
    is_eof = False
    if index < len(lines) and Parser._norm(lines[index]) == "*** End of File":
        index += 1
        is_eof = True
    return context_lines, chunks, index, is_eof

# --------------------------------------------------------------------------- #
#  Patch → Commit and Commit application
# --------------------------------------------------------------------------- #
def _get_updated_file(text: str, action: PatchAction, path: str) -> str:
    """Applies the chunks from a PatchAction to the original file content."""
    if action.type is not ActionType.UPDATE:
        raise DiffError("_get_updated_file called with non-update action")
    
    orig_lines = text.splitlines()
    dest_lines: List[str] = []
    orig_idx_ptr = 0

    sorted_chunks = sorted(action.chunks, key=lambda c: c.orig_index)

    for chunk in sorted_chunks:
        if chunk.orig_index > len(orig_lines):
            raise DiffError(
                f"In file '{path}', chunk tries to apply at line {chunk.orig_index + 1}, which is beyond the file's length of {len(orig_lines)} lines."
            )
        if orig_idx_ptr > chunk.orig_index:
            raise DiffError(
                f"In file '{path}', detected overlapping chunks at line {chunk.orig_index + 1}."
            )

        dest_lines.extend(orig_lines[orig_idx_ptr : chunk.orig_index])
        dest_lines.extend(chunk.ins_lines)
        orig_idx_ptr = chunk.orig_index + len(chunk.del_lines)

    dest_lines.extend(orig_lines[orig_idx_ptr:])
    
    new_content = "\n".join(dest_lines)
    if text.endswith('\n') or (not text and new_content):
        new_content += '\n'
        
    return new_content


def patch_to_commit(patch: Patch, orig: Dict[str, str]) -> Commit:
    """Converts a parsed Patch object into a Commit object with final content."""
    commit = Commit()
    for path, action in patch.actions.items():
        if action.type is ActionType.DELETE:
            commit.changes[path] = FileChange(type=ActionType.DELETE, old_content=orig[path])
        elif action.type is ActionType.ADD:
            if action.new_file is None:
                raise DiffError(f"ADD action for '{path}' has no content")
            commit.changes[path] = FileChange(type=ActionType.ADD, new_content=action.new_file)
        elif action.type is ActionType.UPDATE:
            new_content = _get_updated_file(orig[path], action, path)
            commit.changes[path] = FileChange(
                type=ActionType.UPDATE,
                old_content=orig[path],
                new_content=new_content,
                move_path=action.move_path,
            )
    return commit

# --------------------------------------------------------------------------- #
#  Patch text parser
# --------------------------------------------------------------------------- #
@dataclass
class Parser:
    """Parses patch text into a Patch object."""
    current_files: Dict[str, str]
    lines: List[str]
    index: int = 0
    patch: Patch = field(default_factory=Patch)
    fuzz: int = 0

    def _cur_line(self) -> str:
        if self.index >= len(self.lines):
            raise DiffError("Unexpected end of input while parsing patch")
        return self.lines[self.index]

    @staticmethod
    def _norm(line: str) -> str:
        """Strip CR so comparisons work for both LF and CRLF input."""
        return line.rstrip("\r")

    def is_done(self, prefixes: Optional[Tuple[str, ...]] = None) -> bool:
        if self.index >= len(self.lines):
            return True
        if prefixes and self._norm(self._cur_line()).startswith(prefixes):
            return True
        return False

    def startswith(self, prefix: Union[str, Tuple[str, ...]]) -> bool:
        return self._norm(self._cur_line()).startswith(prefix)

    def read_str(self, prefix: str) -> str:
        """Consumes the current line if it starts with *prefix* and returns the text after it."""
        if not prefix:
            raise ValueError("read_str() requires a non-empty prefix")
        norm_line = self._norm(self._cur_line())
        if norm_line.startswith(prefix):
            text = self._cur_line()[len(prefix) :]
            self.index += 1
            return text
        return ""

    def read_line(self) -> str:
        """Return the current raw line and advance."""
        line = self._cur_line()
        self.index += 1
        return line

    def parse(self) -> None:
        """Main parsing loop."""
        while not self.is_done(("*** End Patch",)):
            # ---------- UPDATE ---------- #
            if path := self.read_str("*** Update File: "):
                if path in self.patch.actions:
                    raise DiffError(f"Duplicate update for file: {path}")
                move_to = self.read_str("*** Move to: ")
                if path not in self.current_files:
                    raise DiffError(f"Update File Error - file to be updated does not exist: {path}")
                text = self.current_files[path]
                action = self._parse_update_file(text, path)
                action.move_path = move_to or None
                self.patch.actions[path] = action
                continue

            # ---------- DELETE ---------- #
            if path := self.read_str("*** Delete File: "):
                if path in self.patch.actions:
                    raise DiffError(f"Duplicate delete for file: {path}")
                if path not in self.current_files:
                    raise DiffError(f"Delete File Error - file to be deleted does not exist: {path}")
                self.patch.actions[path] = PatchAction(type=ActionType.DELETE)
                continue

            # ---------- ADD ---------- #
            if path := self.read_str("*** Add File: "):
                if path in self.patch.actions:
                    raise DiffError(f"Duplicate add for file: {path}")
                # The check for file existence is now handled in `process_patch`
                self.patch.actions[path] = self._parse_add_file()
                continue
            
            # If we are here, no known action was found
            line_preview = self._cur_line().strip()
            if not line_preview: # Skip blank lines between actions
                self.index += 1
                continue
            raise DiffError(f"Unknown or malformed action line while parsing: '{line_preview}'")

        if not self.startswith("*** End Patch"):
            raise DiffError("Missing '*** End Patch' sentinel at the end of the file")
        self.index += 1  # consume sentinel

    def _parse_update_file(self, text: str, path_for_error: str) -> PatchAction:
        """Parses the content of an 'Update File' section."""
        action = PatchAction(type=ActionType.UPDATE)
        orig_lines = text.splitlines()

        first_ctx_line = self.read_str("@@ ").strip()
        search_start_idx = 0
        if first_ctx_line:
            # FIX: Use fuzzy finding for the initial context line
            idx, _fuzz = find_context_core(orig_lines, [first_ctx_line], 0)
            if idx == -1:
                raise DiffError(f"In file '{path_for_error}', could not find initial context line: '{first_ctx_line}'")
            # FIX: The search for the full context block should start at the found line, not after it.
            search_start_idx = idx
        
        while not self.is_done(
            (
                "*** End Patch",
                "*** Update File:",
                "*** Delete File:",
                "*** Add File:",
            )
        ):
            next_ctx, chunks, end_idx, eof = peek_next_section(self.lines, self.index)
            if not chunks: 
                self.index = end_idx
                if self.startswith("@@"): # Consume the marker for the next section
                    self.index += 1
                if eof or self.is_done( # If no more chunks, we might be done
                    ("*** End Patch", "*** Update File:", "*** Delete File:", "*** Add File:")
                ):
                    break
                continue
            
            new_index, fuzz = find_context(orig_lines, next_ctx, search_start_idx, eof)
            if new_index == -1:
                ctx_txt = "\n".join(next_ctx)
                raise DiffError(
                    f"In file '{path_for_error}', could not find context block:\n---\n{ctx_txt}\n---"
                )
            
            self.fuzz += fuzz
            for ch in chunks:
                ch.orig_index += new_index
                action.chunks.append(ch)

            search_start_idx = new_index + len(next_ctx)
            self.index = end_idx

        return action

    def _parse_add_file(self) -> PatchAction:
        """Parses the content of an 'Add File' section."""
        lines: List[str] = []
        # FIX: Loop robustly, stopping when a line is not part of the add block.
        while not self.is_done(("*** End Patch", "*** Update File:", "*** Delete File:", "*** Add File:")):
            current_line = self._cur_line()
            if not current_line.startswith('+'):
                # Line is not part of the add block, so stop parsing this section.
                break
            
            s = self.read_line() # Consume the line
            lines.append(s[1:])

        content = "\n".join(lines)
        # FIX: By convention, ensure non-empty text files end with a newline.
        if content:
            content += '\n'

        return PatchAction(type=ActionType.ADD, new_file=content)