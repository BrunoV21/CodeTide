from functools import partial
from codetide import CodeTide
from ...mcp.tools.patch_code import file_exists, open_file, process_patch, remove_file, write_file
from ...core.defaults import DEFAULT_ENCODING, DEFAULT_STORAGE_PATH
from ...autocomplete import AutoComplete
from .models import Steps
from .prompts import (
    AGENT_TIDE_SYSTEM_PROMPT, GET_CODE_IDENTIFIERS_SYSTEM_PROMPT, REJECT_PATCH_FEEDBACK_TEMPLATE,
    STAGED_DIFFS_TEMPLATE, STEPS_SYSTEM_PROMPT, WRITE_PATCH_SYSTEM_PROMPT
)
from .utils import delete_file, parse_blocks, parse_patch_blocks, parse_steps_markdown, trim_to_patch_section
from .consts import AGENT_TIDE_ASCII_ART

try:
    from aicore.llm import Llm
    from aicore.logger import _logger, SPECIAL_TOKENS
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' package. "
        "Install it with: pip install codetide[agents]"
    ) from e

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self
from typing import List, Optional, Set
from datetime import date
from pathlib import Path
from ulid import ulid
import aiofiles
import asyncio
import pygit2
import os

async def custom_logger_fn(message :str, session_id :str, filepath :str):
    if message not in SPECIAL_TOKENS:
        async with aiofiles.open(filepath, 'a', encoding=DEFAULT_ENCODING) as f:
            await f.write(message)

    await _logger.log_chunk_to_queue(message, session_id)

class AgentTide(BaseModel):
    llm :Llm
    tide :CodeTide
    history :Optional[list]=None
    steps :Optional[Steps]=None
    session_id :str=Field(default_factory=ulid)
    changed_paths :List[str]=Field(default_factory=list)
    request_human_confirmation :bool=False

    contextIdentifiers :Optional[List[str]]=None
    modifyIdentifiers :Optional[List[str]]=None
    reasoning :Optional[str]=None

    _skip_context_retrieval :bool=False
    _last_code_identifers :Optional[Set[str]]=set()
    _last_code_context :Optional[str] = None
    _has_patch :bool=False

    @model_validator(mode="after")
    def pass_custom_logger_fn(self)->Self:
        self.llm.logger_fn = partial(custom_logger_fn, session_id=self.session_id, filepath=self.patch_path)
        return self
    
    def approve(self):
        self._has_patch = False
        if os.path.exists(self.patch_path):
            changed_paths = process_patch(self.patch_path, open_file, write_file, remove_file, file_exists, root_path=self.tide.rootpath)
            self.changed_paths.extend(changed_paths)

            previous_response = self.history[-1]
            diffPatches = parse_patch_blocks(previous_response, multiple=True)
            if diffPatches:
                for patch in diffPatches:
                    # TODO this deletes previouspatches from history to make sure changes are always focused on the latest version of the file
                    previous_response = previous_response.replace(f"*** Begin Patch\n{patch}*** End Patch", "")
                self.history[-1] = previous_response

    def reject(self, feedback :str):
        self._has_patch = False
        self.history.append(REJECT_PATCH_FEEDBACK_TEMPLATE.format(
            FEEDBACK=feedback
        ))

    @property
    def patch_path(self)->Path:
        if not os.path.exists(self.tide.rootpath / DEFAULT_STORAGE_PATH):
            os.makedirs(self.tide.rootpath / DEFAULT_STORAGE_PATH, exist_ok=True)
        
        return self.tide.rootpath / DEFAULT_STORAGE_PATH / f"{self.session_id}.bash"

    @staticmethod
    def trim_messages(messages, tokenizer_fn, max_tokens :Optional[int]=None):
        max_tokens = max_tokens or int(os.environ.get("MAX_HISTORY_TOKENS", 1028))
        while messages and sum(len(tokenizer_fn(str(msg))) for msg in messages) > max_tokens:
            messages.pop(0)  # Remove from the beginning

    async def agent_loop(self, codeIdentifiers :Optional[List[str]]=None):
        TODAY = date.today()

        # update codetide with the latest changes made by the human and agent
        await self.tide.check_for_updates(serialize=True, include_cached_ids=True)

        repo_tree = self.tide.codebase.get_tree_view(
            include_modules=True,
            include_types=True
        )

        if codeIdentifiers is None and not self._skip_context_retrieval:
            context_response = await self.llm.acomplete(
                self.history,
                system_prompt=[GET_CODE_IDENTIFIERS_SYSTEM_PROMPT.format(DATE=TODAY)],
                prefix_prompt=repo_tree,
                stream=False
                # json_output=True
            )

            contextIdentifiers = parse_blocks(context_response, block_word="Context Identifiers", multiple=False)
            modifyIdentifiers = parse_blocks(context_response, block_word="Modify Identifiers", multiple=False)

            reasoning = context_response.split("*** Begin")
            if not reasoning:
                reasoning = [context_response]
            self.reasoning = reasoning[0].strip()

            self.contextIdentifiers = contextIdentifiers.splitlines() or None
            self.modifyIdentifiers = modifyIdentifiers.splitlines() or None
            # TODO need fo finsih implementing context and modify identifiers into codetide logic

        codeContext = None
        if codeIdentifiers:
            autocomplete = AutoComplete(self.tide.cached_ids)
            # Validate each code identifier
            validatedCodeIdentifiers = []
            for codeId in codeIdentifiers:
                result = autocomplete.validate_code_identifier(codeId)
                if result.get("is_valid"):
                    validatedCodeIdentifiers.append(codeId)
                
                elif result.get("matching_identifiers"):
                    validatedCodeIdentifiers.append(result.get("matching_identifiers")[0])

            self._last_code_identifers = set(validatedCodeIdentifiers)
            codeContext = self.tide.get(validatedCodeIdentifiers, as_string=True)
            self._last_code_context = codeContext

        await delete_file(self.patch_path)
        response = await self.llm.acomplete(
            self.history,
            system_prompt=[
                AGENT_TIDE_SYSTEM_PROMPT.format(DATE=TODAY),
                STEPS_SYSTEM_PROMPT.format(DATE=TODAY, REPO_TREE=repo_tree),
                WRITE_PATCH_SYSTEM_PROMPT.format(DATE=TODAY)
            ],
            prefix_prompt=codeContext
        )

        await trim_to_patch_section(self.patch_path)
        if not self.request_human_confirmation:
            self.approve()

        commitMessage = parse_blocks(response, multiple=False, block_word="Commit")
        if commitMessage:
            self.commit(commitMessage)

        steps = parse_steps_markdown(response)
        if steps:
            self.steps = Steps.from_steps(steps)

        diffPatches = parse_patch_blocks(response, multiple=True)
        if diffPatches:
            if self.request_human_confirmation:
                self._has_patch = True
            else:
                for patch in diffPatches:
                    # TODO this deletes previouspatches from history to make sure changes are always focused on the latest version of the file
                    response = response.replace(f"*** Begin Patch\n{patch}*** End Patch", "")

        self.history.append(response)

    @staticmethod
    async def get_git_diff_staged_simple(directory: str) -> str:
        """
        Simple async function to get git diff --staged output
        """
        # Validate directory exists
        if not Path(directory).is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        process = await asyncio.create_subprocess_exec(
            'git', 'diff', '--staged',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=directory
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Git command failed: {stderr.decode().strip()}")
        
        return stdout.decode()

    async def _stage(self)->str:
        index = self.tide.repo.index
        for path in self.changed_paths:
           index.add(path)

        index.write()

        staged_diff = await self.get_git_diff_staged_simple(self.tide.rootpath)
        staged_diff = staged_diff.strip()
        return staged_diff if staged_diff else "No files were staged. Nothing to commit. Tell the user to request some changes so there is something to commit"

    async def prepare_commit(self)->str:
        staged_diff = await self._stage()
        self.changed_paths = []
        self._skip_context_retrieval = True
        return STAGED_DIFFS_TEMPLATE.format(diffs=staged_diff)

    def commit(self, message :str):
        """
        Commit all staged files in a git repository with the given message.
        
        Args:
            repo_path (str): Path to the git repository
            message (str): Commit message
            author_name (str, optional): Author name. If None, uses repo config
            author_email (str, optional): Author email. If None, uses repo config
        
        Returns:
            pygit2.Commit: The created commit object, or None if no changes to commit
        
        Raises:
            ValueError: If no files are staged for commit
            Exception: For other git-related errors
        """
        try:
            # Open the repository
            repo = self.tide.repo
            
            # Get author and committer information
            config = repo.config
            author_name = config._get('user.name')[1].value or 'Unknown Author'
            author_email = config._get('user.email')[1].value or 'unknown@example.com'
            
            author = pygit2.Signature(author_name, author_email)
            committer = author  # Typically same as author
            
            # Get the current tree from the index
            tree = repo.index.write_tree()
            
            # Get the parent commit (current HEAD)
            parents = [repo.head.target] if repo.head else []
            
            # Create the commit
            commit_oid = repo.create_commit(
                'HEAD',  # Reference to update
                author,
                committer,
                message,
                tree,
                parents
            )
            
            # Clear the staging area after successful commit
            repo.index.write()
            
            return repo[commit_oid]
            
        except pygit2.GitError as e:
            raise Exception(f"Git error: {e}")
        except KeyError as e:
            raise Exception(f"Configuration error: {e}")
        
        finally:
            self._skip_context_retrieval = False

    async def run(self, max_tokens: int = 48000):
        if self.history is None:
            self.history = []

        # 1. Set up key bindings
        bindings = KeyBindings()

        @bindings.add('escape')
        def _(event):
            """When Esc is pressed, exit the application."""
            _logger.logger.warning("Escape key pressed — exiting...")
            event.app.exit()

        # 2. Create a prompt session with the custom key bindings
        session = PromptSession(key_bindings=bindings)

        print(f"\n{AGENT_TIDE_ASCII_ART}\n")
        _logger.logger.info("Ready to surf. Press ESC to exit.")
        try:
            while True:
                try:
                    # 3. Use the async prompt instead of input()
                    message = await session.prompt_async("You: ")
                    if message is None:
                        break
                    
                    message = message.strip()

                    if not message:
                        continue

                except (EOFError, KeyboardInterrupt):
                    # prompt_toolkit raises EOFError on Ctrl-D and KeyboardInterrupt on Ctrl-C
                    _logger.logger.warning("Exiting...")
                    break

                self.history.append(message)
                self.trim_messages(self.history, self.llm.tokenizer, max_tokens)

                print("Agent: Thinking...")
                await self.agent_loop()

        except asyncio.CancelledError:
            # This can happen if the event loop is shut down
            pass
        finally:
            _logger.logger.info("Exited by user. Goodbye!")

    async def _handle_commands(self, command :str) -> str:
        # TODO add logic here to handlle git command, i.e stage files, write commit messages and checkout
        # expand to support new branches
        context = ""
        if command == "commit":
            context = await self.prepare_commit()

        return context
