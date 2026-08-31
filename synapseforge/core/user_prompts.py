"""
User-Defined Agent Roles and Custom System Prompt Manager for SynapseForge.
Gives complete autonomy to the human author to create, edit, register, and manage
their own custom agent personas, prompts, and model assignments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserPromptManager:
    """Manages user-defined custom agent prompts stored in the user workspace."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.prompts_dir = self.workspace_root / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.prompts_dir / "custom_roles.json"

    def _load_meta(self) -> Dict[str, Dict[str, Any]]:
        if self.meta_file.exists():
            try:
                return json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_meta(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.meta_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def set_prompt(
        self,
        role_id: str,
        prompt_content: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """User sets or updates a custom agent role and its system prompt."""
        role_id = role_id.strip().lower().replace(" ", "_")
        prompt_file = self.prompts_dir / f"{role_id}.md"
        prompt_file.write_text(prompt_content, encoding="utf-8")

        meta = self._load_meta()
        meta[role_id] = {
            "role_id": role_id,
            "display_name": display_name or role_id.title(),
            "description": description or f"User custom role for {role_id}",
            "prompt_file": f"prompts/{role_id}.md",
            "model": model or "deepseek-v3",
        }
        self._save_meta(meta)

        return {
            "ok": True,
            "role_id": role_id,
            "display_name": meta[role_id]["display_name"],
            "prompt_file": meta[role_id]["prompt_file"],
            "length_characters": len(prompt_content),
        }

    def get_prompt(self, role_id: str) -> Optional[str]:
        """Fetches the user's custom system prompt for an agent role."""
        role_id = role_id.strip().lower().replace(" ", "_")
        prompt_file = self.prompts_dir / f"{role_id}.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return None

    def list_prompts(self) -> List[Dict[str, Any]]:
        """Lists all user-defined custom agent prompts."""
        meta = self._load_meta()
        res = []
        for r_id, info in meta.items():
            p_file = self.workspace_root / info["prompt_file"]
            info["exists"] = p_file.exists()
            info["size_bytes"] = p_file.stat().st_size if p_file.exists() else 0
            res.append(info)

        # Also detect any standalone .md files placed in prompts/
        for p in self.prompts_dir.glob("*.md"):
            if p.stem not in meta:
                res.append({
                    "role_id": p.stem,
                    "display_name": p.stem.title(),
                    "description": "User created markdown prompt file",
                    "prompt_file": str(p.relative_to(self.workspace_root)),
                    "model": "user-default",
                    "exists": True,
                    "size_bytes": p.stat().st_size,
                })
        return res

    def delete_prompt(self, role_id: str) -> bool:
        """Deletes a custom user prompt."""
        role_id = role_id.strip().lower().replace(" ", "_")
        prompt_file = self.prompts_dir / f"{role_id}.md"
        if prompt_file.exists():
            prompt_file.unlink()

        meta = self._load_meta()
        if role_id in meta:
            del meta[role_id]
            self._save_meta(meta)
            return True
        return False
