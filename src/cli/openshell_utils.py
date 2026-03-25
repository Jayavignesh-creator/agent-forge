from __future__ import annotations

import subprocess
from pathlib import Path


def upload_run_to_openshell_sandbox(
    folder_path: str | Path,
    run_id: str,
) -> subprocess.CompletedProcess[str]:
    source = Path(folder_path) / run_id
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Folder not found: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"Expected a directory, got: {source}")

    destination = f"/sandbox/.openclaw/workspace/{run_id}"

    try:
        return subprocess.run(
            ["openshell", "sandbox", "upload", "orchestrator", str(source), destination, "--no-git-ignore"],
            check=True,
            capture_output=True,
            text=True,
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
            ["ssh", sandbox_name, openclaw_command],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "No stderr output."
        raise RuntimeError(
            f"Failed to run command in sandbox '{sandbox_name}': {stderr}"
        ) from exc
