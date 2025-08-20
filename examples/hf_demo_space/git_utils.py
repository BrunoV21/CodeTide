import asyncio
from pathlib import Path
import re
import subprocess


GIT_URL_PATTERN = re.compile(
    r'^(?:http|https|git|ssh)://'  # Protocol
    r'(?:\S+@)?'  # Optional username
    r'([^/]+)'  # Domain
    r'(?:[:/])([^/]+/[^/]+?)(?:\.git)?$'  # Repo path
)

async def validate_git_url(url) -> None:
    """Validate the Git repository URL using git ls-remote."""

    if not GIT_URL_PATTERN.match(url):
        raise ValueError(f"Invalid Git repository URL format: {url}")
        
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "ls-remote", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, ["git", "ls-remote", url], stdout, stderr)
            
        if not stdout.strip():
            raise ValueError(f"URL {url} points to an empty repository")
            
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ValueError(f"Timeout while validating URL {url}")
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Invalid Git repository URL: {url}. Error: {e.stderr}") from e

async def commit_and_push_changes(repo_path: Path, branch_name: str = None, commit_message: str = "Auto-commit: Save changes") -> None:
    """Add all changes, commit with default message, and push to remote."""
    
    repo_path_str = str(repo_path)
    
    try:
        # Create new branch with Agent Tide + ULID name if not provided
        if not branch_name:
            import ulid
            branch_name = f"agent-tide-{ulid.new()}"
        
        # Create and checkout new branch
        process = await asyncio.create_subprocess_exec(
            "git", "checkout", "-b", branch_name,
            cwd=repo_path_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, ["git", "checkout", "-b", branch_name], stdout, stderr)
        
        # Add all changes
        process = await asyncio.create_subprocess_exec(
            "git", "add", ".",
            cwd=repo_path_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, ["git", "add", "."], stdout, stderr)
        
        # Commit changes
        process = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", commit_message,
            cwd=repo_path_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        
        if process.returncode != 0:
            # Check if it's because there are no changes to commit
            if "nothing to commit" in stderr or "nothing to commit" in stdout:
                return  # No changes to commit, exit gracefully
            raise subprocess.CalledProcessError(process.returncode, ["git", "commit", "-m", commit_message], stdout, stderr)
        
        # Push to remote
        process = await asyncio.create_subprocess_exec(
            "git", "push", "origin", branch_name,
            cwd=repo_path_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, ["git", "push", "origin", branch_name], stdout, stderr)
            
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ValueError(f"Timeout during git operation in {repo_path}")
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Git operation failed in {repo_path}. Error: {e.stderr}") from e
