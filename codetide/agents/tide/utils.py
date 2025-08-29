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
                break  # Stop after end marker
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

def parse_patch_blocks(text: str, multiple: bool = True) -> Union[str, List[str], None]:
    """
    Extract content between *** Begin Patch and *** End Patch markers (inclusive),
    ensuring that both markers are at zero indentation (start of line, no leading spaces).

    Args:
        text: Full input text containing one or more patch blocks.
        multiple: If True, return a list of all patch blocks. If False, return the first match.

    Returns:
        A string (single patch), list of strings (multiple patches), or None if not found.
    """
    
    pattern = r"(?m)^(\*\*\* Begin Patch[\s\S]*?^\*\*\* End Patch)$"
    matches = re.findall(pattern, text)

    if not matches:
        return None

    return matches if multiple else matches[0]

def parse_commit_blocks(text: str, multiple: bool = True) -> Union[str, List[str], None]:
    """
    Extract content between *** Begin Commit and *** End Commit markers (exclusive),
    ensuring that both markers are at zero indentation (start of line, no leading spaces).

    Args:
        text: Full input text containing one or more commit blocks.
        multiple: If True, return a list of all commit blocks. If False, return the first match.

    Returns:
        A string (single commit), list of strings (multiple commits), or None if not found.
    """
    
    pattern = r"(?m)^\*\*\* Begin Commit\n([\s\S]*?)^\*\*\* End Commit$"
    matches = re.findall(pattern, text)

    if not matches:
        return None

    return matches if multiple else matches[0].strip()

def parse_steps_markdown(md: str):
    steps = []
    
    # Extract only content between *** Begin Steps and *** End Steps
    match = re.search(r"\*\*\* Begin Steps(.*?)\*\*\* End Steps", md, re.DOTALL)
    if not match:
        return []
    
    steps_block = match.group(1).strip()

    # Split steps by '---'
    raw_steps = [s.strip() for s in steps_block.split('---') if s.strip()]
    
    for raw_step in raw_steps:
        # Match step number and description
        step_header = re.match(r"(\d+)\.\s+\*\*(.*?)\*\*", raw_step)
        if not step_header:
            continue

        step_num = int(step_header.group(1))
        description = step_header.group(2).strip()

        # Match instructions
        instructions_match = re.search(r"\*\*instructions\*\*:\s*(.*?)(?=\*\*context_identifiers\*\*:)", raw_step, re.DOTALL)
        instructions = instructions_match.group(1).strip() if instructions_match else ""

        # Match context identifiers
        context_match = re.search(r"\*\*context_identifiers\*\*:\s*(.*)", raw_step, re.DOTALL)
        context_block = context_match.group(1).strip() if context_match else ""
        context_identifiers = re.findall(r"- (.+)", context_block)

        steps.append({
            "step": step_num,
            "description": description,
            "instructions": instructions,
            "context_identifiers": context_identifiers
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
