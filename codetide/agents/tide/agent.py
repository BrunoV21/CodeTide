import json
from codetide import CodeTide
from ...mcp.tools.patch_code import file_exists, open_file, process_patch, remove_file, write_file, parse_patch_blocks
from ...core.defaults import DEFAULT_STORAGE_PATH
from ...parsers import SUPPORTED_LANGUAGES
from ...autocomplete import AutoComplete
from .models import Steps
from .prompts import (
    AGENT_TIDE_SYSTEM_PROMPT, CALMNESS_SYSTEM_PROMPT, CMD_BRAINSTORM_PROMPT, CMD_CODE_REVIEW_PROMPT, CMD_TRIGGER_PLANNING_STEPS, CMD_WRITE_TESTS_PROMPT, FINALIZE_IDENTIFIERS_PROMPT, GATHER_CANDIDATES_PROMPT, GET_CODE_IDENTIFIERS_UNIFIED_PROMPT, README_CONTEXT_PROMPT, REJECT_PATCH_FEEDBACK_TEMPLATE,
    REPO_TREE_CONTEXT_PROMPT, STAGED_DIFFS_TEMPLATE, STEPS_SYSTEM_PROMPT, WRITE_PATCH_SYSTEM_PROMPT
)
from .utils import delete_file, parse_blocks, parse_steps_markdown, trim_to_patch_section
from .consts import AGENT_TIDE_ASCII_ART

try:
    from aicore.llm import Llm
    from aicore.logger import _logger    
    from .streaming.service import custom_logger_fn
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' package. "
        "Install it with: pip install codetide[agents]"
    ) from e

from pydantic import BaseModel, Field, ConfigDict, model_validator
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from typing import List, Optional, Set
from typing_extensions import Self
from functools import partial
from datetime import date
from pathlib import Path
from ulid import ulid
import asyncio
import pygit2
import os

ROUND_FINISHED = "<FINISHED-GEN>"

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
    _direct_mode :bool=False

    # Number of previous interactions to remember for context identifiers
    CONTEXT_WINDOW_SIZE: int = 3
    # Rolling window of identifier sets from previous N interactions
    _context_identifier_window: Optional[list] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def pass_custom_logger_fn(self)->Self:
        self.llm.logger_fn = partial(custom_logger_fn, session_id=self.session_id, filepath=self.patch_path)
        return self

    async def get_repo_tree_from_user_prompt(self, history :list, include_modules :bool=False, expand_paths :Optional[List[str]]=None)->str:

        history_str = "\n\n".join(history)
        for CMD_PROMPT in [CMD_TRIGGER_PLANNING_STEPS, CMD_WRITE_TESTS_PROMPT, CMD_BRAINSTORM_PROMPT, CMD_CODE_REVIEW_PROMPT]:
            history_str.replace(CMD_PROMPT, "")

        self.tide.codebase._build_tree_dict(expand_paths)

        tree = self.tide.codebase.get_tree_view(
            include_modules=include_modules,
            include_types=True
        )
        return tree

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

    @staticmethod
    def get_valid_identifier(autocomplete :AutoComplete, identifier:str)->Optional[str]:
        result = autocomplete.validate_code_identifier(identifier)
        if result.get("is_valid"):
            return identifier
        elif result.get("matching_identifiers"):
            return result.get("matching_identifiers")[0]
        return None

    def _clean_history(self):
        for i in range(len(self.history)):
            message = self.history[i]
            if isinstance(message, dict):
                self.history[i] = message.get("content" ,"")
    
    async def get_identifiers_two_phase(self, autocomplete :AutoComplete, codeIdentifiers=None, TODAY :str=None):
        """
        Two-phase identifier resolution:
        Phase 1: Gather candidates through iterative tree expansion
        Phase 2: Classify and finalize identifiers with operation mode
        """
        # Initialize tracking
        last_message = self.history[-1] if self.history else ""
        matches = autocomplete.extract_words_from_text(last_message, max_matches_per_word=1)["all_found_words"]
        
        self._context_identifier_window.append(set(matches))
        if len(self._context_identifier_window) > self.CONTEXT_WINDOW_SIZE:
            self._context_identifier_window.pop(0)
        
        window_identifiers = set()
        for s in self._context_identifier_window:
            window_identifiers.update(s)
        
        initial_identifiers = set(codeIdentifiers) if codeIdentifiers else set()
        initial_identifiers.update(window_identifiers)
        
        # ===== PHASE 1: CANDIDATE GATHERING =====
        candidate_pool = set()
        all_reasoning = []
        iteration_count = 0
        max_iterations = 3
        repo_tree = None
        expand_paths = ["./"]
        enough_identifiers = False
        expanded_history = list(self.history)[-3:]  # Track expanded history
        
        while not enough_identifiers and iteration_count < max_iterations:
            iteration_count += 1
            
            # Get current repo tree state
            if repo_tree is None or iteration_count > 1:
                repo_tree = await self.get_repo_tree_from_user_prompt(
                    expanded_history,
                    include_modules=bool(iteration_count > 1),
                    expand_paths=expand_paths
                )
            
            # Prepare accumulated context
            accumulated_context = "\n".join(sorted(candidate_pool)) if candidate_pool else "None yet"
            
            # Phase 1 LLM call
            phase1_response = await self.llm.acomplete(
                expanded_history,
                system_prompt=[GATHER_CANDIDATES_PROMPT.format(
                    DATE=TODAY,
                    SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES,
                    TREE_STATE="Current view" if iteration_count == 1 else "Expanded view",
                    ACCUMULATED_CONTEXT=accumulated_context,
                    ITERATION_COUNT=iteration_count
                )],
                prefix_prompt=repo_tree,
                stream=True
            )
            
            print(f"Phase 1 Iteration {iteration_count}: {phase1_response}")
            
            # Parse Phase 1 response
            reasoning_blocks = parse_blocks(phase1_response, block_word="Reasoning", multiple=True)
            expand_paths_block = parse_blocks(phase1_response, block_word="Expand Paths", multiple=False)
            
            # Extract and accumulate candidates from reasoning blocks
            for reasoning in reasoning_blocks:
                all_reasoning.append(reasoning)
                # Extract candidate identifiers from reasoning block
                if "**Candidate Identifiers**:" in reasoning or "**candidate_identifiers**:" in reasoning.lower():
                    lines = reasoning.split('\n')
                    capture = False
                    for line in lines:
                        if "candidate" in line.lower() and "identifier" in line.lower():
                            capture = True
                            continue
                        if capture and line.strip().startswith('-'):
                            ident = line.strip().lstrip('-').strip()
                            if ident := self.get_valid_identifier(autocomplete, ident):
                                candidate_pool.add(ident)
            
            # Check if we need to expand more
            if "ENOUGH_IDENTIFIERS: TRUE" in phase1_response.upper():
                enough_identifiers = True
            
            # Check if we need more history
            if "ENOUGH_HISTORY: FALSE" in phase1_response.upper() and iteration_count == 1:
                # Load more history for next iteration
                # TODO this should be imcremental i.e starting += 2 each time!
                expanded_history = self.history[-5:] if len(self.history) > 1 else self.history
            
            # Parse expansion paths for next iteration
            if expand_paths_block and not enough_identifiers:
                expand_paths = [
                    path.strip() for path in expand_paths_block.strip().split('\n')
                    if path.strip() and self.get_valid_identifier(autocomplete, path.strip())
                ]
            else:
                expand_paths = []
        
        # ===== PHASE 2: FINAL SELECTION AND CLASSIFICATION =====
        
        # Prepare Phase 2 input
        all_reasoning_text = "\n\n".join(all_reasoning)
        all_candidates_text = "\n".join(sorted(candidate_pool))
        
        phase2_response = await self.llm.acomplete(
            expanded_history,
            system_prompt=[FINALIZE_IDENTIFIERS_PROMPT.format(
                DATE=TODAY,
                SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES,
                USER_REQUEST=last_message,
                ALL_CANDIDATES=all_candidates_text
            )],
            prefix_prompt=f"Phase 1 Exploration Results:\n\n{all_reasoning_text}",
            stream=True
        )
        
        print(f"Phase 2 Final Selection: {phase2_response}")
        
        # Parse Phase 2 response
        summary = parse_blocks(phase2_response, block_word="Summary", multiple=False)
        context_identifiers = parse_blocks(phase2_response, block_word="Context Identifiers", multiple=False)
        modify_identifiers = parse_blocks(phase2_response, block_word="Modify Identifiers", multiple=False)
        
        # Extract operation mode
        operation_mode = "STANDARD"  # default
        if "OPERATION_MODE:" in phase2_response:
            mode_line = [line for line in phase2_response.split('\n') if 'OPERATION_MODE:' in line]
            if mode_line:
                operation_mode = mode_line[0].split('OPERATION_MODE:')[1].strip()
        
        # Process final identifiers
        final_context = set()
        final_modify = set()
        
        if context_identifiers:
            for ident in context_identifiers.strip().split('\n'):
                if ident := self.get_valid_identifier(autocomplete, ident.strip()):
                    final_context.add(ident)
        
        if modify_identifiers:
            for ident in modify_identifiers.strip().split('\n'):
                if ident := self.get_valid_identifier(autocomplete, ident.strip()):
                    final_modify.add(ident)
        
        return {
            "matches": matches,
            "context_identifiers": list(final_context),
            "modify_identifiers": self.tide._as_file_paths(list(final_modify)),
            "operation_mode": operation_mode,
            "summary": summary,
            "expanded_history": expanded_history,  # Make available for downstream
            "all_reasoning": all_reasoning_text,
            "iteration_count": iteration_count
        }

    async def agent_loop(self, codeIdentifiers :Optional[List[str]]=None):
        TODAY = date.today()
        await self.tide.check_for_updates(serialize=True, include_cached_ids=True)
        print("Finished check for updates")
        self._clean_history()
        print("Finished clean history")

        # Initialize the context identifier window if not present
        if self._context_identifier_window is None:
            self._context_identifier_window = []

        codeContext = None
        if self._skip_context_retrieval:
            expanded_history = self.history[-1]
        else:
            autocomplete = AutoComplete(self.tide.cached_ids)
            print(f"{autocomplete=}")
            if self._direct_mode:
                self.contextIdentifiers = None
                # Only extract matches from the last message
                last_message = self.history[-1] if self.history else ""
                exact_matches = autocomplete.extract_words_from_text(last_message, max_matches_per_word=1)["all_found_words"]
                self.modifyIdentifiers = self.tide._as_file_paths(exact_matches)
                codeIdentifiers = self.modifyIdentifiers
                self._direct_mode = False
                # Update the context identifier window
                self._context_identifier_window.append(set(exact_matches))
                if len(self._context_identifier_window) > self.CONTEXT_WINDOW_SIZE:
                    self._context_identifier_window.pop(0)
                expanded_history = self.history[-5:]
                operation_mode = "STANDARD, PATH_CODE"
                ### TODO create lightweight version to skip tree expansion and infer operationan_mode and expanded_history
            else:
                reasoning_output = await self.get_identifiers_two_phase(autocomplete, codeIdentifiers, TODAY)
                print(json.dumps(reasoning_output, indent=4))

                codeIdentifiers = reasoning_output.get("context_identifiers", []) + reasoning_output.get("modify_identifiers", [])
                matches = reasoning_output.get("matches")
                operation_mode = reasoning_output.get("operation_mode")
                expanded_history = reasoning_output.get("expanded_history")

            # --- End Unified Identifier Retrieval ---
            if codeIdentifiers:
                self._last_code_identifers = set(codeIdentifiers)
                codeContext = self.tide.get(codeIdentifiers, as_string=True)

            if not codeContext:
                codeContext = REPO_TREE_CONTEXT_PROMPT.format(REPO_TREE=self.tide.codebase.get_tree_view())
                # Use matches from the last message for README context
                readmeFile = self.tide.get(["README.md"] + (matches if 'matches' in locals() else []), as_string_list=True)
                if readmeFile:
                    codeContext = "\n".join([codeContext, README_CONTEXT_PROMPT.format(README=readmeFile)])

        self._last_code_context = codeContext
        await delete_file(self.patch_path)
        response = await self.llm.acomplete(
            expanded_history,
            system_prompt=[
                AGENT_TIDE_SYSTEM_PROMPT.format(DATE=TODAY),
                STEPS_SYSTEM_PROMPT.format(DATE=TODAY),
                WRITE_PATCH_SYSTEM_PROMPT.format(DATE=TODAY),
                CALMNESS_SYSTEM_PROMPT
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
        await self.llm.logger_fn(ROUND_FINISHED)

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

    def _has_staged(self)->bool:
        status = self.tide.repo.status()
        result = any([file_status == pygit2.GIT_STATUS_INDEX_MODIFIED for file_status in status.values()])
        _logger.logger.debug(f"_has_staged {result=}")
        return result

    async def _stage(self)->str:
        index = self.tide.repo.index
        if not self._has_staged():
            for path in self.changed_paths:
                index.add(str(Path(path)))

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
        elif command == "direct_mode":
            self._direct_mode = True

        return context
