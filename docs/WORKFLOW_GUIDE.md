# SynapseForge Distributed Collaborative Workflow Guide

This guide describes how globally distributed human contributors and autonomous AI agents collaborate asynchronously on complex technical documents.

## Step 1: Defining the Document DAG in `synapseforge.yaml`

A document is broken into structured, modular sections with explicit dependencies:

```yaml
sections:
  - id: "sec_01_intro"
    title: "Introduction and Problem Setting"
    file: "sections/01_introduction.md"
    assigned_role: "drafter"
    dependencies: []
    word_count_target: 1000

  - id: "sec_02_architecture"
    title: "System Architecture"
    file: "sections/02_architecture.md"
    assigned_role: "drafter"
    dependencies: ["sec_01_intro"]
    word_count_target: 1500
```

## Step 2: Task Dispatching via GitHub Issues

1. Create a GitHub Issue with title: `[Task: sec_01_intro] Write Introduction Section`
2. The GitHub Action `task-orchestrator.yml` automatically:
   - Claims the section lock in `.synapse/state.json`
   - Creates a dedicated branch `synapse/sec_01_intro`
   - Replies on the issue with drafting instructions

## Step 2b: Same-machine Agent CLI rooms

When Codex, Grok Build, and Antigravity share one laptop, open a local team room before anyone edits `sections/`:

```bash
synapseforge team open --document sections/01_abstract_introduction.md --cwd .
synapseforge team join --room <room> --agent grok
synapseforge team claim-task --room <room> --agent grok --task-id 1
```

Rules: one live seat per name (`already_online` observers do not edit), lock files inside the workspace, reclaim silent holders, only Antigravity calls push/submit after `team claim-action`. Full protocol: `docs/LOCAL_AGENT_COLLAB.md`.

## Step 3: Drafting & Local Quality Verification

Collaborators (agent or human) write content in their dedicated branch and run local quality checks:

```bash
# Verify all quality gates locally
synapseforge lint

# Test publication build
synapseforge build
```

## Step 4: Pull Request & Automated Swarm Review

1. Push your branch and open a Pull Request to `main`.
2. The `agent-peer-review.yml` workflow triggers automatically.
3. The **Critic Agent** and **Anti-AI Linter** inspect all modified lines and post line-by-line comments with suggested diffs.
4. Once quality gates pass and human reviewers approve, merge the PR into `main`.
