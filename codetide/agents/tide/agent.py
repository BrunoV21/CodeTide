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
    AGENT_TIDE_SYSTEM_PROMPT, ASSESS_HISTORY_RELEVANCE_PROMPT, CALMNESS_SYSTEM_PROMPT, 
    CMD_BRAINSTORM_PROMPT, CMD_CODE_REVIEW_PROMPT, CMD_TRIGGER_PLANNING_STEPS, 
    CMD_WRITE_TESTS_PROMPT, DETERMINE_OPERATION_MODE_PROMPT, DETERMINE_OPERATION_MODE_SYSTEM, 
    FINALIZE_IDENTIFIERS_PROMPT, GATHER_CANDIDATES_PREFIX, GATHER_CANDIDATES_SYSTEM, 
    PREFIX_SUMMARY_PROMPT, README_CONTEXT_PROMPT, REJECT_PATCH_FEEDBACK_TEMPLATE,
    REPO_TREE_CONTEXT_PROMPT, STAGED_DIFFS_TEMPLATE, STEPS_SYSTEM_PROMPT, WRITE_PATCH_SYSTEM_PROMPT
)
from .defaults import DEFAULT_MAX_HISTORY_TOKENS
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
from typing import Dict, List, Optional, Set, Tuple
from typing_extensions import Self
from functools import partial
from datetime import date
from pathlib import Path
from ulid import ulid
import asyncio
import pygit2
import os

# ============================================================================
# Constants
# ============================================================================

FILE_TEMPLATE = """{FILENAME}

{CONTENT}
"""

# Default configuration values
DEFAULT_CONTEXT_WINDOW_SIZE = 3
DEFAULT_MAX_EXPANSION_ITERATIONS = 10
DEFAULT_MAX_CANDIDATE_ITERATIONS = 3
DEFAULT_SEARCH_TOP_K = 15

# Operation modes
OPERATION_MODE_STANDARD = "STANDARD"
OPERATION_MODE_PLAN_STEPS = "PLAN_STEPS"
OPERATION_MODE_PATCH_CODE = "PATCH_CODE"

# Commands to filter from history
COMMAND_PROMPTS = [
    CMD_TRIGGER_PLANNING_STEPS,
    CMD_WRITE_TESTS_PROMPT,
    CMD_BRAINSTORM_PROMPT,
    CMD_CODE_REVIEW_PROMPT
]


# ============================================================================
# Data Classes for Identifier Resolution
# ============================================================================

class IdentifierResolutionResult(BaseModel):
    """Result of the two-phase identifier resolution process."""
    matches: List[str]
    context_identifiers: List[str]
    modify_identifiers: List[str]
    summary: Optional[str]
    all_reasoning: str
    iteration_count: int


class OperationModeResult(BaseModel):
    """Result of operation mode extraction."""
    operation_mode: str
    sufficient_context: bool
    expanded_history: list
    search_query: Optional[str]
    is_new_topic: Optional[bool]=None
    topic_title: Optional[str]=None


# ============================================================================
# Helper Classes
# ============================================================================

class GitOperations:
    """Handles Git-related operations."""
    
    def __init__(self, repo: pygit2.Repository, rootpath: Path):
        self.repo = repo
        self.rootpath = rootpath
    
    def has_staged_changes(self) -> bool:
        """Check if there are staged changes in the repository."""
        status = self.repo.status()
        result = any([
            file_status == pygit2.GIT_STATUS_INDEX_MODIFIED 
            for file_status in status.values()
        ])
        _logger.logger.debug(f"has_staged_changes result={result}")
        return result
    
    async def get_staged_diff(self) -> str:
        """Get the diff of staged changes."""
        if not Path(self.rootpath).is_dir():
            raise FileNotFoundError(f"Directory not found: {self.rootpath}")
        
        process = await asyncio.create_subprocess_exec(
            'git', 'diff', '--staged',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.rootpath
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Git command failed: {stderr.decode().strip()}")
        
        return stdout.decode()
    
    async def stage_files(self, changed_paths: List[str]) -> str:
        """Stage files and return the diff."""
        index = self.repo.index
        
        if not self.has_staged_changes():
            for path in changed_paths:
                index.add(str(Path(path)))
            index.write()
        
        staged_diff = await self.get_staged_diff()
        staged_diff = staged_diff.strip()
        
        return staged_diff if staged_diff else (
            "No files were staged. Nothing to commit. "
            "Tell the user to request some changes so there is something to commit"
        )
    
    def commit(self, message: str) -> pygit2.Commit:
        """
        Commit all staged files with the given message.
        
        Args:
            message: Commit message
        
        Returns:
            The created commit object
        
        Raises:
            ValueError: If no files are staged for commit
            Exception: For other git-related errors
        """
        try:
            config = self.repo.config
            author_name = config._get('user.name')[1].value or 'Unknown Author'
            author_email = config._get('user.email')[1].value or 'unknown@example.com'
            
            author = pygit2.Signature(author_name, author_email)
            committer = author
            
            tree = self.repo.index.write_tree()
            parents = [self.repo.head.target] if self.repo.head else []
            
            commit_oid = self.repo.create_commit(
                'HEAD',
                author,
                committer,
                message,
                tree,
                parents
            )
            
            self.repo.index.write()
            return self.repo[commit_oid]
            
        except pygit2.GitError as e:
            raise Exception(f"Git error: {e}")
        except KeyError as e:
            raise Exception(f"Configuration error: {e}")


class IdentifierResolver:
    """Handles the two-phase identifier resolution process."""
    
    def __init__(
        self,
        llm: Llm,
        tide: CodeTide,
        smart_code_search: SmartCodeSearch,
        autocomplete: AutoComplete
    ):
        self.llm = llm
        self.tide = tide
        self.smart_code_search = smart_code_search
        self.autocomplete = autocomplete
    
    @staticmethod
    def extract_candidate_identifiers(reasoning: str) -> List[str]:
        """Extract candidate identifiers from reasoning text using regex."""
        pattern = r"^\s*-\s*(.+?)$"
        matches = re.findall(pattern, reasoning, re.MULTILINE)
        return [match.strip() for match in matches]
    
    def validate_identifier(self, identifier: str) -> Optional[str]:
        """Validate and potentially correct an identifier."""
        result = self.autocomplete.validate_code_identifier(identifier)
        if result.get("is_valid"):
            return identifier
        elif result.get("matching_identifiers"):
            return result.get("matching_identifiers")[0]
        return None
    
    async def gather_candidates(
        self,
        search_query: str,
        direct_matches: Set[str],
        expanded_history: list,
        context_window: Set[str],
        today: str
    ) -> Tuple[Set[str], List[str], Optional[str]]:
        """
        Phase 1: Gather candidate identifiers through iterative search and expansion.
        
        Returns:
            Tuple of (candidate_pool, all_reasoning, final_search_query)
        """
        candidate_pool = set()
        all_reasoning = []
        iteration_count = 0
        previous_response = None
        
        while iteration_count < DEFAULT_MAX_CANDIDATE_ITERATIONS:
            iteration_count += 1
            
            # Search for relevant identifiers
            search_results = await self.smart_code_search.search_smart(
                search_query,
                use_variations=False,
                top_k=DEFAULT_SEARCH_TOP_K
            )
            identifiers_from_search = {result[0] for result in search_results}
            
            # Early exit if all direct matches found
            # if identifiers_from_search.issubset(direct_matches):
            #     candidate_pool = identifiers_from_search
            #     print("All matches found in identifiers from search")
            #     break
            
            # Build filtered tree view
            candidates_to_filter = self.tide._as_file_paths(list(identifiers_from_search))
            self.tide.codebase._build_tree_dict(candidates_to_filter, slim=True)
            sub_tree = self.tide.codebase.get_tree_view()
            
            # Prepare prompts
            prefix_prompt = [
                GATHER_CANDIDATES_PREFIX.format(
                    LAST_SEARCH_QUERY=search_query,
                    ITERATION_COUNT=iteration_count,
                    ACCUMULATED_CONTEXT=context_window,
                    DIRECT_MATCHES=direct_matches,
                    SEARCH_CANDIDATES=identifiers_from_search,
                    REPO_TREE=sub_tree
                )
            ]
            if previous_response:
                prefix_prompt.insert(0, previous_response)
            
            # Get LLM response
            phase1_response = await self.llm.acomplete(
                expanded_history,
                system_prompt=GATHER_CANDIDATES_SYSTEM.format(
                    DATE=today,
                    SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES
                ),
                prefix_prompt=prefix_prompt,
                stream=True,
                action_id=f"phase_1.{iteration_count}"
            )
            previous_response = phase1_response
            
            # Parse response
            reasoning_blocks = parse_blocks(phase1_response, block_word="Reasoning", multiple=True)
            search_query = parse_blocks(phase1_response, block_word="Search Query", multiple=False)
            
            # Extract candidates from reasoning
            if reasoning_blocks:
                all_reasoning.extend(reasoning_blocks)
                for reasoning in reasoning_blocks:
                    candidate_matches = self.extract_candidate_identifiers(reasoning)
                    for match in candidate_matches:
                        if validated := self.validate_identifier(match):
                            candidate_pool.add(validated)
            
            # Check if we have enough identifiers
            if ("ENOUGH_IDENTIFIERS: TRUE" in phase1_response.upper() or 
                direct_matches.issubset(candidate_pool)):
                break
        
        return candidate_pool, all_reasoning, search_query
    
    async def finalize_identifiers(
        self,
        candidate_pool: Set[str],
        all_reasoning: List[str],
        expanded_history: list,
        today: str
    ) -> Tuple[Set[str], Set[str], Optional[str]]:
        """
        Phase 2: Classify candidates into context and modify identifiers.
        
        Returns:
            Tuple of (context_identifiers, modify_identifiers, summary)
        """
        all_reasoning_text = "\n\n".join(all_reasoning)
        all_candidates_text = "\n".join(sorted(candidate_pool))
        
        phase2_response = await self.llm.acomplete(
            expanded_history,
            system_prompt=[FINALIZE_IDENTIFIERS_PROMPT.format(
                DATE=today,
                SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES,
                EXPLORATION_STEPS=all_reasoning_text,
                ALL_CANDIDATES=all_candidates_text,
            )],
            stream=True,
            action_id="phase2.finalize"
        )
        
        # Parse results
        summary = parse_blocks(phase2_response, block_word="Summary", multiple=False)
        context_identifiers = parse_blocks(
            phase2_response,
            block_word="Context Identifiers",
            multiple=False
        )
        modify_identifiers = parse_blocks(
            phase2_response,
            block_word="Modify Identifiers",
            multiple=False
        )
        
        # Process and validate identifiers
        final_context = set()
        final_modify = set()
        
        if context_identifiers:
            for ident in context_identifiers.strip().split('\n'):
                if validated := self.validate_identifier(ident.strip()):
                    final_context.add(validated)
        
        if modify_identifiers:
            for ident in modify_identifiers.strip().split('\n'):
                if validated := self.validate_identifier(ident.strip()):
                    final_modify.add(validated)
        
        return final_context, final_modify, summary
    
    async def resolve_identifiers(
        self,
        search_query: Optional[str],
        direct_matches: List[str],
        expanded_history: list,
        context_window: Set[str],
        today: str
    ) -> IdentifierResolutionResult:
        """
        Execute the full two-phase identifier resolution process.
        
        Args:
            search_query: Initial search query (if None, uses last history item)
            direct_matches: Identifiers directly matched from autocomplete
            expanded_history: Conversation history to use
            context_window: Set of identifiers from recent context
            today: Current date string
        
        Returns:
            IdentifierResolutionResult with all resolved identifiers
        """
        if search_query is None:
            search_query = expanded_history[-1]
        
        # Phase 1: Gather candidates
        candidate_pool, all_reasoning, _ = await self.gather_candidates(
            search_query,
            set(direct_matches),
            expanded_history,
            context_window,
            today
        )
        
        # Phase 2: Finalize classification
        context_ids, modify_ids, summary = await self.finalize_identifiers(
            candidate_pool,
            all_reasoning,
            expanded_history,
            today
        )
        
        return IdentifierResolutionResult(
            matches=direct_matches,
            context_identifiers=list(context_ids),
            modify_identifiers=self.tide._as_file_paths(list(modify_ids)),
            summary=summary,
            all_reasoning="\n\n".join(all_reasoning),
            iteration_count=len(all_reasoning)
        )


class HistoryManager:
    """Manages conversation history expansion and relevance assessment."""
    
    def __init__(self, llm: Llm):
        self.llm = llm
    
    @staticmethod
    def trim_messages(messages: list, tokenizer_fn, max_tokens: Optional[int] = None):
        """Trim messages to fit within token budget."""
        max_tokens = max_tokens or int(
            os.environ.get("MAX_HISTORY_TOKENS", DEFAULT_MAX_HISTORY_TOKENS)
        )
        while messages and sum(len(tokenizer_fn(str(msg))) for msg in messages) > max_tokens:
            messages.pop(0)
    
    async def expand_history_if_needed(
        self,
        history: list,
        sufficient_context: bool,
        initial_history_count: int,
    ) -> int:
        """
        Iteratively expand history window if more context is needed.
        
        Args:
            history: Full conversation history
            sufficient_context: Whether initial context is sufficient
            initial_history_count: Starting history count
        
        Returns:
            Final history count to use
        """
        current_count = max(initial_history_count, 1)
        
        if sufficient_context:
            return current_count
        
        iteration = 0
        while iteration < DEFAULT_MAX_EXPANSION_ITERATIONS and current_count < len(history):
            iteration += 1
            
            start_index = max(0, len(history) - current_count)
            end_index = len(history)
            current_window = history[start_index:end_index]
            latest_request = history[-1]
            
            response = await self.llm.acomplete(
                current_window,
                system_prompt=ASSESS_HISTORY_RELEVANCE_PROMPT.format(
                    START_INDEX=start_index,
                    END_INDEX=end_index,
                    TOTAL_INTERACTIONS=len(history),
                    CURRENT_WINDOW=str(current_window),
                    LATEST_REQUEST=str(latest_request)
                ),
                stream=False,
                action_id=f"expand_history.iteration_{iteration}"
            )
            
            # Extract assessment fields
            history_sufficient = self._extract_boolean_field(response, "HISTORY_SUFFICIENT")
            requires_more = self._extract_integer_field(response, "REQUIRES_MORE_MESSAGES")
            
            if history_sufficient is None or requires_more is None:
                raise ValueError(
                    f"Failed to extract relevance assessment at iteration {iteration}:\n{response}"
                )
            
            if history_sufficient:
                return current_count
            
            if requires_more > 0:
                current_count = min(current_count + requires_more, len(history))
            else:
                current_count = len(history)
        
        return min(current_count, len(history))
    
    @staticmethod
    def _extract_boolean_field(text: str, field_name: str) -> Optional[bool]:
        """Extract a boolean field from response text."""
        match = re.search(rf'{field_name}:\s*\[?(TRUE|FALSE)\]?', text)
        if match:
            return match.group(1).upper() == "TRUE"
        return None
    
    @staticmethod
    def _extract_integer_field(text: str, field_name: str) -> Optional[int]:
        """Extract an integer field from response text."""
        match = re.search(rf'{field_name}:\s*\[?(\d+)\]?', text)
        if match:
            return int(match.group(1))
        return None


# ============================================================================
# Main Agent Class
# ============================================================================

class AgentTide(BaseModel):
    """Main agent for autonomous code editing and task execution."""
    
    llm: Llm
    tide: CodeTide
    history: Optional[list] = None
    steps: Optional[Steps] = None
    session_id: str = Field(default_factory=ulid)
    changed_paths: List[str] = Field(default_factory=list)
    request_human_confirmation: bool = False
    
    context_identifiers: Optional[List[str]] = None
    modify_identifiers: Optional[List[str]] = None
    reasoning: Optional[str] = None
    
    # Internal state
    _skip_context_retrieval: bool = False
    _last_code_identifiers: Optional[Set[str]] = set()
    _last_code_context: Optional[str] = None
    _has_patch: bool = False
    _direct_mode: bool = False
    _smart_code_search: Optional[SmartCodeSearch] = None
    _context_identifier_window: Optional[list] = None
    _git_operations: Optional[GitOperations] = None
    _history_manager: Optional[HistoryManager] = None
    
    # Configuration
    CONTEXT_WINDOW_SIZE: int = DEFAULT_CONTEXT_WINDOW_SIZE
    
    OPERATIONS: Dict[str, str] = {
        OPERATION_MODE_PLAN_STEPS: STEPS_SYSTEM_PROMPT,
        OPERATION_MODE_PATCH_CODE: WRITE_PATCH_SYSTEM_PROMPT
    }
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    @model_validator(mode="after")
    def initialize_components(self) -> Self:
        """Initialize helper components and configure logging."""
        self.llm.logger_fn = partial(
            custom_logger_fn,
            session_id=self.session_id,
            filepath=self.patch_path
        )
        self._git_operations = GitOperations(self.tide.repo, self.tide.rootpath)
        self._history_manager = HistoryManager(self.llm)
        return self
    
    @property
    def patch_path(self) -> Path:
        """Get the path for storing patches."""
        storage_dir = self.tide.rootpath / DEFAULT_STORAGE_PATH
        storage_dir.mkdir(exist_ok=True)
        return storage_dir / f"{self.session_id}.bash"
    
    # ========================================================================
    # Patch Management
    # ========================================================================
    
    def approve(self):
        """Approve and apply the current patch."""
        self._has_patch = False
        if not os.path.exists(self.patch_path):
            return
        
        changed_paths = process_patch(
            self.patch_path,
            open_file,
            write_file,
            remove_file,
            file_exists,
            root_path=self.tide.rootpath
        )
        self.changed_paths.extend(changed_paths)
        
        # Clean up patch blocks from history
        self._remove_patch_blocks_from_history()
    
    def reject(self, feedback: str):
        """Reject the current patch with feedback."""
        self._has_patch = False
        self.history.append(REJECT_PATCH_FEEDBACK_TEMPLATE.format(FEEDBACK=feedback))
    
    def _remove_patch_blocks_from_history(self):
        """Remove patch blocks from the last response in history."""
        if not self.history:
            return
        
        previous_response = self.history[-1]
        diff_patches = parse_patch_blocks(previous_response, multiple=True)
        
        if diff_patches:
            for patch in diff_patches:
                previous_response = previous_response.replace(
                    f"*** Begin Patch\n{patch}*** End Patch",
                    ""
                )
            self.history[-1] = previous_response
    
    # ========================================================================
    # History Management
    # ========================================================================
    
    def _clean_history(self):
        """Convert history messages to plain strings."""
        for i, message in enumerate(self.history):
            if isinstance(message, dict):
                self.history[i] = message.get("content", "")
    
    def _filter_command_prompts_from_history(self, history: list) -> str:
        """Remove command prompts from history string."""
        history_str = "\n\n".join(history)
        for cmd_prompt in COMMAND_PROMPTS:
            history_str = history_str.replace(cmd_prompt, "")
        return history_str
    
    # ========================================================================
    # Operation Mode and Context Extraction
    # ========================================================================
    
    async def extract_operation_mode(
        self,
        cached_identifiers: Set[str]
    ) -> OperationModeResult:
        """
        Extract operation mode, context sufficiency, and relevant history.
        
        Returns:
            OperationModeResult with all extracted information
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
        
        # Extract fields from response
        operation_mode = self._extract_field(response, "OPERATION_MODE", "STANDARD")
        sufficient_context = self._extract_field(response, "SUFFICIENT_CONTEXT", "FALSE")
        history_count = self._extract_field(response, "HISTORY_COUNT", "2")
        is_new_topic = self._extract_field(response, "IS_NEW_TOPIC")
        topic_title = self._extract_field(response, "TOPIC_TITLE")
        search_query = self._extract_field(response, "SEARCH_QUERY")
        
        # Validate extraction
        if operation_mode is None or sufficient_context is None:
            raise ValueError(f"Failed to extract required fields from response:\n{response}")
        
        # Parse values
        operation_mode = operation_mode.strip()
        sufficient_context = sufficient_context.strip().upper() == "TRUE"
        history_count = int(history_count) if history_count else len(self.history)
        is_new_topic = is_new_topic.strip().upper() == "TRUE" if is_new_topic else False
        topic_title = topic_title.strip() if topic_title and topic_title.strip().lower() != "null" else None
        search_query = search_query.strip() if search_query and search_query.strip().upper() != "NO" else None
        
        # Expand history if needed
        final_history_count = await self._history_manager.expand_history_if_needed(
            self.history,
            sufficient_context,
            min(history_count, int(history_count * 0.2) + 1)
        )
        expanded_history = self.history[-final_history_count:]
        
        return OperationModeResult(
            operation_mode=operation_mode,
            sufficient_context=sufficient_context,
            expanded_history=expanded_history,
            search_query=search_query,
            is_new_topic=is_new_topic,
            topic_title=topic_title
        )
    
    @staticmethod
    def _extract_field(text: str, field_name: str, default :Optional[str]=None) -> Optional[str]:
        """Extract a field value from response text."""
        pattern = rf'{field_name}:\s*\[?([^\]]+?)\]?(?:\n|$)'
        match = re.search(pattern, text)
        return match.group(1) if match else default
    
    @staticmethod
    def _extract_search_query(response: str) -> Optional[str]:
        """Extract search query by removing known fields from response."""
        cleaned = response
        for field in ["OPERATION_MODE", "SUFFICIENT_CONTEXT", "HISTORY_COUNT"]:
            cleaned = re.sub(rf'{field}:\s*\[?[^\]]+?\]?', '', cleaned)
        search_query = cleaned.strip()
        return search_query if search_query else None
    
    # ========================================================================
    # Context Building
    # ========================================================================
    
    async def prepare_search_infrastructure(self):
        """Initialize search components and update codebase."""
        await self.tide.check_for_updates(serialize=True, include_cached_ids=True)
        
        self._smart_code_search = SmartCodeSearch(
            documents={
                codefile.file_path: FILE_TEMPLATE.format(
                    CONTENT=codefile.raw,
                    FILENAME=codefile.file_path
                )
                for codefile in self.tide.codebase.root
            }
        )
        await self._smart_code_search.initialize_async()
    
    async def get_repo_tree_from_user_prompt(
        self,
        history: list,
        include_modules: bool = False,
        expand_paths: Optional[List[str]] = None
    ) -> str:
        """Get a tree view of the repository based on user prompt context."""
        self._filter_command_prompts_from_history(history)
        self.tide.codebase._build_tree_dict(expand_paths)
        
        return self.tide.codebase.get_tree_view(
            include_modules=include_modules,
            include_types=True
        )
    
    def _build_code_context(
        self,
        code_identifiers: Optional[List[str]],
        matches: Optional[List[str]] = None
    ) -> Optional[str]:
        """Build code context from identifiers, falling back to tree view if needed."""
        if code_identifiers:
            ### TODO prefix this into:
            #  As you answer the user's questions, you can use the following context:
            return self.tide.get(code_identifiers, as_string=True)
        
        # Fallback to tree view and README
        tree_view = REPO_TREE_CONTEXT_PROMPT.format(
            REPO_TREE=self.tide.codebase.get_tree_view()
        )
        
        readme_files = self.tide.get(
            ["README.md"] + (matches or []),
            as_string_list=True
        )
        
        if readme_files:
            return "\n".join([
                tree_view,
                README_CONTEXT_PROMPT.format(README=readme_files)
            ])
        
        return tree_view
    
    # ========================================================================
    # Identifier Resolution
    # ========================================================================
    
    async def resolve_identifiers_for_request(
        self,
        operation_result: OperationModeResult,
        autocomplete: AutoComplete,
        today: str
    ) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
        """
        Resolve code identifiers based on operation mode and context.
        
        Returns:
            Tuple of (code_identifiers, code_context, prefilled_summary)
        """
        # Initialize context window if needed
        if self._context_identifier_window is None:
            self._context_identifier_window = []
        
        expanded_history = operation_result.expanded_history
        sufficient_context = operation_result.sufficient_context
        search_query = operation_result.search_query
        
        # Extract direct matches from last message
        autocomplete_result = await autocomplete.async_extract_words_from_text(
            self.history[-1] if self.history else "",
            max_matches_per_word=1,
            timeout=30
        )
        direct_matches = autocomplete_result["all_found_words"]
        
        print(f"operation_mode={operation_result.operation_mode}")
        print(f"direct_matches={direct_matches}")
        print(f"search_query={search_query}")
        print(f"sufficient_context={sufficient_context}")
        
        # Case 1: Sufficient context with cached identifiers
        if sufficient_context or (
            direct_matches and set(direct_matches).issubset(self._last_code_identifiers)
        ):
            await self.llm.logger_fn(REASONING_FINISHED)
            return list(self._last_code_identifiers), None, None
        
        # Case 2: Direct mode - use only exact matches
        if self._direct_mode:
            self.context_identifiers = None
            self.modify_identifiers = self.tide._as_file_paths(direct_matches)
            self._update_context_window(direct_matches)
            self._direct_mode = False
            await self.llm.logger_fn(REASONING_FINISHED)
            return self.modify_identifiers, None, None
        
        # Case 3: Full two-phase identifier resolution
        print("Entering two-phase identifier resolution")
        await self.llm.logger_fn(REASONING_STARTED)
        
        resolver = IdentifierResolver(
            self.llm,
            self.tide,
            self._smart_code_search,
            autocomplete
        )
        
        context_window = set()
        if self._context_identifier_window:
            context_window = set().union(*self._context_identifier_window)
        
        resolution_result = await resolver.resolve_identifiers(
            search_query,
            direct_matches,
            expanded_history,
            context_window,
            today
        )
        
        await self.llm.logger_fn(REASONING_FINISHED)
        print(json.dumps(resolution_result.dict(), indent=4))
        
        code_identifiers = (
            resolution_result.context_identifiers +
            resolution_result.modify_identifiers
        )
        self._update_context_window(resolution_result.matches)
        
        return code_identifiers, None, resolution_result.summary
    
    def _update_context_window(self, new_identifiers: List[str]):
        """Update the rolling window of context identifiers."""
        self._context_identifier_window.append(set(new_identifiers))
        if len(self._context_identifier_window) > self.CONTEXT_WINDOW_SIZE:
            self._context_identifier_window.pop(0)
    
    # ========================================================================
    # Main Agent Loop
    # ========================================================================
    
    async def agent_loop(self, code_identifiers: Optional[List[str]] = None):
        """
        Main agent execution loop.
        
        Args:
            code_identifiers: Optional list of code identifiers to use directly
        """
        today = date.today()
        operation_mode = None
        code_context = None
        prefilled_summary = None
        
        # Skip context retrieval if flagged
        if self._skip_context_retrieval:
            expanded_history = [self.history[-1]]
            await self.llm.logger_fn(REASONING_FINISHED)
        else:
            # Prepare autocomplete and search infrastructure
            cached_identifiers = self._last_code_identifiers.copy()
            if code_identifiers:
                cached_identifiers.update(code_identifiers)
            
            autocomplete = AutoComplete(
                self.tide.cached_ids,
                mapped_words=self.tide.filenames_mapped
            )
            
            # Run preparation and mode extraction in parallel
            operation_result, _ = await asyncio.gather(
                self.extract_operation_mode(cached_identifiers),
                self.prepare_search_infrastructure()
            )
            
            operation_mode = operation_result.operation_mode
            expanded_history = operation_result.expanded_history
            
            # Resolve identifiers and build context
            code_identifiers, _, prefilled_summary = await self.resolve_identifiers_for_request(
                operation_result,
                autocomplete,
                str(today)
            )
            
            # Build code context
            if code_identifiers:
                self._last_code_identifiers = set(code_identifiers)
                code_context = self.tide.get(code_identifiers, as_string=True)
            
            if not code_context and not operation_result.sufficient_context:
                code_context = self._build_code_context(code_identifiers)
        
        # Store context for potential reuse
        self._last_code_context = code_context
        await delete_file(self.patch_path)
        
        # Build system prompt
        system_prompt = [
            AGENT_TIDE_SYSTEM_PROMPT.format(DATE=today),
            CALMNESS_SYSTEM_PROMPT
        ]
        if operation_mode in self.OPERATIONS:
            system_prompt.insert(1, self.OPERATIONS[operation_mode])
        
        # Build prefix prompt
        prefix_prompt = None
        if prefilled_summary:
            prefix_prompt = [PREFIX_SUMMARY_PROMPT.format(SUMMARY=prefilled_summary)]
        
        # Generate response
        history_with_context = (
            expanded_history[:-1] + [code_context] + expanded_history[-1:] if code_context else expanded_history
        )
        
        response = await self.llm.acomplete(
            history_with_context,
            system_prompt=system_prompt,
            prefix_prompt=prefix_prompt,
            action_id="agent_loop.main"
        )
        
        # Process response
        await self._process_agent_response(response)
        
        self.history.append(response)
        await self.llm.logger_fn(ROUND_FINISHED)
    
    async def _process_agent_response(self, response: str):
        """Process the agent's response for patches, commits, and steps."""
        await trim_to_patch_section(self.patch_path)
        
        # Handle patches
        if not self.request_human_confirmation:
            self.approve()
        
        # Handle commits
        commit_message = parse_blocks(response, multiple=False, block_word="Commit")
        if commit_message:
            self.commit(commit_message)
        
        # Handle steps
        steps = parse_steps_markdown(response)
        if steps:
            self.steps = Steps.from_steps(steps)
        
        # Track patches for human confirmation
        diff_patches = parse_patch_blocks(response, multiple=True)
        if diff_patches:
            if self.request_human_confirmation:
                self._has_patch = True
            else:
                # Remove patch blocks from response to keep history clean
                for patch in diff_patches:
                    response = response.replace(
                        f"*** Begin Patch\n{patch}*** End Patch",
                        ""
                    )
    
    # ========================================================================
    # Git Operations
    # ========================================================================
    
    async def prepare_commit(self) -> str:
        """Stage files and prepare commit context."""
        staged_diff = await self._git_operations.stage_files(self.changed_paths)
        self.changed_paths = []
        self._skip_context_retrieval = True
        return STAGED_DIFFS_TEMPLATE.format(diffs=staged_diff)
    
    def commit(self, message: str):
        """Commit staged changes with the given message."""
        try:
            self._git_operations.commit(message)
        finally:
            self._skip_context_retrieval = False
    
    # ========================================================================
    # Command Handling
    # ========================================================================
    
    async def _handle_commands(self, command: str) -> str:
        """
        Handle special commands.
        
        Args:
            command: Command to execute
        
        Returns:
            Context string resulting from command execution
        """
        if command == "commit":
            return await self.prepare_commit()
        elif command == "direct_mode":
            self._direct_mode = True
            return ""
        return ""
    
    # ========================================================================
    # Interactive Loop
    # ========================================================================
    
    async def run(self, max_tokens: int = 48000):
        """
        Run the interactive agent loop.
        
        Args:
            max_tokens: Maximum tokens to keep in history
        """
        if self.history is None:
            self.history = []
        
        # Set up key bindings
        bindings = KeyBindings()
        
        @bindings.add('escape')
        def exit_handler(event):
            """Exit on Escape key."""
            _logger.logger.warning("Escape key pressed — exiting...")
            event.app.exit()
        
        session = PromptSession(key_bindings=bindings)
        
        print(f"\n{AGENT_TIDE_ASCII_ART}\n")
        _logger.logger.info("Ready to surf. Press ESC to exit.")
        
        try:
            while True:
                try:
                    message = await session.prompt_async("You: ")
                    if message is None:
                        break
                    
                    message = message.strip()
                    if not message:
                        continue
                
                except (EOFError, KeyboardInterrupt):
                    _logger.logger.warning("Exiting...")
                    break
                
                self.history.append(message)
                self._history_manager.trim_messages(
                    self.history,
                    self.llm.tokenizer,
                    max_tokens
                )
                
                print("Agent: Thinking...")
                await self.agent_loop()
        
        except asyncio.CancelledError:
            pass
        finally:
            _logger.logger.info("Exited by user. Goodbye!")
