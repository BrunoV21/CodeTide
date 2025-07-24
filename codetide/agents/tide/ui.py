try:
    from aicore.config import Config
    from aicore.llm import Llm, LlmConfig
    from aicore.logger import _logger
    from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN#, REASONING_START_TOKEN, REASONING_STOP_TOKEN
    import chainlit as cl
    from chainlit.cli import run_chainlit
    from chainlit.input_widget import Slider, TextInput
except ImportError as e:
    raise ImportError(
        "The 'codetide.agents' module requires the 'aicore' and 'chainlit' packages. "
        "Install it with: pip install codetide[agents-ui]"
    ) from e

from codetide.agents.tide.defaults import DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH
from pathlib import Path
import asyncio
import os

class LlmObj(object):
    def __init__(self, project_path: Path=Path("./")):
        self.project_path :Path = Path(project_path)
        self.config_path = os.getenv("AGENT_TIDE_CONFIG_PATH", DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH)
        config = Config.from_yaml(self.project_path / self.config_path)
        self.llm_config :LlmConfig = config.llm
        self.llm = Llm.from_config( self.llm_config)

    def settings(self):
        return [
        TextInput(
            id="provider",
            label="Provider",
            initial=self.llm_config.provider
        ),
        TextInput(
            id="Model",
            label="Llm",
            initial=self.llm_config.model
        ),
        TextInput(
            id="Api Key",
            label="Api Key",
            initial=self.llm_config.api_key
        ),
        TextInput(
            id="Base Url",
            label="Base Url",
            initial=self.llm_config.base_url
        ),
        Slider(
            id="Temperature",
            label="Temperature",
            initial=self.llm_config.temperature,
            min=0,
            max=1,
            step=0.1,
        ),
        Slider(
            id="Max Tokens",
            label="Max Tokens",
            initial=self.llm_config.max_tokens,
            min=4096,
            max=self.llm_config.max_tokens,
            step=4096,
        )
    ]

@cl.on_settings_update
async def setup_llm_config(settings):
    ### update self.llm_config according to settings
    llmObj :LlmObj = cl.user_session.get("LlmObj")
    await cl.ChatSettings(llmObj.settings()).send()
    ### update settings on config_path and serialize
    llmObj.llm = Llm.from_config(llmObj.llm_config)

@cl.on_chat_start
async def start_chat():
    llmObj = LlmObj(os.getenv("AGENT_TIDE_PROJECT_PATH", "./"))
    cl.user_session.set("LlmObj", llmObj)
    await cl.ChatSettings(llmObj.settings()).send()

async def run_concurrent_tasks(llm, message):
    asyncio.create_task(llm.acomplete(message))
    asyncio.create_task(_logger.distribute())
    # Stream logger output while LLM is running
    while True:        
        async for chunk in _logger.get_session_logs(llm.session_id):
            yield chunk  # Yield each chunk directly
            
@cl.on_message
async def main(message: cl.Message):
    # llm = cl.user_session.get("llm")
    # if not llm.config.api_key:
    #     while True:
    #         api_key_msg = await cl.AskUserMessage(content="Please provide a valid api_key", timeout=10).send()
    #         if api_key_msg:
    #             api_key = api_key_msg.get("output")
    #             valid = check_openai_api_key(api_key)
    #             if valid:
    #                 await cl.Message(
    #                     content=f"Config updated with key.",
    #                 ).send()
    #                 llm.config.api_key = api_key
    #                 cl.user_session.set("llm", llm)
    #                 break
    
    # start = time.time()

    llm :Llm = cl.user_session.get("LlmObj").llm
    
    history = []
    history.append(message.content)
    # history = trim_messages(history, llm.tokenizer)
    model_id = None
    try:
        msg = cl.Message(content="")
        async for chunk in run_concurrent_tasks(
                llm,
                message=history
            ):
            if chunk == STREAM_START_TOKEN:
                continue

            if chunk == STREAM_END_TOKEN:
                    break
            
            await msg.stream_token(chunk)
            
        hst_msg = msg.content.replace(model_id, "") if model_id else msg.content
        history.append(hst_msg)
        await msg.send()
    
    except Exception:
        await cl.ErrorMessage("Internal Server Error").send()

def serve():
    run_chainlit(os.path.abspath(__file__))