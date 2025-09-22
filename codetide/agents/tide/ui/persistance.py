from rich.progress import Progress
import docker
import time
import os


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
