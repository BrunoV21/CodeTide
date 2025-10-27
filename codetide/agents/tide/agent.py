import json
import re
from codetide import CodeTide
from ...mcp.tools.patch_code import file_exists, open_file, process_patch, remove_file, write_file, parse_patch_blocks
from ...search.code_search import SmartCodeSearch
from ...core.defaults import DEFAULT_STORAGE_PATH
from ...parsers import SUPPORTED_LANGUAGES
from ...autocomplete import AutoComplete
from .models import Steps
from .prompts import (
    AGENT_TIDE_SYSTEM_PROMPT, ASSESS_HISTORY_RELEVANCE_PROMPT, CALMNESS_SYSTEM_PROMPT, CMD_BRAINSTORM_PROMPT, CMD_CODE_REVIEW_PROMPT, CMD_TRIGGER_PLANNING_STEPS, CMD_WRITE_TESTS_PROMPT, DETERMINE_OPERATION_MODE_PROMPT, DETERMINE_OPERATION_MODE_SYSTEM, FINALIZE_IDENTIFIERS_PROMPT, GATHER_CANDIDATES_PREFIX, GATHER_CANDIDATES_SYSTEM, PREFIX_SUMMARY_PROMPT, README_CONTEXT_PROMPT, REASONING_TEMPLTAE, REJECT_PATCH_FEEDBACK_TEMPLATE,
    REPO_TREE_CONTEXT_PROMPT, STAGED_DIFFS_TEMPLATE, STEPS_SYSTEM_PROMPT, WRITE_PATCH_SYSTEM_PROMPT
)
from .utils import delete_file, parse_blocks, parse_steps_markdown, trim_to_patch_section
from .consts import AGENT_TIDE_ASCII_ART, REASONING_FINISHED, REASONING_STARTED, ROUND_FINISHED

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
from typing import Any, Dict, List, Optional, Set, Tuple
from typing_extensions import Self
from functools import partial
from datetime import date
from pathlib import Path
from ulid import ulid
import asyncio
import pygit2
import os

FILE_TEMPLATE = """{FILENAME}

{CONTENT}
"""

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
    _smart_code_search :Optional[Any]=None

    # Number of previous interactions to remember for context identifiers
    CONTEXT_WINDOW_SIZE: int = 3
    # Rolling window of identifier sets from previous N interactions
    _context_identifier_window: Optional[list] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    OPERATIONS :Dict[str, str] = {
        "PLAN_STEPS": STEPS_SYSTEM_PROMPT,
        "PATCH_CODE": WRITE_PATCH_SYSTEM_PROMPT
    }

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
    
    async def get_identifiers_two_phase(self, search_query :Optional[str], direct_matches :List[str], autocomplete :AutoComplete, expanded_history :list, codeIdentifiers=None, TODAY :str=None):
        """
        Two-phase identifier resolution:
        Phase 1: Gather candidates through iterative tree expansion
        Phase 2: Classify and finalize identifiers with operation mode
        """
        # Initialize tracking
        matches = set(direct_matches)

        ### TODO replace matches with search based on received search query
        ### get identifiers 
        ### search for identifers and ask llm to return only related ones -> if not enough then generate search query and keep cycling instead of expanding paths
        if search_query is None:
            search_query = expanded_history[-1]
        
        # ===== PHASE 1: CANDIDATE GATHERING =====
        candidate_pool = set()
        all_reasoning = []
        iteration_count = 0
        max_iterations = 3
        enough_identifiers = False
        previous_phase_1_response = None
        
        while not enough_identifiers and iteration_count < max_iterations:
            # print(f"{iteration_count=}")
            iteration_count += 1
            serch_results = await self._smart_code_search.search_smart(search_query, use_variations=False, top_k=15)
            identifiers_from_search = {result[0] for result in serch_results}

            if matches.issubset(identifiers_from_search):
                candidate_pool = matches
                print("All matches found in indeintiferis from search")
                break

            candidates_to_filter_tree = self.tide._as_file_paths(list(identifiers_from_search))
            # print("got identifiers")
            self.tide.codebase._build_tree_dict(candidates_to_filter_tree, slim=True)
            # print("got tree")
            sub_tree = self.tide.codebase.get_tree_view()
            # print(sub_tree)
            prefix_prompt = [
                GATHER_CANDIDATES_PREFIX.format(
                    LAST_SEARCH_QUERY=search_query,
                    ITERATION_COUNT=iteration_count,
                    ACCUMULATED_CONTEXT=set(self._context_identifier_window),
                    DIRECT_MATCHES=matches,
                    SEARCH_CANDIDATES=identifiers_from_search,
                    REPO_TREE=sub_tree
                )
            ]
            if previous_phase_1_response:
                prefix_prompt.insert(0, previous_phase_1_response)
            
            # Phase 1 LLM call
            phase1_response = await self.llm.acomplete(
                expanded_history,
                system_prompt=GATHER_CANDIDATES_SYSTEM.format(
                    DATE=TODAY,
                    SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES
                ),
                prefix_prompt=prefix_prompt,
                stream=True,
                action_id=f"phase_1.{iteration_count}"
            )
            previous_phase_1_response = phase1_response
            
            # Parse Phase 1 response
            reasoning_blocks = parse_blocks(phase1_response, block_word="Reasoning", multiple=True)
            search_query = parse_blocks(phase1_response, block_word="Search Query", multiple=False)

            patterns = {
                "header": r"\*{0,2}Task\*{0,2}:\s*(.+?)(?=\n\s*\*{0,2}Rationale\*{0,2})",
                "content": r"\*{0,2}Rationale\*{0,2}:\s*(.+?)(?=\s*\*{0,2}NEW Candidate Identifiers\*{0,2}|$)",
                "candidate_identifiers": r"^\s*-\s*(.+?)$"
            }
            if reasoning_blocks is not None:
                all_reasoning.extend(reasoning_blocks)
                for reasoning in reasoning_blocks:
                    # Extract candidate identifiers using regex
                    candidate_pattern = patterns["candidate_identifiers"]
                    candidate_matches = re.findall(candidate_pattern, reasoning, re.MULTILINE)
                    # print(f"{candidate_matches}=")
                    
                    for match in candidate_matches:
                        ident = match.strip()
                        if ident := self.get_valid_identifier(autocomplete, ident):
                            candidate_pool.add(ident)
            # Check if we need to expand more
            if "ENOUGH_IDENTIFIERS: TRUE" in phase1_response.upper() or matches.issubset(candidate_pool):
                enough_identifiers = True

        # ===== PHASE 2: FINAL SELECTION AND CLASSIFICATION =====
        # print("Here 2")
        # Prepare Phase 2 input
        all_reasoning_text = "\n\n".join(all_reasoning)
        all_candidates_text = "\n".join(sorted(candidate_pool))

        # print(sub_tree)

        # print(f"{all_candidates_text=}")
        
        phase2_response = await self.llm.acomplete(
            expanded_history,
            system_prompt=[FINALIZE_IDENTIFIERS_PROMPT.format(
                DATE=TODAY,
                SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES,
                EXPLORATION_STEPS=all_reasoning_text,
                ALL_CANDIDATES=all_candidates_text,
            )],
            stream=True,
            action_id="phase2.finalize"
        )
        
        # print(f"Phase 2 Final Selection: {phase2_response}")
        
        # Parse Phase 2 response
        summary = parse_blocks(phase2_response, block_word="Summary", multiple=False)
        context_identifiers = parse_blocks(phase2_response, block_word="Context Identifiers", multiple=False)
        modify_identifiers = parse_blocks(phase2_response, block_word="Modify Identifiers", multiple=False)
        
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
            "matches": list(matches),
            "context_identifiers": list(final_context),
            "modify_identifiers": self.tide._as_file_paths(list(final_modify)),
            "summary": summary,
            "all_reasoning": all_reasoning_text,
            "iteration_count": iteration_count
        }
    
    async def expand_history_if_needed(
        self,
        sufficient_context: bool,
        history_count: int,
    ) -> int:
        """
        Iteratively expand history window if initial assessment indicates more context is needed.
        
        Args:
            sufficient_context: Boolean indicating if context is sufficient
            history_count: Initial history count from operation mode extraction
        
        Returns:
            Final history count to use for processing
        
        Raises:
            ValueError: If extraction fails at any iteration
        """
        current_history_count = history_count
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        if not current_history_count:
            current_history_count += 1
        
        # If context is already sufficient, return early
        if sufficient_context:
            return current_history_count
        
        # Expand history iteratively
        while iteration < max_iterations and current_history_count < len(self.history):
            iteration += 1
            
            # Calculate window indices
            start_index = max(0, len(self.history) - current_history_count)
            end_index = len(self.history)
            current_window = self.history[start_index:end_index]
            latest_request = self.history[-1]  # Last interaction is the current request
            
            # Assess if current window has enough history
            response = await self.llm.acomplete(
                current_window,
                system_prompt=ASSESS_HISTORY_RELEVANCE_PROMPT.format(
                    START_INDEX=start_index,
                    END_INDEX=end_index,
                    TOTAL_INTERACTIONS=len(self.history),
                    CURRENT_WINDOW=str(current_window),
                    LATEST_REQUEST=str(latest_request)
                ),
               stream=False,
               action_id=f"expand_history.iteration_{iteration}"
            )
            
            # Extract HISTORY_SUFFICIENT
            history_sufficient_match = re.search(
                r'HISTORY_SUFFICIENT:\s*\[?(TRUE|FALSE)\]?',
                response
            )
            history_sufficient = (
                history_sufficient_match.group(1).lower() == 'true'
                if history_sufficient_match else False
            )
            
            # Extract REQUIRES_MORE_MESSAGES
            requires_more_match = re.search(
                r'REQUIRES_MORE_MESSAGES:\s*\[?(\d+)\]?',
                response
            )
            requires_more = int(requires_more_match.group(1)) if requires_more_match else 0
            
            # Validate extraction
            if history_sufficient_match is None or requires_more_match is None:
                raise ValueError(
                    f"Failed to extract relevance assessment fields at iteration {iteration}:\n{response}"
                )
            
            # If history is sufficient, we're done
            if history_sufficient:
                return current_history_count
            
            # If more messages are needed, expand the count
            if requires_more > 0:
                new_count = current_history_count + requires_more
                # Prevent exceeding total history
                if new_count > len(self.history):
                    new_count = len(self.history)
                
                current_history_count = new_count
            else:
                # No more messages required but not sufficient - use full history
                current_history_count = len(self.history)
        
        # Return final count (capped at total history length)
        return min(current_history_count, len(self.history))
    
    async def extract_operation_mode(
        self,
        cached_identifiers: str
    ) -> Tuple[str, bool, list]:
        """
        Extract operation mode, context sufficiency, and history count from LLM response.
        
        Args:
            llm: Language model instance with acomplete method
            history: Conversation history
            cached_identifiers: Code identifiers string
            system_prompt: System prompt template (DETERMINE_OPERATION_MODE_PROMPT)
        
        Returns:
            Tuple of (operation_mode, sufficient_context, history_count)
            - operation_mode: str [STANDARD|PLAN_STEPS|PATCH_CODE]
            - sufficient_context: bool
            - history_count: int
        
        Raises:
            ValueError: If required fields cannot be extracted from response
        """
        response = await self.llm.acomplete(
            self.history[-3:],
            system_prompt=DETERMINE_OPERATION_MODE_SYSTEM,
            prefix_prompt=DETERMINE_OPERATION_MODE_PROMPT.format(
                INTERACTION_COUNT=len(self.history),
                CODE_IDENTIFIERS=cached_identifiers
            ),
           stream=False,
           action_id="extract_operation_mode"
        )

        response_text = response.strip()
        # Extract and remove OPERATION_MODE
        operation_mode_match = re.search(r'OPERATION_MODE:\s*\[?(STANDARD|PLAN_STEPS|PATCH_CODE)\]?', response_text)
        operation_mode = operation_mode_match.group(1) if operation_mode_match else None
        if operation_mode_match:
            response_text = response_text.replace(operation_mode_match.group(0), '')

        # Extract and remove SUFFICIENT_CONTEXT
        sufficient_context_match = re.search(r'SUFFICIENT_CONTEXT:\s*\[?(TRUE|FALSE)\]?', response_text)
        sufficient_context = (
            sufficient_context_match.group(1).strip().upper() == "TRUE"
            if sufficient_context_match else None
        )
        if sufficient_context_match:
            response_text = response_text.replace(sufficient_context_match.group(0), '')

        # Extract and remove HISTORY_COUNT
        history_count_match = re.search(r'HISTORY_COUNT:\s*\[?(\d+)\]?', response_text)
        history_count = int(history_count_match.group(1)) if history_count_match else len(self.history)
        if history_count_match:
            response_text = response_text.replace(history_count_match.group(0), '')

        # Whatever remains (if anything) is the search query
        search_query = response_text.strip() or None

        # Validate extraction
        if operation_mode is None or sufficient_context is None:
            raise ValueError(f"Failed to extract required fields from response:\n{response}")

        final_history_count = await self.expand_history_if_needed(sufficient_context, min(history_count, int(history_count * 0.2)+1))
        expanded_history = self.history[-final_history_count:]

        return operation_mode, sufficient_context, expanded_history, search_query

    async def prepare_loop(self):
        await self.tide.check_for_updates(serialize=True, include_cached_ids=True)
        ### TODO this whole process neds to be integrated and updated from coetide directly for efficiency
        self._smart_code_search = SmartCodeSearch(
            documents={
                codefile.file_path: FILE_TEMPLATE.format(CONTENT=codefile.raw, FILENAME=codefile.file_path)
                for codefile in self.tide.codebase.root
            }
        )
        await self._smart_code_search.initialize_async()

    async def agent_loop(self, codeIdentifiers :Optional[List[str]]=None):
        TODAY = date.today()

        # Initialize the context identifier window if not present
        if self._context_identifier_window is None:
            self._context_identifier_window = []

        operation_mode = None
        codeContext = None
        prefilled_summary = None
        prefil_context = None
        if self._skip_context_retrieval:
            expanded_history = self.history[-1]
            await self.llm.logger_fn(REASONING_FINISHED)
        else:
            cached_identifiers = self._last_code_identifers
            if codeIdentifiers:
                for identifier in codeIdentifiers:
                    cached_identifiers.add(identifier)
            
            autocomplete = AutoComplete(self.tide.cached_ids)
            tasks = [
                self.extract_operation_mode(cached_identifiers),
                autocomplete.async_extract_words_from_text(self.history[-1] if self.history else "", max_matches_per_word=1),
                self.prepare_loop()
            ]
            operation_context_history_task, autocomplete_matches, _ = await asyncio.gather(*tasks)

            operation_mode, sufficient_context, expanded_history, search_query = operation_context_history_task
            direct_matches = autocomplete_matches["all_found_words"]
            print(f"{search_query=}")

            ### TODO super quick prompt here for operation mode
            ### needs more context based on cached identifiers or not
            ### needs more history or not, default is last 5 iteratinos
            if sufficient_context or set(direct_matches).issubset(cached_identifiers):
                codeIdentifiers = list(self._last_code_identifers)
                await self.llm.logger_fn(REASONING_FINISHED)

            elif self._direct_mode:
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
                await self.llm.logger_fn(REASONING_FINISHED)
                ### TODO create lightweight version to skip tree expansion and infer operationan_mode and expanded_history
            else:
                await self.llm.logger_fn(REASONING_STARTED)
                reasoning_output = await self.get_identifiers_two_phase(search_query, direct_matches, autocomplete, expanded_history, codeIdentifiers, TODAY)
                await self.llm.logger_fn(REASONING_FINISHED)
                print(json.dumps(reasoning_output, indent=4))

                codeIdentifiers = reasoning_output.get("context_identifiers", []) + reasoning_output.get("modify_identifiers", [])
                matches = reasoning_output.get("matches")
                prefilled_summary = reasoning_output.get("summary") 

            # --- End Unified Identifier Retrieval ---
            if codeIdentifiers:
                self._last_code_identifers = set(codeIdentifiers)
                codeContext = self.tide.get(codeIdentifiers, as_string=True)

            if not codeContext and not sufficient_context:
                codeContext = REPO_TREE_CONTEXT_PROMPT.format(REPO_TREE=self.tide.codebase.get_tree_view())
                # Use matches from the last message for README context
                readmeFile = self.tide.get(["README.md"] + (matches if 'matches' in locals() else []), as_string_list=True)
                if readmeFile:
                    codeContext = "\n".join([codeContext, README_CONTEXT_PROMPT.format(README=readmeFile)])
        self._last_code_context = codeContext
        await delete_file(self.patch_path)

        system_prompt = [
            AGENT_TIDE_SYSTEM_PROMPT.format(DATE=TODAY),
            CALMNESS_SYSTEM_PROMPT
        ]
        if operation_mode in self.OPERATIONS:
            system_prompt.insert(1, self.OPERATIONS.get(operation_mode))
        
        if prefilled_summary is not None:
            prefil_context = [
                PREFIX_SUMMARY_PROMPT.format(SUMMARY=prefilled_summary),
                codeContext
            ]
        elif codeContext:
            prefil_context = [codeContext]

        ### TODO get system prompt based on OEPRATION_MODE
        response = await self.llm.acomplete(
            expanded_history,
            system_prompt=system_prompt,
           prefix_prompt=prefil_context,
           action_id="agent_loop.main"
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
