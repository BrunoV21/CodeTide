from aicore.logger import _logger

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession

from .utils import init_llm, trim_messages
from prompts.tide_system import AGENT_TIDE_SYSTEM_PROMPT
from .const import AGENT_TIDE_ASCII_ART



async def main(max_tokens: int = 48000):
    llm = init_llm()
    history = []

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
                _logger.warning("\nExiting...")
                break

            history.append(message)
            trim_messages(history, llm.tokenizer, max_tokens)

            print("Agent: Thinking...")
            response = await llm.acomplete(history, system_prompt=[AGENT_TIDE_SYSTEM_PROMPT], as_message_records=True)
            print(f"Agent: {response}")
            history.extend(response)

    except asyncio.CancelledError:
        # This can happen if the event loop is shut down
        pass
    finally:
        _logger.logger.info("\nExited by user. Goodbye!")

if __name__ == "__main__": 
    from dotenv import load_dotenv
    import asyncio

    load_dotenv()
    asyncio.run(main())

    ### TODO create instrucitons to calle ach tool in sequence with all logic hardcoded into framework
    # step one receives user req and returns one choice -> requreis reo tree strcuture - requires repo tree stctrure with code elements - requires nothing
    # aased on previous step fitler his
    # use history like basemodel with in built trim
    # if requries anthing get tree strucute (if tree structure already exists in history use it from cache) and decide which identifiers are required as context + pass them via checker and return matches
    # generate identifiers prompt requires tree structure 
    # use context to plan patch generation with reasoning of the cahnges with list of filepaths that will be changed and respective reasoning
    #  -> generate 100% certain ptch strcutre and call apply patch for each pathch!

