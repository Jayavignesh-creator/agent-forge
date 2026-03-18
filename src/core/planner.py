from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import APIError, OpenAI, OpenAIError


@dataclass(slots=True)
class PlannerConfig:
    model: str = os.getenv("OPENAI_MODEL", "gpt-5.2")
    prompt_path: Path = Path("src/schemas/planner.yaml")


class PlannerAgent:
    """Generate orchestration plans for user prompts."""

    def __init__(
        self,
        client: OpenAI | None = None
    ) -> None:
        load_dotenv()
        self.config = PlannerConfig()
        self.client = client or OpenAI()
        self.system_prompt = self._load_system_prompt(self.config.prompt_path)

    def create_plan(self, task_prompt: str) -> dict[str, Any]:
        if not task_prompt.strip():
            raise ValueError("Task prompt cannot be empty.")

        try:
            response = self.client.responses.create(
                model=self.config.model,
                input=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": task_prompt},
                ],
                text={"format": {"type": "json_object"}},
            )
        except OpenAIError as exc:
            message = "Planner request failed."
            if isinstance(exc, APIError) and exc.message:
                message = f"Planner request failed: {exc.message}"
            raise RuntimeError(message) from exc

        output_text = response.output_text
        if not output_text:
            raise ValueError("Planner model returned an empty response.")

        try:
            return json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Planner model returned invalid JSON.") from exc

    @staticmethod
    def _load_system_prompt(prompt_path: Path) -> str:
        raw_prompt = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
        
        if not isinstance(raw_prompt, dict):
            raise ValueError("Planner prompt file must be a YAML mapping.")

        prompt = raw_prompt.get("prompt")
        return prompt
