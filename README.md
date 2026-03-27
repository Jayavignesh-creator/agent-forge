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
2. `construct` prepares orchestrator inputs, uploads the run into OpenShell, and invokes OpenClaw for execution in the sandbox.

Generated artifacts are written to the `runs/` directory so each run is isolated and inspectable.

## Prerequisites

OpenShell is required before using this project.

- Install OpenShell on your machine.

This project currently expects:

- an OpenShell sandbox named `orchestrator`
- SSH access to a sandbox target named `openshell-orchestrator`
- `openclaw` available and configured inside that sandbox

To setup these, run the setup script from the repo root:

```bash
bash src/config/configure.sh
```

That script creates the expected sandbox, applies the project sandbox policy, configures SSH access, runs OpenClaw onboarding inside the sandbox, and uploads the project identity file into the sandbox workspace.

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
ANTHROPIC_API_KEY=... #(For openclaw executions)
```

## Install

```bash
git clone <your-repo-url>
cd agent-forge
uv tool install .
```

## Usage

Run preflight every time you start working with `agent-forge`:

```bash
agent-forge preflight
```

Then use the normal workflow:

```bash
agent-forge plan "Build a plan for my task"
agent-forge construct <run-id>
```
