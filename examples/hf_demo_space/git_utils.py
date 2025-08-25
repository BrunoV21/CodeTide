from pathlib import Path
from ulid import ulid
import subprocess
import asyncio
import pygit2
import re


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
            branch_name = f"agent-tide-{ulid()}"
        
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

def push_new_branch(repo :pygit2.Repository, branch_name :str, remote_name :str='origin'):
    """
    Push a new branch to remote origin (equivalent to 'git push origin branch_name')
    
    Args:
        repo (pygit2.Repository): Repo Obj
        branch_name (str): Name of the branch to push
        remote_name (str): Name of the remote (default: 'origin')
    
    Returns:
        bool: True if push was successful, False otherwise
    """
    
    # Get the remote
    remote = repo.remotes[remote_name]
    
    # Create refspec for pushing new branch
    # Format: local_branch:remote_branch (this publishes the new branch)
    refspec = f'refs/heads/{branch_name}:refs/heads/{branch_name}'
    
    # Push to remote
    result = remote.push([refspec])
    
    # Check if push was successful (no error message means success)
    return not result.error_message

def checkout_new_branch(repo :pygit2.Repository, new_branch_name :str, start_point=None):
    """
    Create and checkout a new branch from the current HEAD or specified start point.
    
    Args:
        repo_path (str): Path to the git repository
        new_branch_name (str): Name of the new branch to create and checkout
        start_point (pygit2.Oid or Reference, optional): Commit or reference to start from. 
                                                         If None, uses current HEAD.
    
    Returns:
        pygit2.Reference: The newly created branch reference
    
    Raises:
        ValueError: If branch already exists or invalid start point
        Exception: For other git-related errors
    """
    
    # Check if branch already exists
    if new_branch_name in repo.branches.local:
        raise ValueError(f"Branch '{new_branch_name}' already exists")
    
    # Get the start point commit (default to HEAD)
    if start_point is None:
        if repo.head_is_detached:
            raise ValueError("HEAD is detached, please specify a start point")
        start_point = repo.head.target
    
    # Create the new branch
    new_branch = repo.branches.local.create(new_branch_name, repo[start_point])
    
    # Checkout the new branch
    repo.checkout(new_branch, strategy=pygit2.GIT_CHECKOUT_SAFE)
    
    return new_branch