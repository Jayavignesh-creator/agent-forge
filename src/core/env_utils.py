from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_project_env(start_file: str) -> None:
    cwd_env = find_dotenv(filename=".env", usecwd=True)
    if cwd_env:
        load_dotenv(dotenv_path=cwd_env)
        return

    fallback_env = Path(start_file).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=fallback_env)


def require_openai_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or .env file."
        )
