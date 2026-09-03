# Local Agent CLI Collaboration

SynapseForge already treats GitHub as the durable GitOps state machine and Tailscale as the cross-machine mesh. Host Agent CLIs on a single laptop need a third layer: a **local collaboration bus**.

`synapseforge team` is that bus. Codex, Grok Build, Antigravity (`agy`), Claude Code, and humans join one room, share a document, claim tasks, lock files, and take turns on irreversible actions (push / submit / deploy).

## Why this exists

Dispatching `grok` / `codex` / `agy` independently against the same `sections/*.md` tree races:

- two seats with the same name both think they own the work
- two agents create duplicate task cards for the same files
- a crashed holder keeps a section lease until wall-clock expiry
- reviewer and implementer both push

The bus is SQLite in `.synapse/team.db`. It does not bypass each CLI's own permission prompts.

## Seats

| Seat | CLI binary | Default job |
|---|---|---|
| `codex` | `codex` | Coordinator. Silent after 75s of no heartbeat → others freeze the plan and continue. |
| `grok` | `grok` | Independent analysis and review. Does not submit. |
| `antigravity` | `agy` | Implementation and tests. Only seat that should push/submit, after `claim-action`. |
| `human` | — | Directives. `kind=directive` is live instruction; agents act immediately. |

A second process joining as an already-live seat gets `already_online=true` and must observe only.

## Protocol (short)

1. Join first (`team join` or MCP `team_join`).
2. Read the shared document, recent messages, and any human directive.
3. List tasks before creating one. Same files / similar title → `deduplicated=true`; claim that card.
4. Claim a task and lock its files before editing. Paths must sit inside the room workspace.
5. If a lock holder is silent, `team reclaim` — do not wait forever.
6. If `coordinator_silent` is true after one `wait_for_activity` timeout, freeze and continue.
7. Before push/submit/deploy, `team claim-action --action-key unique`. Only the winner may call the API.
8. Heartbeat by reading messages at least every 60 seconds.

## CLI

```bash
# Create or resume a room; print paste prompts for each host CLI
synapseforge team open --document README.md --cwd . --json

# Join a seat
synapseforge team join --room my-paper --agent grok --role reviewer --json

# Human directive
synapseforge team say --room my-paper --agent human -m "Stop submitting" --kind directive

synapseforge team status --room my-paper --json
synapseforge team create-task --room my-paper --agent grok --title "Draft sec_01" --files sections/01_abstract_introduction.md
synapseforge team claim-task --room my-paper --agent grok --task-id 1
synapseforge team reclaim --room my-paper --agent grok
synapseforge team claim-action --room my-paper --agent antigravity --action-key push:main
```

Room name can be supplied as `--room` or `SYNAPSEFORGE_ROOM`. The database is `<workspace>/.synapse/team.db` unless `SYNAPSEFORGE_TEAM_DB` is set.

## MCP for host CLIs

```bash
synapseforge team mcp
```

The stdio server speaks Content-Length frames (Codex, Antigravity, MCP SDK) and newline-delimited JSON (Grok). Point each CLI's MCP config at that command with `SYNAPSEFORGE_WORKSPACE` and `SYNAPSEFORGE_ROOM` set. Tools: `team_join`, `team_share_document`, `team_post_message`, `team_read_messages`, `team_create_task`, `team_claim_task`, `team_lock_files`, `team_status`, `team_wait_for_activity`, `team_reclaim_stale_locks`, `team_claim_action`, …

## Host CLI invocation

`synapseforge agent run-cli` now matches the real binaries:

| Agent | argv |
|---|---|
| grok | `grok -p PROMPT` or `grok --prompt-file PATH` |
| antigravity | `agy -p PROMPT` |
| claude | `claude -p PROMPT` |
| codex | `codex exec PROMPT` |

Long Grok instructions are written to `.synapse/run/` and passed with `--prompt-file` so they do not hit `ARG_MAX`.

## Relation to mesh rooms

`synapseforge room` remains the Tailscale P2P room. `synapseforge team` is the same-machine bus. Use team for three terminals on one laptop; use mesh rooms when authors are on different nodes.
