from __future__ import annotations

import json
import operator
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, TypedDict

import yaml
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from openai import APIError, OpenAI, OpenAIError


RUNS_DIR = Path("runs")
TASK_SUMMARY_PATTERN = re.compile(r"\*\*Task Summary:\*\*\s*(.+)")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")


class WorkerAssignment(TypedDict):
    agent_id: str
    role_name: str
    prompt_path: str


class WorkerResult(TypedDict):
    agent_id: str
    role_name: str
    prompt_path: str
    output_path: str
    result: dict[str, Any]


class OrchestratorState(TypedDict):
    run_id: str
    task_summary: str
    execution_order: list[str]
    worker_assignments: list[WorkerAssignment]
    worker_results: Annotated[list[WorkerResult], operator.add]
    final_output: str
    final_output_path: str


class WorkerState(TypedDict):
    run_id: str
    task_summary: str
    agent_id: str
    role_name: str
    prompt_path: str


@dataclass(slots=True)
class RunArtifacts:
    run_id: str
    run_dir: Path
    current_plan_path: Path
    state_path: Path
    prompts_dir: Path
    outputs_dir: Path


def _build_run_artifacts(run_id: str) -> RunArtifacts:
    run_dir = RUNS_DIR / run_id
    current_plan_path = run_dir / "current_plan.md"
    state_path = run_dir / "state.json"
    prompts_dir = run_dir / "agent-schemas"
    outputs_dir = run_dir / "outputs"

    if not current_plan_path.exists():
        raise FileNotFoundError(f"Run plan not found at {current_plan_path}")
    if not state_path.exists():
        raise FileNotFoundError(f"Run state not found at {state_path}")
    if not prompts_dir.exists():
        raise FileNotFoundError(f"Run prompt directory not found at {prompts_dir}")

    outputs_dir.mkdir(parents=True, exist_ok=True)
    return RunArtifacts(
        run_id=run_id,
        run_dir=run_dir,
        current_plan_path=current_plan_path,
        state_path=state_path,
        prompts_dir=prompts_dir,
        outputs_dir=outputs_dir,
    )


def _extract_task_summary(current_plan_path: Path) -> str:
    plan_markdown = current_plan_path.read_text(encoding="utf-8")
    match = TASK_SUMMARY_PATTERN.search(plan_markdown)
    if not match:
        raise ValueError(f"Task summary not found in {current_plan_path}")
    return match.group(1).strip()


def _load_execution_order(state_path: Path) -> list[str]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    execution_order = state.get("execution_order", [])
    if not isinstance(execution_order, list):
        raise ValueError("Run state execution_order must be a list.")
    return [str(agent_id) for agent_id in execution_order]


def _infer_execution_order(prompts_dir: Path) -> list[str]:
    prompt_files = sorted(prompts_dir.glob("*.yaml"))
    return [prompt_file.stem for prompt_file in prompt_files]


def _load_worker_assignments(
    execution_order: list[str],
    prompts_dir: Path,
) -> list[WorkerAssignment]:
    assignments: list[WorkerAssignment] = []

    for agent_id in execution_order:
        prompt_path = prompts_dir / f"{agent_id}.yaml"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Worker prompt not found at {prompt_path}")

        prompt_doc = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
        if not isinstance(prompt_doc, dict):
            raise ValueError(f"Worker prompt file must be a YAML mapping: {prompt_path}")

        metadata = prompt_doc.get("metadata", {})
        role_name = metadata.get("name") or prompt_doc.get("id") or agent_id

        assignments.append(
            {
                "agent_id": agent_id,
                "role_name": str(role_name),
                "prompt_path": str(prompt_path),
            }
        )

    return assignments


def _load_system_prompt(prompt_path: Path) -> str:
    prompt_doc = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
    if not isinstance(prompt_doc, dict):
        raise ValueError(f"Worker prompt file must be a YAML mapping: {prompt_path}")

    system_prompt = prompt_doc.get("prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError(f"Worker prompt is missing a valid prompt body: {prompt_path}")

    return system_prompt


def _call_worker_model(
    client: OpenAI,
    task_summary: str,
    role_name: str,
    system_prompt: str,
) -> dict[str, Any]:
    user_prompt = (
        "Complete your assigned role for the following task summary.\n"
        "Return valid JSON only.\n\n"
        f"Task summary:\n{task_summary}"
    )

    try:
        response = client.responses.create(
            model=DEFAULT_MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            text={"format": {"type": "json_object"}},
        )
    except OpenAIError as exc:
        message = f"Worker request failed for {role_name}."
        if isinstance(exc, APIError) and exc.message:
            message = f"Worker request failed for {role_name}: {exc.message}"
        raise RuntimeError(message) from exc

    if not response.output_text:
        raise ValueError(f"Worker {role_name} returned an empty response.")

    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Worker {role_name} returned invalid JSON.") from exc


def _write_worker_output(
    outputs_dir: Path,
    agent_id: str,
    result: dict[str, Any],
) -> Path:
    output_path = outputs_dir / f"{agent_id}.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output_path


def _render_final_output(task_summary: str, worker_results: list[WorkerResult]) -> str:
    lines = [
        "# Execution Results",
        "",
        f"**Task Summary:** {task_summary}",
        "",
        "## Worker Outputs",
    ]

    for worker_result in worker_results:
        lines.extend(
            [
                "",
                f"### {worker_result['agent_id']} - {worker_result['role_name']}",
                f"Output File: {worker_result['output_path']}",
                "```json",
                json.dumps(worker_result["result"], indent=2),
                "```",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _write_final_output(run_dir: Path, final_output: str) -> Path:
    output_path = run_dir / "final_output.md"
    output_path.write_text(final_output, encoding="utf-8")
    return output_path


def orchestrator(state: OrchestratorState) -> dict[str, Any]:
    return {"worker_assignments": state["worker_assignments"]}


def assign_workers(state: OrchestratorState) -> list[Send]:
    return [
        Send(
            "worker",
            {
                "run_id": state["run_id"],
                "task_summary": state["task_summary"],
                "agent_id": assignment["agent_id"],
                "role_name": assignment["role_name"],
                "prompt_path": assignment["prompt_path"],
            },
        )
        for assignment in state["worker_assignments"]
    ]


def worker(state: WorkerState) -> dict[str, Any]:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or .env file."
        )

    client = OpenAI()
    run_artifacts = _build_run_artifacts(state["run_id"])
    prompt_path = Path(state["prompt_path"])
    system_prompt = _load_system_prompt(prompt_path)
    result = _call_worker_model(
        client=client,
        task_summary=state["task_summary"],
        role_name=state["role_name"],
        system_prompt=system_prompt,
    )
    output_path = _write_worker_output(
        outputs_dir=run_artifacts.outputs_dir,
        agent_id=state["agent_id"],
        result=result,
    )

    return {
        "worker_results": [
            {
                "agent_id": state["agent_id"],
                "role_name": state["role_name"],
                "prompt_path": str(prompt_path),
                "output_path": str(output_path),
                "result": result,
            }
        ]
    }


def synthesizer(state: OrchestratorState) -> dict[str, Any]:
    run_artifacts = _build_run_artifacts(state["run_id"])
    final_output = _render_final_output(
        task_summary=state["task_summary"],
        worker_results=state.get("worker_results", []),
    )
    final_output_path = _write_final_output(run_artifacts.run_dir, final_output)
    return {
        "final_output": final_output,
        "final_output_path": str(final_output_path),
    }


def build_orchestrator_graph():
    builder = StateGraph(OrchestratorState)
    builder.add_node("orchestrator", orchestrator)
    builder.add_node("worker", worker)
    builder.add_node("synthesizer", synthesizer)
    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges("orchestrator", assign_workers, ["worker"])
    builder.add_edge("worker", "synthesizer")
    builder.add_edge("synthesizer", END)
    return builder.compile()


def execute_run(run_id: str) -> dict[str, Any]:
    run_artifacts = _build_run_artifacts(run_id)
    task_summary = _extract_task_summary(run_artifacts.current_plan_path)
    execution_order = _load_execution_order(run_artifacts.state_path)
    if not execution_order:
        execution_order = _infer_execution_order(run_artifacts.prompts_dir)

    worker_assignments = _load_worker_assignments(
        execution_order=execution_order,
        prompts_dir=run_artifacts.prompts_dir,
    )

    graph = build_orchestrator_graph()
    return graph.invoke(
        {
            "run_id": run_id,
            "task_summary": task_summary,
            "execution_order": execution_order,
            "worker_assignments": worker_assignments,
            "worker_results": [],
            "final_output": "",
            "final_output_path": "",
        }
    )
