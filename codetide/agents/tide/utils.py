from codetide.core.defaults import DEFAULT_ENCODING

from typing import List, Union
import aiofiles.os
import aiofiles
import os
import re

async def trim_to_patch_section(filename):
    """Remove all lines before '*** Begin Patch' and after '*** End Patch'"""
    lines_to_keep = []
    capturing = False

    if not os.path.exists(filename):
        return
    
    async with aiofiles.open(filename, 'r', encoding=DEFAULT_ENCODING) as f:
        async for line in f:
            if '*** Begin Patch' in line:
                capturing = True
                lines_to_keep.append(line)  # Include the begin marker
            elif '*** End Patch' in line:
                lines_to_keep.append(line)  # Include the end marker
                capturing = False  # Stop capturing but continue processing
            elif capturing:
                lines_to_keep.append(line)
    
    if lines_to_keep: # Write back only the lines we want to keep
        async with aiofiles.open(filename, 'w', encoding=DEFAULT_ENCODING) as f:
            await f.writelines(lines_to_keep)
    else: # Otherwise, delete the file
        try:
            os.remove(filename)
        except FileNotFoundError:
            pass


def parse_blocks(text: str, block_word: str = "Commit", multiple: bool = True) -> Union[str, List[str], None]:
    """
    Extract content between *** Begin <block_word> and *** End <block_word> markers (exclusive),
    ensuring that both markers are at zero indentation (start of line, no leading spaces).

    Args:
        text: Full input text containing one or more blocks.
        block_word: The word to use in the block markers (e.g., "Commit", "Section", "Code").
        multiple: If True, return a list of all blocks. If False, return the first match.

    Returns:
        A string (single block), list of strings (multiple blocks), or None if not found.
    """
    
    # Escape the block_word to handle any special regex characters
    escaped_word = re.escape(block_word)
    
    # Create pattern with the parameterized block word
    pattern = rf"(?m)^\*\*\* Begin {escaped_word}\n([\s\S]*?)^\*\*\* End {escaped_word}$"
    matches = re.findall(pattern, text)

    if not matches:
        return None

    if multiple:
        return [match.strip() for match in matches]
    else:
        return matches[0].strip()

def parse_steps_markdown(md: str):
    """
    Parse the markdown steps block and return a list of step dicts.
    Now supports both context_identifiers and modify_identifiers.
    """
    steps = []
    step_blocks = re.split(r'---\s*', md)
    for block in step_blocks:
        block = block.strip()
        if not block or block.startswith("*** End Steps"):
            continue
        # Parse step number and description
        m = re.match(
            r'(\d+)\.\s+\*\*(.*?)\*\*\s*\n\s*\*\*instructions\*\*:\s*(.*?)\n\s*\*\*context_identifiers\*\*:\s*((?:- .*\n?)*)\s*\*\*modify_identifiers\*\*:\s*((?:- .*\n?)*)',
            block, re.DOTALL)
        if not m:
            continue
        step_num = int(m.group(1))
        description = m.group(2).strip()
        instructions = m.group(3).strip()
        context_block = m.group(4)
        modify_block = m.group(5)
        context_identifiers = [line[2:].strip() for line in context_block.strip().splitlines() if line.strip().startswith('-')]
        modify_identifiers = [line[2:].strip() for line in modify_block.strip().splitlines() if line.strip().startswith('-')]
        steps.append({
            "step": step_num,
            "description": description,
            "instructions": instructions,
            "context_identifiers": context_identifiers,
            "modify_identifiers": modify_identifiers
        })
    return steps

async def delete_file(file_path: str) -> bool:
    """
    Safely delete a file asynchronously.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        bool: True if file was deleted, False if it didn't exist
        
    Raises:
        PermissionError: If lacking permissions to delete
        OSError: For other OS-related errors
    """
    try:
        await aiofiles.os.remove(file_path)
        return True
    except FileNotFoundError:
        # File doesn't exist - consider this "success"
        return False
    except PermissionError:
        # Handle permission issues
        raise
    except OSError:
        # Handle other OS errors (disk full, etc.)
        raise
