# agent-forge

`agent-forge` is a CLI for turning a single task prompt into an executable multi-agent workflow.

It uses an OpenAI-powered planning pipeline to:

- analyze a task and decide the minimum set of agents needed
- compile each agent into a concrete prompt/schema package
- assemble run artifacts under `runs/<run-id>/`
- hand the run to OpenShell/OpenClaw so an orchestrator can be generated and executed in a sandbox

In practice, this repo is the "plan and package" layer for agentic execution. It does not just run one model call. It creates a structured plan, prepares agent prompt files, and then delegates orchestration work to OpenClaw inside OpenShell.

## Workflow

The CLI is centered around a simple flow:

1. `plan` creates a task plan and compiled agent schemas.
2. `construct` prepares orchestrator inputs, uploads the run into OpenShell, and invokes OpenClaw in the sandbox.
3. `execute` runs the generated orchestration flow.

Generated artifacts are written to the `runs/` directory so each run is isolated and inspectable.

## Prerequisites

OpenShell is required before using this project.

- Install and configure OpenShell on your machine.
- Ensure the OpenShell gateway/sandbox is available.
- Ensure OpenClaw is configured inside that OpenShell environment, because this repo invokes it from the sandbox.

This project currently expects:

- an OpenShell sandbox named `orchestrator`
- SSH access to a sandbox target named `openshell-orchestrator`
- `openclaw` available inside that sandbox

Once OpenShell and OpenClaw are configured, set up SSH access with:

```bash
printf '\n' >> ~/.ssh/config && openshell sandbox ssh-config orchestrator >> ~/.ssh/config
```

The `construct` command calls:

```bash
openclaw agent --agent main --local -m "Follow the instructions inside TASK.yaml inside folder <run-id>" --session-id <run-id>
```

So your OpenShell/OpenClaw setup needs to support that command path.

## Environment

Create a `.env` file based on `.env.example` and set:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

## Install

```bash
git clone <your-repo-url>
cd agent-forge
uv tool install .
```

## Usage

```bash
agent-forge plan "Build a plan for my task"
agent-forge construct <run-id>
agent-forge execute <run-id>
```
