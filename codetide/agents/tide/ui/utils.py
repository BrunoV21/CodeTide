from codetide.agents.tide.ui.agent_tide_ui import AgentTideUi

from typing import List, Optional, Tuple
from chainlit.types import ThreadDict
from rich.progress import Progress
from aicore.logger import _logger
from aicore.llm import LlmConfig
import chainlit as cl
import asyncio
import orjson
import docker
import time
import os


def process_thread(thread :ThreadDict)->Tuple[List[dict], Optional[LlmConfig], str]:
    ### type: tool
    ### if nout ouput pop
    ### start = end
    idx_to_pop = []
    steps = thread.get("steps")
    tool_moves = []
    for i, entry in enumerate(steps):
        if entry.get("type") == "tool":
            if not entry.get("output"):
                idx_to_pop.insert(0, i)
                continue
            entry["start"] = entry["end"]
            tool_moves.append(i)

    for idx in idx_to_pop:
        steps.pop(idx)

    # Move tool entries with output after the next non-tool entry
    # Recompute tool_moves since popping may have changed indices
    # We'll process from the end to avoid index shifting issues
    # First, collect the indices of tool entries with output again
    tool_indices = []
    for i, entry in enumerate(steps):
        if entry.get("type") == "tool" and entry.get("output"):
            tool_indices.append(i)
    # For each tool entry, move it after the next non-tool entry
    # Process from last to first to avoid index shifting
    for tool_idx in reversed(tool_indices):
        tool_entry = steps[tool_idx]
        # Find the next non-tool entry after tool_idx
        insert_idx = None
        for j in range(tool_idx + 1, len(steps)):
            if steps[j].get("type") != "tool":
                insert_idx = j + 1
                break
        if insert_idx is not None and insert_idx - 1 != tool_idx:
            # Remove and insert at new position
            steps.pop(tool_idx)
            # If tool_idx < insert_idx, after pop, insert_idx decreases by 1
            if tool_idx < insert_idx:
                insert_idx -= 1
            steps.insert(insert_idx, tool_entry)

    metadata = thread.get("metadata")
    if metadata:
        metadata = orjson.loads(metadata)
        history = metadata.get("chat_history", [])
        settings = metadata.get("chat_settings")
        session_id = metadata.get("session_id")
    else:
        history = []
        settings = None
        session_id = None

    return history, settings, session_id

async def run_concurrent_tasks(agent_tide_ui: AgentTideUi, codeIdentifiers :Optional[List[str]]=None):
    asyncio.create_task(agent_tide_ui.agent_tide.agent_loop(codeIdentifiers))
    asyncio.create_task(_logger.distribute())
    while True:
        async for chunk in _logger.get_session_logs(agent_tide_ui.agent_tide.llm.session_id):
            yield chunk

async def send_reasoning_msg(loading_msg :cl.message, context_msg :cl.Message, agent_tide_ui :AgentTideUi, st :float)->bool:
    await loading_msg.remove()

    context_data = {
        key: value for key in ["contextIdentifiers", "modifyIdentifiers"]
        if (value := getattr(agent_tide_ui.agent_tide, key, None))
    }
    context_msg.elements.append(
        cl.CustomElement(
            name="ReasoningMessage",
            props={
                "reasoning": agent_tide_ui.agent_tide.reasoning,
                "data": context_data,
                "title": f"Thought for {time.time()-st:.2f} seconds",
                "defaultExpanded": False,
                "showControls": False
            }
        )
    )
    await context_msg.send()
    return True

def check_docker():
    try:
        client = docker.from_env()
        client.ping()  # Simple API check
        return True
    except Exception:
        return False
    
tasks = {}

# Show task progress (red for download, green for extract)
def show_progress(line, progress):
    if line['status'] == 'Downloading':
        id = f'[red][Download {line["id"]}]'
    elif line['status'] == 'Extracting':
        id = f'[green][Extract  {line["id"]}]'
    else:
        # skip other statuses
        return

    if id not in tasks.keys():
        tasks[id] = progress.add_task(f"{id}", total=line['progressDetail']['total'])
    else:
        progress.update(tasks[id], completed=line['progressDetail']['current'])

def image_pull(client :docker.DockerClient, image_name):
    print(f'Pulling image: {image_name}')
    with Progress() as progress:
        resp = client.api.pull(image_name, stream=True, decode=True)
        for line in resp:
            show_progress(line, progress)

def wait_for_postgres_ready(container, username: str, password: str, max_attempts: int = 30, delay: int = 2) -> bool:
    """
    Wait for PostgreSQL to be ready by checking container logs and attempting connections.
    """
    print("Waiting for PostgreSQL to be ready...")
    
    for attempt in range(max_attempts):
        try:
            # First, check if container is still running
            container.reload()
            if container.status != "running":
                print(f"Container stopped unexpectedly. Status: {container.status}")
                return False
            
            # Check logs for readiness indicator
            logs = container.logs().decode('utf-8')
            if "database system is ready to accept connections" in logs:
                print("PostgreSQL is ready to accept connections!")
                # Give it one more second to be completely ready
                time.sleep(5)
                return True
                
            print(f"Attempt {attempt + 1}/{max_attempts}: PostgreSQL not ready yet...")
            time.sleep(delay)
            
        except Exception as e:
            print(f"Error checking PostgreSQL readiness: {e}")
            time.sleep(delay)
    
    print("Timeout waiting for PostgreSQL to be ready")
    return False

def launch_postgres(POSTGRES_USER: str, POSTGRES_PASSWORD: str, volume_path: str):
    client = docker.from_env()
    container_name = "agent-tide-postgres"

    # Check if the container already exists
    try:
        container = client.containers.get(container_name)
        status = container.status
        print(f"Container '{container_name}' status: {status}")
        if status == "running":
            print("Container is already running. No need to relaunch.")
            return
        else:
            print("Container exists but is not running. Starting container...")
            container.start()
            return
    except docker.errors.NotFound:
        # Container does not exist, we need to create it
        print("Container does not exist. Launching a new one...")


    image_pull(client, "postgres:alpine")
    print("Image pulled successfully")
    # Launch a new container
    container = client.containers.run(
        "postgres:alpine",
        name=container_name,
        environment={
            "POSTGRES_USER": POSTGRES_USER,
            "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
            "POSTGRES_DB": "agenttidedb"
        },
        ports={"5432/tcp": os.getenv('AGENTTIDE_PG_PORT', 5437)},
        volumes={volume_path: {"bind": "/var/lib/postgresql/data", "mode": "rw"}},
        detach=True,
        restart_policy={"Name": "always"}
    )

    print(f"Container '{container_name}' launched successfully with status: {container.status}")
    # Wait for PostgreSQL to be ready
    return wait_for_postgres_ready(container, POSTGRES_USER, POSTGRES_PASSWORD)
