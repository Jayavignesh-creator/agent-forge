from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
import yaml
from dotenv import load_dotenv
from openai import APIError, OpenAI, OpenAIError

from cli.main import slugify

@dataclass(slots=True)
class OrchestratorConfig:
    model: str = os.getenv("OPENAI_MODEL", "gpt-5.2")
    prompt_path: Path = Path("src/schemas/orchestrator.yaml")

class MasterOrchestrator:
    """Orchestrate the overall agent workflow by coordinating the planner and compiler agents."""

    def __init__(
        self,
        run_id: str,
    ) -> None:
        load_dotenv()
        self.config = OrchestratorConfig()
        self.RUN_DIR = Path(f"runs") / run_id
        self.run_id = run_id
        self.system_prompt = self._load_system_prompt(self.config.prompt_path)

    def construct_orechestrator_plan(self) -> dict[str, Any]:
        # read current_plan.json from RUN_DIR
        plan_json_path = self.RUN_DIR / "current_plan.json"
        if not plan_json_path.exists():
            raise FileNotFoundError(f"Plan file not found at {plan_json_path}")
        plan_result = json.loads(plan_json_path.read_text(encoding="utf-8"))
        agent_paths = []

        for agent in plan_result.get("agents", []):
            id = agent.get("id", "unknown_agent")
            agent_prompt_path = self.RUN_DIR / "agent-schemas" / f"{slugify(id)}.yaml"
            if agent_prompt_path.exists():
                agent_paths.append(str(agent_prompt_path))
            else:
                typer.secho(f"Warning: System prompt for agent '{id}' not found at {agent_prompt_path}", fg=typer.colors.YELLOW)
        

        orch_plan = {
            "execution_plan": {
                "order": plan_result.get("execution_plan", {}).get("order", []),
                "parallel_groups": plan_result.get("execution_plan", {}).get("parallel_groups", []),
                "merge_strategy": plan_result.get("execution_plan", {}).get("merge_strategy", [])
            },
            "agents": plan_result.get("agents", []),
            "agent_prompt_paths": agent_paths,
            "state_path": str(self.RUN_DIR / "state.json"),
        }

        orch_plan = json.dumps(orch_plan, indent=2)
        
        orch_input_path = self.RUN_DIR / "orch_input.json"
        orch_input_path.write_text(orch_plan, encoding="utf-8")

        return orch_plan
    
    def write_orchestrator_output(self, orchestrator_output: dict[str, Any]) -> Path:
        output_path = self.RUN_DIR / "orchestrator_output.json"
        output_path.write_text(json.dumps(orchestrator_output, indent=2), encoding="utf-8")

        orch_code = orchestrator_output["orchestrator_code"]
        # create a runnable Python script with the orchestrator code
        script_path = self.RUN_DIR / "orchestrator.py"
        script_content = f"""\"\"\"Auto-generated orchestrator script. Do not edit directly.\"\"\"\n{orch_code}"""
        script_path.write_text(script_content, encoding="utf-8")

        return output_path.resolve()

    @staticmethod
    def _load_system_prompt(prompt_path: Path) -> str:
        raw_prompt = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
        
        if not isinstance(raw_prompt, dict):
            raise ValueError("Master orchestrator prompt file must be a YAML mapping.")

        prompt = raw_prompt.get("prompt")
        return prompt
