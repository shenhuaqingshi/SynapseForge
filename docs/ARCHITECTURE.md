# SynapseForge Architecture Whitepaper

## 1. System Overview

SynapseForge bridges autonomous multi-agent swarms and globally distributed human co-authors by treating **GitHub as a Decentralized Consensus State Machine (GitOps-as-State)**. Rather than relying on centralized socket servers or naive ephemeral multi-agent chats, SynapseForge uses immutable Git commit histories, branch leases, GitHub Actions CI quality gates, and Pull Request review matrices to coordinate complex knowledge synthesis.

```
+-----------------------------------------------------------------------------------+
|                           Distributed Authors & Swarm                            |
|  [Agent: Drafter]    [Agent: Architect]    [Human: Lead Editor]    [Human: Peer]  |
+----------------------------------------+------------------------------------------+
                                         | (Git Commits / Draft PRs)
                                         v
+-----------------------------------------------------------------------------------+
|                        GitHub GitOps Coordination Layer                           |
|  - Issue Task Dispatcher (`[Task: sec_id]`) -> Automatic Branch Leasing          |
|  - Branch Protection & CODEOWNERS Approval Hierarchy                              |
|  - PR Review Bot with Inline Suggestions (`suggestion`)                           |
+----------------------------------------+------------------------------------------+
                                         | (GitHub Actions Event Trigger)
                                         v
+-----------------------------------------------------------------------------------+
|                     SynapseForge Quality Gates & Merging Engine                   |
|  +---------------------------+  +--------------------------+  +----------------+  |
|  | Anti-AI Flavor Linter     |  | Semantic AST 3-Way Merge |  | BibTeX Guard   |  |
|  +---------------------------+  +--------------------------+  +----------------+  |
|  | Coherence & Anchor Checker|  | Booktabs Table Validator |  | Typo Spacing   |  |
|  +---------------------------+  +--------------------------+  +----------------+  |
+----------------------------------------+------------------------------------------+
                                         | (Clean Convergence)
                                         v
+-----------------------------------------------------------------------------------+
|                          Multi-Target Publication Pipeline                        |
|   [Publication-Grade HTML]       [Vector Typst / PDF]      [Consolidated Markdown] |
+-----------------------------------------------------------------------------------+
```

## 2. AST-Level Semantic 3-Way Merge

Standard git `merge-recursive` or `ort` relies on the Longest Common Subsequence (LCS) across flat text lines. In document authoring, this results in high false-positive collision rates when concurrent authors edit different paragraphs within the same chapter or reorganize section sequences.

SynapseForge deconstructs documents into hierarchical Abstract Syntax Trees:
$$\mathcal{T}(\mathcal{D}) = \left( \mathcal{V}_{\text{frontmatter}}, \mathcal{V}_{\text{heading}}, \mathcal{V}_{\text{body}}, \mathcal{E}_{\text{hier}} \right)$$

The `SemanticConflictResolver` performs:
1. **Section Identity Mapping**: Matches nodes across Base, Ours, and Theirs via slugified section identifiers.
2. **Topological Order Preservation**: Resolves non-conflicting section additions and reorderings automatically.
3. **Block-Level Disjoint Merging**: Merges independent paragraph additions, math formulas, and tables within the same chapter.
4. **Structured Conflict Injection**: Generates attribution-tagged conflict markers with explicit resolution guidance when overlapping text blocks collide.

## 3. Autonomous PR Peer Review Matrix

When a Pull Request is opened by either a human or an agent, the PR Review Bot executes a multi-agent review matrix:
- **Critic Agent**: Scrutinizes quantitative claims, flags unsupported assertions, and checks logical edge cases.
- **Harmonizer Agent**: Harmonizes cross-regional voice and transitions between chapters.
- **Fact-Checker**: Cross-validates `@cite_key` anchors against `bibliography.bib`.

## 4. Local Agent CLI Bus

GitHub is the durable consensus log. Tailscale mesh rooms replicate state across nodes. Host Agent CLIs on one laptop (`codex`, `grok`, `agy`) need a third coordinator: a SQLite bus at `.synapse/team.db`.

`synapseforge team` / `synapseforge team mcp` provide:

- **Exclusive seats.** A second process joining as a live `grok` (or `codex` / `antigravity`) receives `already_online=true` and must observe only.
- **Task board with dedup.** Creating a card for the same files or a similar title returns the existing open card (`deduplicated=true`).
- **Workspace-scoped file locks** with heartbeat. Silent holders are reclaimed; a live OS process is not a heartbeat.
- **Coordinator-silent.** If `codex` has no heartbeat for 75 seconds, remaining agents freeze the plan and continue after one wait timeout.
- **Action claims.** `team_claim_action` is a one-shot mutex for push / submit / deploy. Default submitter is Antigravity; reviewers do not submit.
- **Human directives.** `kind=directive` from `human`, and anything the user says in an agent's own session, is live instruction.

This layer does not replace GitOps CI quality gates. It only prevents local CLI races before a PR exists. See `docs/LOCAL_AGENT_COLLAB.md`.
