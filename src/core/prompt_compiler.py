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
class CompilerConfig:
    model: str = os.getenv("OPENAI_MODEL", "gpt-5.2")
    prompt_path: Path = Path("src/schemas/compiler.yaml")


class PromptCompilerAgent:
    """Compile agent specifications into executable prompts."""

    def __init__(
        self,
        client: OpenAI | None = None
    ) -> None:
        load_dotenv()
        self.config = CompilerConfig()
        self.client = client or OpenAI()
        self.system_prompt = self._load_system_prompt(self.config.prompt_path)

    def extract_system_prompt(self, compiled_agent_spec: dict[str, Any]) -> str:
        compiled_package = compiled_agent_spec.get("compiled_prompt_package", {})

        system_prompt = compiled_package.get("system_prompt", "").strip()
        output_schema = json.dumps(
            compiled_package.get("output_schema", {}),
            indent=2,
            ensure_ascii=True,
        )
        execution_guidance = json.dumps(
            compiled_package.get("execution_guidance", {}),
            indent=2,
            ensure_ascii=True,
        )

        return "\n\n".join(
            [
                system_prompt,
                "Output schema:",
                output_schema,
                "Execution guidance:",
                execution_guidance,
            ]
        ).strip()


    def compile_agent_spec(self, agent_spec: str) -> dict[str, Any]:
        if not agent_spec.strip():
            raise ValueError("Agent specification cannot be empty.")

        try:
            response = self.client.responses.create(
                model=self.config.model,
                input=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": agent_spec},
                ],
                text={"format": {"type": "json_object"}},
            )
        except OpenAIError as exc:
            message = "Compiler request failed."
            if isinstance(exc, APIError) and exc.message:
                message = f"Compiler request failed: {exc.message}"
            raise RuntimeError(message) from exc

        output_text = response.output_text
        if not output_text:
            raise ValueError("Compiler model returned an empty response.")

        try:
            return json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Compiler model returned invalid JSON.") from exc

    @staticmethod
    def _load_system_prompt(prompt_path: Path) -> str:
        raw_prompt = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
        
        if not isinstance(raw_prompt, dict):
            raise ValueError("Compiler prompt file must be a YAML mapping.")

        prompt = raw_prompt.get("prompt")
        return prompt
