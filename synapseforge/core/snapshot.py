"""
Git-backed Version Snapshot and Rollback Engine for SynapseForge.
Enables fine-grained, non-destructive document versioning for solo human authors and AI agents.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class SnapshotManager:
    """Manages atomic Git checkpoints, branch tags, and section rollbacks."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()

    def create_checkpoint(self, message: str, section_id: Optional[str] = None, author: str = "SynapseForge") -> Dict[str, Any]:
        """Creates an atomic Git snapshot commit for current workspace changes."""
        try:
            # Stage markdown files and assets
            subprocess.run(["git", "add", "sections/", "assets/", "synapseforge.yaml"], cwd=self.repo_root, check=False)
            
            # Check if there are staged changes
            diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.repo_root)
            if diff_res.returncode == 0:
                # No changes to commit
                head_hash = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=self.repo_root, capture_output=True, text=True).stdout.strip()
                return {
                    "ok": True,
                    "created": False,
                    "commit_hash": head_hash,
                    "message": "No new changes to snapshot",
                }

            full_msg = f"checkpoint({section_id or 'doc'}): {message} [by {author}]"
            res = subprocess.run(["git", "commit", "-m", full_msg], cwd=self.repo_root, capture_output=True, text=True)
            head_hash = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=self.repo_root, capture_output=True, text=True).stdout.strip()

            return {
                "ok": res.returncode == 0,
                "created": True,
                "commit_hash": head_hash,
                "message": full_msg,
                "timestamp": time.time(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_history(self, section_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent snapshot history for a section or the whole document."""
        cmd = ["git", "log", f"-n{limit}", "--pretty=format:%h|%an|%at|%s"]
        if section_id:
            sec_file = self.repo_root / "sections" / f"{section_id}.md"
            if sec_file.exists():
                cmd.append(str(sec_file.relative_to(self.repo_root)))

        try:
            res = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
            history = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    history.append({
                        "commit_hash": parts[0],
                        "author": parts[1],
                        "timestamp": int(parts[2]),
                        "message": parts[3],
                    })
            return history
        except Exception:
            return []

    def rollback(self, commit_hash: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Rolls back a specific file or section to a previous commit checkpoint."""
        try:
            target = file_path or "sections/"
            res = subprocess.run(["git", "checkout", commit_hash, "--", target], cwd=self.repo_root, capture_output=True, text=True)
            return {
                "ok": res.returncode == 0,
                "target": target,
                "commit_hash": commit_hash,
                "error": res.stderr if res.returncode != 0 else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
