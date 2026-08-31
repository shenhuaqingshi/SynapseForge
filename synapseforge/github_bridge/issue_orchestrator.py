"""
Issue-to-Branch & Task Dispatcher.
Converts GitHub Issues with section drafting assignments into dedicated branches and draft PRs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.state import SectionStatus, StateManager
from synapseforge.github_bridge.client import GitHubClient


class IssueTaskOrchestrator:
    """Orchestrates incoming GitHub issue tasks into agent drafting workflows."""

    def __init__(self, project_root: Optional[Path] = None, config: Optional[ProjectConfig] = None):
        self.project_root = project_root or Path.cwd()
        self.config = config or load_config(self.project_root / "synapseforge.yaml")
        self.state_manager = StateManager(self.project_root)
        self.state_manager.sync_from_config(self.config)
        self.gh_client = GitHubClient()

    def parse_issue_payload(self, event_path: Path | str) -> Optional[Dict[str, Any]]:
        """Parses GitHub Action $GITHUB_EVENT_PATH payload."""
        p = Path(event_path)
        if not p.exists():
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def process_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts section ID and role from issue title/body, claims section in state, and reports branch."""
        title = issue_data.get("title", "")
        body = issue_data.get("body", "")
        issue_number = issue_data.get("number", 0)
        sender = issue_data.get("user", {}).get("login", "collaborator")

        # Match section ID in issue e.g. "[Task: sec_01_architecture] System Architecture"
        m = re.search(r'\[(?:Task|Section):\s*([a-zA-Z0-9_\-]+)\]', title)
        sec_id = m.group(1) if m else None

        if not sec_id or sec_id not in self.state_manager.state.sections:
            return {"status": "skipped", "reason": "No valid section ID found in issue title"}

        # Claim section in state ledger
        branch_name = f"{self.config.gitops.branch_prefix}{sec_id}"
        claimed = self.state_manager.claim_section(sec_id, actor=sender)
        if not claimed:
            # Lease held by another actor: do not overwrite status or save()
            holder = self.state_manager.state.active_locks.get(sec_id, "unknown")
            return {
                "status": "locked",
                "section_id": sec_id,
                "holder": holder,
            }
        sec_state = self.state_manager.state.sections[sec_id]
        sec_state.branch_name = branch_name
        sec_state.status = SectionStatus.DRAFTING
        self.state_manager.save()

        # Comment on issue
        comment = (
            f"### 🚀 SynapseForge Section Task Claimed\n\n"
            f"- **Section ID**: `{sec_id}` ({sec_state.title})\n"
            f"- **Assigned Actor**: @{sender}\n"
            f"- **Working Branch**: `{branch_name}`\n"
            f"- **Target File**: `{sec_state.file}`\n\n"
            f"Agent swarms and human reviewers can now collaborate on this branch. "
            f"Once ready, open a Pull Request against `{self.config.gitops.base_branch}`."
        )
        self.gh_client.post_issue_comment(issue_number, comment)

        return {
            "status": "claimed",
            "section_id": sec_id,
            "branch": branch_name,
            "actor": sender,
        }
