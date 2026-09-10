"""Start a real server twice and verify persisted HTTP conversations.

Creates engineering conversations in the configured local database; retains them for inspection.
"""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager

import httpx

from afterstory.config import ROOT, Settings


@contextmanager
def server(provider):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, LLM_ACTIVE_MODEL=provider)
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "afterstory.api:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=90) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Backend exited during startup; check local config/migrations"
                        )
                    try:
                        if client.get("/health", timeout=1).status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Backend health check timed out")
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def post(client, path, body):
    result = client.post(path, json=body)
    if result.is_error:
        raise RuntimeError(f"Smoke request failed: HTTP {result.status_code}")
    return result.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    if (
        args.profile != "fake"
        and not Settings(llm_active_model=args.profile).active_model.api_key.get_secret_value()
    ):
        parser.error(
            "Set the selected profile API_KEY in local .env first; do not paste it into chat."
        )
    paths = []
    with server(args.profile) as client:
        for version in ("test-lan-v1", "test-xiao-v1"):
            instance = post(client, "/instances", {"version_id": version})
            conversation = post(client, "/conversations", {"instance_id": instance["instance_id"]})
            path = f"/conversations/{conversation['conversation_id']}/messages"
            paths.append(path)
            for index, message in enumerate(
                ("你好，我喜欢画画。", "今天画了一只猫。", "我刚才画了什么？")
            ):
                reply = post(client, path, {"request_id": f"smoke-{index}", "text": message})
                assert reply["text"] and reply["audio_status"] == "not_requested"
            assert client.get(path).json()["total"] == 3
    with server(args.profile) as client:
        for path in paths:
            assert client.get(path).json()["total"] == 3
            post(client, path, {"request_id": "smoke-restart", "text": "我们接着聊。"})
            assert client.get(path).json()["total"] == 4
    print(f"PASS: {args.profile}; two characters, eight turns, real process restart persisted.")
    if args.profile == "fake":
        print("Engineering verification only; real model expression has not been evaluated.")


if __name__ == "__main__":
    main()
