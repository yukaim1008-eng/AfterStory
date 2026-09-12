import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def run(command, *, cwd=ROOT, timeout=300, capture=False):
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        timeout=timeout,
        text=True,
        capture_output=capture,
    )


def main():
    docker = shutil.which("docker") or "docker"
    uv = shutil.which("uv") or "uv"
    npm = shutil.which("npm") or "npm"
    started_postgres = False
    try:
        running = run(
            [docker, "compose", "ps", "--status", "running", "--services"],
            timeout=30,
            capture=True,
        ).stdout.splitlines()
        if "postgres" not in running:
            started_postgres = True
            run([docker, "compose", "up", "-d", "--wait", "postgres"], timeout=120)

        run([uv, "run", "alembic", "upgrade", "head"], timeout=120)
        run([uv, "run", "python", "-m", "scripts.doctor", "--profile", "fake"], timeout=30)
        run([uv, "run", "ruff", "check", "afterstory", "tests", "scripts"], timeout=120)
        run([uv, "run", "pytest", "-q"], timeout=300)
        run([npm, "run", "build"], cwd=FRONTEND, timeout=300)
        run([npm, "run", "test:e2e"], cwd=FRONTEND, timeout=300)
        return 0
    except subprocess.TimeoutExpired as error:
        print(f"Verification timed out: {Path(str(error.cmd[0])).name}")
        return 1
    except (subprocess.CalledProcessError, OSError) as error:
        command = getattr(error, "cmd", None)
        name = Path(str(command[0])).name if command else type(error).__name__
        print(f"Verification failed: {name}")
        return 1
    finally:
        if started_postgres:
            try:
                run([docker, "compose", "stop", "postgres"], timeout=60)
            except (subprocess.SubprocessError, OSError):
                print("Verification could not stop the PostgreSQL service it started.")


if __name__ == "__main__":
    raise SystemExit(main())
