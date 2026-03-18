from typing import Annotated

import typer
from rich import print_json

from core.planner_agent import PlannerAgent, PlannerConfig

app = typer.Typer(
    name="agent-forge",
    help="CLI for agent-forge workflows.",
    no_args_is_help=True,
)


@app.callback()
def cli() -> None:
    """Run agent-forge commands."""


@app.command()
def plan(
    prompt: Annotated[str, typer.Argument(help="Prompt to generate a plan for.")]
) -> None:
    """Create a plan from a prompt."""
    try:
        planner = PlannerAgent()
        plan_result = planner.create_plan(prompt)
        print_json(data=plan_result)
    except Exception as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
