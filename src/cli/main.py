import subprocess
import json
from pathlib import Path
from typing import Annotated
from time import sleep

import typer
import yaml

from core.planner import PlannerAgent
from core.prompt_compiler import PromptCompilerAgent

from cli.openshell_utils import upload_to_openshell_sandbox, run_openclaw_agent_in_sandbox, run_openshell_command

import uuid
    
RUN_DIR = Path(f"runs")

app = typer.Typer(
    name="agent-forge",
    help="CLI for agent-forge workflows.",
    no_args_is_help=True,
)


@app.callback()
def cli() -> None:
    """Run agent-forge commands."""


def generate_run_id() -> str:
    global RUN_DIR
    run_id = str(uuid.uuid4())
    RUN_DIR = RUN_DIR / run_id
    return run_id


def render_plan_markdown(plan_result: dict) -> str:
    lines = [
        "# Current Plan",
        "",
        f"**Task Summary:** {plan_result.get('task_summary', 'No task summary provided.')}",
        f"**Task Type:** {plan_result.get('task_type', 'unknown')}",
        f"**Execution Mode:** {plan_result.get('execution_mode', 'unknown')}",
        f"**Recommended Agent Count:** {plan_result.get('recommended_agent_count', 0)}",
        "",
        "## Planning Rationale",
    ]

    for item in plan_result.get("planning_rationale", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Agents"])
    for agent in plan_result.get("agents", []):
        lines.extend(
            [
                "",
                f"### {agent.get('id', 'unknown')} - {agent.get('role_name', 'Unnamed Agent')}",
                f"- Category: {agent.get('category', 'unknown')}",
                f"- Purpose: {agent.get('purpose', 'No purpose provided.')}",
                f"- Mandatory: {agent.get('mandatory', False)}",
                f"- Parallelizable: {agent.get('parallelizable', False)}",
                "- Responsibilities:",
            ]
        )
        for responsibility in agent.get("responsibilities", []):
            lines.append(f"  - {responsibility}")

        lines.append("- Outputs:")
        for output in agent.get("outputs", []):
            lines.append(f"  - {output}")

        dependencies = agent.get("dependencies", [])
        lines.append(
            f"- Dependencies: {', '.join(dependencies) if dependencies else 'None'}"
        )

    execution_plan = plan_result.get("execution_plan", {})
    lines.extend(
        [
            "",
            "## Execution Plan",
            f"- Order: {', '.join(execution_plan.get('order', [])) or 'None'}",
            f"- Merge Strategy: {execution_plan.get('merge_strategy', 'None')}",
            "",
            "## Verification Strategy",
            f"- Needed: {plan_result.get('verification_strategy', {}).get('needed', False)}",
        ]
    )

    for method in plan_result.get("verification_strategy", {}).get("methods", []):
        lines.append(f"- {method}")

    lines.extend(["", "## Stop Conditions"])
    for condition in plan_result.get("stop_conditions", []):
        lines.append(f"- {condition}")

    return "\n".join(lines).strip() + "\n"


def construct_state(plan_result: dict) -> dict:
    init_state = {
        "status": "idle",
        "agents": [],
        "execution_order": [],
        "parallel_groups": [],
        "completed_agents": [],
        "failed_agents": [],
        "spawned_agents": []
    }

    init_state["execution_order"] = plan_result.get("execution_plan", {}).get("order", [])
    init_state["parallel_groups"] = plan_result.get("execution_plan", {}).get("parallel_groups", [])
    init_state["agents"] = plan_result.get("agents", [])

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    state_file = RUN_DIR / "state.json"
    state_file.write_text(json.dumps(init_state, indent=2), encoding="utf-8")

    return init_state


def write_plan_file(plan_result: dict) -> Path:
    plan_markdown = render_plan_markdown(plan_result)
    plan_file = RUN_DIR / "current_plan.md"
    plan_file.write_text(plan_markdown, encoding="utf-8")

    plan_json_file = RUN_DIR / "current_plan.json"
    plan_json_file.write_text(json.dumps(plan_result, indent=2), encoding="utf-8")

    return plan_file.resolve(), plan_json_file.resolve()


def slugify(value: str) -> str:
    normalized = [
        char.lower() if char.isalnum() else "_"
        for char in value.strip()
    ]
    slug = "".join(normalized)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "agent"


def build_prompt_yaml_document(
    compiled_agent_prompt: dict,
    task_summary: str,
) -> dict:
    compiled_package = compiled_agent_prompt.get("compiled_prompt_package", {})
    role_name = compiled_agent_prompt.get("role_name", "Unnamed Agent")
    agent_id = compiled_agent_prompt.get("compiled_from_agent_id", slugify(role_name))

    return {
        "id": agent_id,
        "type": "system",
        "version": "1.0",
        "metadata": {
            "name": role_name,
            "description": f"Generated runtime system prompt for {role_name}",
            "owner": "agent-forge",
            "task_summary": task_summary,
            "category": compiled_agent_prompt.get("category", "unknown"),
        },
        "prompt": compiled_package.get("system_prompt", ""),
        "output_schema": compiled_package.get("output_schema", {}),
        "execution_guidance": compiled_package.get("execution_guidance", {}),
    }


def write_compiled_prompt_file(
    compiled_agent_prompt: dict,
    task_summary: str,
) -> Path:
    GENERATED_PROMPTS_DIR = RUN_DIR / "agent-schemas"
    GENERATED_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    agent_id = compiled_agent_prompt.get("compiled_from_agent_id", "Unnamed Agent")
    filename = f"{slugify(agent_id)}.yaml"
    output_path = GENERATED_PROMPTS_DIR / filename
    yaml_document = build_prompt_yaml_document(compiled_agent_prompt, task_summary)

    output_path.write_text(
        yaml.safe_dump(
            yaml_document,
            sort_keys=False,
            allow_unicode=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return output_path.resolve()


@app.command()
def plan(
    prompt: Annotated[str, typer.Argument(help="Prompt to generate a plan for.")]
) -> None:
    """Create a plan from a prompt."""
    try:
        run_id = generate_run_id()
        planner = PlannerAgent()
        compiler = PromptCompilerAgent()

        typer.secho(f"Run ID save and use it for other operations: {run_id}", fg=typer.colors.YELLOW)
        typer.secho("Generating plan ...", fg=typer.colors.GREEN)
        plan_result = planner.create_plan(prompt)
        state = construct_state(plan_result)

        typer.secho("Plan generation complete", fg=typer.colors.BLUE)
        plan_path, plan_json_path = write_plan_file(plan_result)
        
        typer.secho(f"Current plan written to {plan_path}", fg=typer.colors.BLUE)
        typer.secho(f"Current plan (JSON) written to {plan_json_path}", fg=typer.colors.BLUE)
        typer.secho("Compiling agent prompts ...", fg=typer.colors.GREEN)
        
        task_summary = plan_result.get("task_summary", "No task summary provided.")
        generated_prompt_paths: list[Path] = []

        for agent in plan_result.get("agents", []):
            agent_spec = {
                "task_summary": task_summary,
                "spec": agent
            }
            compiled_agent_prompt = compiler.compile_agent_spec(json.dumps(agent_spec))
            prompt_path = write_compiled_prompt_file(
                compiled_agent_prompt,
                task_summary,
            )
            generated_prompt_paths.append(prompt_path)
        typer.secho("Prompt compilation complete", fg=typer.colors.BLUE)
        for prompt_path in generated_prompt_paths:
            typer.secho(f"Stored generated prompt at {prompt_path}", fg=typer.colors.BLUE)

    except Exception as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    

def upload_files_sandbox(
    run_id: Annotated[str, typer.Argument(help="Run ID to construct orchestrator for.")]
):
    typer.secho(f"Uploading files for run {run_id} to OpenShell sandbox ...", fg=typer.colors.GREEN)
    upload_run = upload_to_openshell_sandbox(Path(RUN_DIR) / run_id, run_id)

    if upload_run.returncode == 0:
        typer.secho(f"Successfully uploaded run {run_id} to OpenShell sandbox.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Failed to upload run {run_id} to OpenShell sandbox. Return code: {upload_run.returncode}", err=True, fg=typer.colors.RED)
        typer.secho(f"stdout: {upload_run.stdout}", err=True, fg=typer.colors.RED)
        typer.secho(f"stderr: {upload_run.stderr}", err=True, fg=typer.colors.RED)
        raise RuntimeError(f"OpenShell upload failed with return code {upload_run.returncode}")
    

def download_outputs_sandbox(
    run_id: Annotated[str, typer.Argument(help="Run ID to construct orchestrator for.")]
):
    typer.secho(f"Downloading output files for run {run_id} from OpenShell sandbox ...", fg=typer.colors.GREEN)
    download_run = run_openshell_command(
        ["openshell", "sandbox", "download", "orchestrator", f"/sandbox/.openclaw/workspace/{run_id}/outputs", str(Path(RUN_DIR) / run_id / "outputs")]
    )

    if download_run.returncode == 0:
        typer.secho(f"Successfully downloaded outputs for run {run_id} from OpenShell sandbox.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Failed to download outputs for run {run_id} from OpenShell sandbox. Return code: {download_run.returncode}", err=True, fg=typer.colors.RED)
        typer.secho(f"stdout: {download_run.stdout}", err=True, fg=typer.colors.RED)
        typer.secho(f"stderr: {download_run.stderr}", err=True, fg=typer.colors.RED)
        raise RuntimeError(f"OpenShell download failed with return code {download_run.returncode}")


@app.command()
def preflight():
    """Run preflight checks."""
    gateway_ok = sandbox_ok = False
    typer.secho("Running preflight checks ...", fg=typer.colors.GREEN)
    try:
        gateway_check = run_openshell_command(["openshell", "status"])

    except Exception as exc:
        typer.secho("OpenShell Gateway is not running or not reachable.", err=True, fg=typer.colors.RED)
        typer.secho(f"Starting gateway container openshell-cluster-openshell", err=True, fg=typer.colors.YELLOW)

        try:
            subprocess.run(
                ["docker", "start", "openshell-cluster-openshell"],
                check=True,
                capture_output=True,
                text=True,
            )
            sleep(10)  # Wait for the container to start
        except Exception as docker_exc:
            typer.secho(f"Docker engine is not running, make sure to start docker before using agent-forge", err=True, fg=typer.colors.RED)

    try:
        sandbox_check = run_openshell_command(["openshell", "sandbox", "get", "orchestrator"])
        
    except Exception as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
    
    typer.secho("Preflight checks passed. OpenShell environment is ready.", fg=typer.colors.GREEN)
        

@app.command()
def construct(
    run_id: Annotated[str, typer.Argument(help="Run ID to construct orchestrator for.")]
):
    """Get orchestrator plan from master orchestrator. Executes the plan in OpenShell sandbox."""
    try:
        # Importing here to avoid circular imports since MasterOrchestrator also imports slugify from cli.main
        from core.master_orchestrator import MasterOrchestrator

        typer.secho(f"Constructing and executing orchestrator plan for run {run_id}", fg=typer.colors.GREEN)
        orchestrator = MasterOrchestrator(run_id=run_id)
        orch_plan = orchestrator.construct_orechestrator_plan()
        
        upload_files_sandbox(run_id)
        openclaw_response = run_openclaw_agent_in_sandbox(
            f"openclaw agent --agent main --local -m 'START {run_id}' --session-id {run_id}",
            "openshell-orchestrator",
        )

        typer.secho(f"OpenClaw agent execution completed with return code {openclaw_response.returncode}", fg=typer.colors.GREEN)
        if openclaw_response.returncode != 0:
            typer.secho(f"stdout: {openclaw_response.stdout}", err=True, fg=typer.colors.RED)
            typer.secho(f"stderr: {openclaw_response.stderr}", err=True, fg=typer.colors.RED)
            raise RuntimeError(f"OpenClaw agent execution failed with return code {openclaw_response.returncode}")
        else:
            typer.secho(f"Openclaw: {openclaw_response.stdout}", fg=typer.colors.BLUE)

        typer.secho(f"Constructed orchestrator plan", fg=typer.colors.BLUE)

        download_outputs_sandbox(run_id)
    except Exception as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)



if __name__ == "__main__":
    app()
