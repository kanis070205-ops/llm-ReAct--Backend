import docker
import uuid
import os
import json

BASE_DIR = os.path.abspath("workspace")


def get_client():
    return docker.from_env()


def run_task_container(task_input: dict) -> dict:
    task_id = str(uuid.uuid4())
    task_dir = os.path.join(BASE_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    input_path = os.path.join(task_dir, "input.json")
    output_path = os.path.join(task_dir, "output.json")

    with open(input_path, "w") as f:
        json.dump(task_input, f)

    env = {}
    if key := os.environ.get("TAVILY_API_KEY"):
        env["TAVILY_API_KEY"] = key

    client = get_client()

    container = None

    try:
        container = client.containers.run(
            image="react-agent-runner",
            command="python runner.py",
            volumes={task_dir: {"bind": "/app/data", "mode": "rw"}},
            working_dir="/app",
            environment=env,

            # 🔒 isolation
            network_disabled=False,

            # 🔒 limits
            mem_limit="256m",
            nano_cpus=500000000,  # 0.5 CPU

            detach=True,
        )

        # ⏱ timeout protection
        result = container.wait(timeout=30)

        logs = container.logs().decode()

        if result["StatusCode"] != 0:
            raise RuntimeError(f"Container failed:\n{logs}")

        if not os.path.exists(output_path):
            raise RuntimeError("output.json not created")

        with open(output_path) as f:
            return json.load(f)

    except Exception as e:
        if container:
            logs = container.logs().decode()
            print("Container logs:\n", logs)
        raise e

    finally:
        if container:
            try:
                container.remove(force=True)
            except:
                pass