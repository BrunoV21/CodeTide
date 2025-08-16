from codetide import CodeTide
from ...mcp.tools.patch_code import file_exists, open_file, process_patch, remove_file, write_file
from ...core.defaults import DEFAULT_STORAGE_PATH
from ...autocomplete import AutoComplete
from .models import Steps
from .prompts import (
    AGENT_TIDE_SYSTEM_PROMPT, GET_CODE_IDENTIFIERS_SYSTEM_PROMPT, STEPS_SYSTEM_PROMPT, WRITE_PATCH_SYSTEM_PROMPT
)
from .utils import parse_patch_blocks, parse_steps_markdown, tee_and_trim_patch
from .consts import AGENT_TIDE_ASCII_ART

try:
    from aicore.llm import Llm
    from aicore.logger import _logger
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' package. "
        "Install it with: pip install codetide[agents]"
    ) from e

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from pathlib import Path
from ulid import ulid
import asyncio
import os

class AgentTide(BaseModel):
    llm :Llm
    tide :CodeTide
    history :Optional[list]=None
    steps :Optional[Steps]=None
    session_id :str=Field(default_factory=ulid)

    @property
    def patch_path(self)->Path:
        if not os.path.exists(DEFAULT_STORAGE_PATH):
            os.makedirs(DEFAULT_STORAGE_PATH, exist_ok=True)
        
        return DEFAULT_STORAGE_PATH / f"{self.session_id}.bash"

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

        if codeIdentifiers is None:
            codeIdentifiers = await self.llm.acomplete(
                self.history,
                system_prompt=[GET_CODE_IDENTIFIERS_SYSTEM_PROMPT.format(DATE=TODAY)],
                prefix_prompt=repo_tree,
                stream=False,
                json_output=True
            )

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

            codeContext = self.tide.get(validatedCodeIdentifiers, as_string=True)

        async with tee_and_trim_patch(self.patch_path):
            response = await self.llm.acomplete(
                self.history,
                system_prompt=[
                    AGENT_TIDE_SYSTEM_PROMPT.format(DATE=TODAY),
                    STEPS_SYSTEM_PROMPT.format(DATE=TODAY, REPO_TREE=repo_tree),
                    WRITE_PATCH_SYSTEM_PROMPT.format(DATE=TODAY)
                ],
                prefix_prompt=codeContext
            )

        if os.path.exists(self.patch_path):
            process_patch(self.patch_path, open_file, write_file, remove_file, file_exists)
        
        steps = parse_steps_markdown(response)
        if steps:
            self.steps = Steps.from_steps(steps)

        diffPatches = parse_patch_blocks(response, multiple=True)
        if diffPatches:
            for patch in diffPatches:
                # TODO this deletes previouspatches from history to make sure changes are always focused on the latest version of the file
                response = response.replace(f"*** Begin Patch\n{patch}*** End Patch", "")

        self.history.append(response)

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

        _logger.logger.info(f"\n{AGENT_TIDE_ASCII_ART}\nReady to surf. Press ESC to exit.\n")
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