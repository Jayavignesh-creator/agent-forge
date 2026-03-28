from __future__ import annotations

import subprocess
from pathlib import Path


def run_openshell_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "No stderr output."
        raise RuntimeError(
            f"OpenShell command '{' '.join(command)}' failed: {stderr}"
        ) from exc


def upload_to_openshell_sandbox(
    folder_path: str | Path,
    run_id: str,
) -> subprocess.CompletedProcess[str]:
    source = Path(folder_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Folder not found: {source}")

    destination = f"/sandbox/.openclaw/workspace/{run_id}"

    try:
        return run_openshell_command(
            ["openshell", "sandbox", "upload", "orchestrator", str(source), destination, "--no-git-ignore"]
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "No stderr output."
        raise RuntimeError(
            f"openshell sandbox upload failed for '{source}' -> '{destination}': {stderr}"
        ) from exc


def run_openclaw_agent_in_sandbox(
    openclaw_command: str,
    sandbox_name: str,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["ssh", "-n", sandbox_name, openclaw_command],
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "No stderr output."
        raise RuntimeError(
            f"Failed to run command in sandbox '{sandbox_name}': {stderr}"
        ) from exc
    
def download_workspace(
    sandbox_name: str = "orchestrator",
    local_workspace: str | Path = Path("workspace"),
) -> subprocess.CompletedProcess[str]:
    local_path = Path(local_workspace).expanduser().resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local workspace not found: {local_path}")

    remote_path = "/sandbox/.openclaw/workspace/"

    try:
        return run_openshell_command(
            ["openshell", "sandbox", "download", sandbox_name, remote_path, str(local_path)]
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "No stderr output."
        raise RuntimeError(
            f"Failed to sync workspace to sandbox '{sandbox_name}': {stderr}"
        ) from exc
    
def upload_workspace(
    sandbox_name: str = "orchestrator",
    local_workspace: str | Path = Path("workspace"),
) -> subprocess.CompletedProcess[str]:
    local_path = Path(local_workspace).expanduser().resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local workspace not found: {local_path}")

    remote_path = "/sandbox/.openclaw/workspace/"

    try:
        return run_openshell_command(
            ["openshell", "sandbox", "upload", sandbox_name, str(local_path), remote_path, "--no-git-ignore"]
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "No stderr output."
        raise RuntimeError(
            f"Failed to upload workspace to sandbox '{sandbox_name}': {stderr}"
        ) from exc
