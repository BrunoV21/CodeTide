from codetide import CodeTide
from ...mcp.tools.patch_code import file_exists, open_file, process_patch, remove_file, write_file
from .prompts import (
    AGENT_TIDE_SYSTEM_PROMPT, GET_CODE_IDENTIFIERS_SYSTEM_PROMPT, WRITE_PATCH_SYSTEM_PROMPT
)
from .consts import AGENT_TIDE_ASCII_ART
from .utils import parse_xml_content

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
from pydantic import BaseModel
from typing import Optional
from datetime import date
from tqdm import tqdm
import asyncio
import os

class AgentTide(BaseModel):
    llm :Llm
    tide :CodeTide
    history :Optional[list]=None

    @staticmethod
    def trim_messages(messages, tokenizer_fn, max_tokens :Optional[int]=None):
        max_tokens = max_tokens or int(os.environ.get("MAX_HISTORY_TOKENS", 1028))
        while messages and sum(len(tokenizer_fn(str(msg))) for msg in messages) > max_tokens:
            messages.pop(0)  # Remove from the beginning

    async def agent_loop(self):
        TODAY = date.today()
        repo_tree = self.tide.codebase.get_tree_view(
            include_modules=True,
            include_types=True
        )

        code_identifiers = await self.llm.acomplete(
            self.history,
            system_prompt=[GET_CODE_IDENTIFIERS_SYSTEM_PROMPT.format(DATE=TODAY)],
            prefix_prompt=repo_tree,
            stream=False,
            json_output=True
        )

        # diffPatches = None
        codeContext = None
        if code_identifiers:
            codeContext = self.tide.get(code_identifiers, as_string=True)

        

        response = await self.llm.acomplete(
            self.history,
            system_prompt=[
                AGENT_TIDE_SYSTEM_PROMPT.format(DATE=TODAY),
                WRITE_PATCH_SYSTEM_PROMPT.format(DATE=TODAY)
            ],
            prefix_prompt=codeContext
        )
        
        diffPatches = parse_xml_content(response, multiple=True)
        if diffPatches:
            diffPatches = [diffPatch.replace("\'", "'") for diffPatch in diffPatches]
            diffPatches = [diffPatch.replace('\"', '"') for diffPatch in diffPatches]
            for diffPatch in tqdm(diffPatches):
                process_patch(diffPatch, open_file, write_file, remove_file, file_exists)
            
            await self.tide.check_for_updates(serialize=True, include_cached_ids=True)

        # else:
        #     response = await self.llm.acomplete(
        #     self.history,
        #     system_prompt=[
        #         AGENT_TIDE_SYSTEM_PROMPT.format(DATE=TODAY),
        #         ASSISTANT_SYSTEM_PROMPT.format(DATE=TODAY)
        #     ],
        #     prefix_prompt=repo_tree
        # )
        
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
                    message = message.strip()

                    if not message:
                        continue

                except (EOFError, KeyboardInterrupt):
                    # prompt_toolkit raises EOFError on Ctrl-D and KeyboardInterrupt on Ctrl-C
                    _logger.logger.warning("\nExiting...")
                    break

                self.history.append(message)
                self.trim_messages(self.history, self.llm.tokenizer, max_tokens)

                print("Agent: Thinking...")
                await self.agent_loop()

        except asyncio.CancelledError:
            # This can happen if the event loop is shut down
            pass
        finally:
            _logger.logger.info("\nExited by user. Goodbye!")