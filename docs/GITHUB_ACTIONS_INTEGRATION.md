# GitHub Actions CI/CD Integration Guide

SynapseForge provides production-ready GitHub Actions workflows out of the box.

## Included Workflows

1. **`document-ci.yml`**:
   - Runs on every push and PR to `main`.
   - Executes unit tests (`pytest`), linter quality gates (`synapseforge lint --ci`), and compiles artifacts.

2. **`agent-peer-review.yml`**:
   - Triggers on PR opening and updates.
   - Runs multi-agent reviewer matrix and posts PR review comments with inline diff suggestions.

3. **`task-orchestrator.yml`**:
   - Listens to GitHub Issues with `[Task: sec_id]` titles.
   - Dispatches branch creation and section lease claiming.

4. **`publication-release.yml`**:
   - Deploys compiled publication to GitHub Pages and creates GitHub Releases upon tagging `v*`.
