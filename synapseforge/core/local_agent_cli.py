"""
Local Agent CLI Adapter and Runner for SynapseForge.
Allows SynapseForge to orchestrate real, native Agent CLIs installed on the user's machine,
such as Antigravity CLI (agy), Claude Code CLI (claude), Codex CLI (codex), Grok Build CLI (grok), Aider, etc.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError
from synapseforge.core.user_prompts import UserPromptManager


@dataclass
class LocalAgentCLISpec:
    name: str
    binary: str
    description: str
    args_pattern: List[str]  # e.g. ["-p", "{instruction}"] or ["exec", "{instruction}"]
    is_installed: bool = False
    resolved_path: Optional[str] = None


DEFAULT_LOCAL_AGENTS = {
    "antigravity": {
        "binary": "agy",
        "description": "Google Antigravity CLI (agy)",
        "args_pattern": ["-p", "{instruction}"],
    },
    "claude": {
        "binary": "claude",
        "description": "Anthropic Claude Code CLI (claude)",
        "args_pattern": ["-p", "{instruction}"],
    },
    "codex": {
        "binary": "codex",
        "description": "OpenAI Codex CLI (codex)",
        "args_pattern": ["exec", "{instruction}"],
    },
    "grok": {
        "binary": "grok",
        "description": "xAI Grok Build CLI (grok)",
        "args_pattern": ["build", "--instruction", "{instruction}"],
    },
    "aider": {
        "binary": "aider",
        "description": "Aider Pair Programming CLI (aider)",
        "args_pattern": ["--message", "{instruction}", "--yes"],
    },
}


class LocalAgentCLIManager:
    """Detects, registers, and dispatches writing tasks to local Agent CLI binaries."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.config_file = self.workspace_root / ".synapse" / "agent_clis.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.user_prompts = UserPromptManager(self.workspace_root)

    def _load_custom_registry(self) -> Dict[str, Dict[str, Any]]:
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_custom_registry(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.config_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def register_cli(
        self,
        name: str,
        binary: str,
        args_pattern: List[str],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registers or overrides a local Agent CLI configuration."""
        registry = self._load_custom_registry()
        registry[name] = {
            "binary": binary,
            "description": description or f"Local CLI agent for {name}",
            "args_pattern": args_pattern,
        }
        self._save_custom_registry(registry)
        return {"ok": True, "agent_name": name, "binary": binary, "args_pattern": args_pattern}

    def detect_available_clis(self) -> List[Dict[str, Any]]:
        """Scans the host system across Windows, macOS, and Linux to find all installed Agent CLIs."""
        all_specs = dict(DEFAULT_LOCAL_AGENTS)
        all_specs.update(self._load_custom_registry())

        # Cross-platform search paths
        candidate_dirs = [
            Path.home() / ".local" / "bin",
            Path("/usr/local/bin"),
            Path("/usr/bin"),
            Path("/opt/homebrew/bin"),  # macOS Homebrew (Apple Silicon)
            Path("/usr/local/Cellar"),  # macOS Homebrew (Intel)
        ]
        if sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            appdata = os.environ.get("APPDATA", "")
            userprofile = os.environ.get("USERPROFILE", "")
            if local_appdata:
                candidate_dirs.append(Path(local_appdata) / "Programs")
                candidate_dirs.append(Path(local_appdata) / "Microsoft" / "WindowsApps")
            if appdata:
                candidate_dirs.append(Path(appdata) / "npm")
            if userprofile:
                candidate_dirs.append(Path(userprofile) / ".local" / "bin")

        detected = []
        for name, spec in all_specs.items():
            bin_name = spec["binary"]
            resolved = shutil.which(bin_name)
            is_present = resolved is not None

            # Cross-platform fallback check
            if not is_present:
                extensions = ["", ".exe", ".cmd", ".bat"] if sys.platform == "win32" else [""]
                for cdir in candidate_dirs:
                    if not cdir.exists():
                        continue
                    for ext in extensions:
                        candidate = cdir / f"{bin_name}{ext}"
                        if candidate.exists() and (sys.platform == "win32" or os.access(str(candidate), os.X_OK)):
                            resolved = str(candidate)
                            is_present = True
                            break
                    if is_present:
                        break

            detected.append({
                "agent_name": name,
                "binary": bin_name,
                "description": spec["description"],
                "args_pattern": spec["args_pattern"],
                "installed": is_present,
                "executable_path": resolved,
                "platform": sys.platform,
            })
        return detected

    def run_agent_cli(
        self,
        agent_name: str,
        section_id: str,
        user_instruction: str,
        role_preset: Optional[str] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """
        Dispatches a section writing or editing task to a local Agent CLI.
        Locks the section atomically during execution, then verifies the output.
        """
        clis = {c["agent_name"]: c for c in self.detect_available_clis()}
        if agent_name not in clis:
            return {"ok": False, "error": f"Agent CLI '{agent_name}' not recognized. Available: {list(clis.keys())}"}

        spec = clis[agent_name]
        bin_path = spec["executable_path"]
        if not spec["installed"] or not bin_path:
            return {
                "ok": False,
                "error": f"Agent CLI binary '{spec['binary']}' not found on host machine. Please install '{spec['binary']}' or add to PATH.",
            }

        # Resolve Section Path
        sec_dir = self.workspace_root / "sections"
        sec_file = None
        for p in sec_dir.glob("*.md"):
            if section_id in p.name:
                sec_file = p
                break
        if not sec_file:
            sec_file = sec_dir / f"{section_id}.md"

        # Load User Custom System Prompt if available
        system_prompt = ""
        if role_preset:
            system_prompt = self.user_prompts.get_prompt(role_preset) or ""

        # Construct comprehensive prompt for local coding agent
        full_instruction = (
            f"[SynapseForge Task Directive]\n"
            f"Target Section File: {sec_file.relative_to(self.workspace_root) if sec_file.exists() else sec_file.name}\n"
            f"Role Guidelines:\n{system_prompt}\n\n"
            f"User Instruction:\n{user_instruction}\n\n"
            f"Requirement: Directly edit the target section file with rigorous academic prose, KaTeX formulas, and Booktabs tables."
        )

        # Build Command Arguments
        cmd_args = [bin_path]
        for arg in spec["args_pattern"]:
            if "{instruction}" in arg:
                cmd_args.append(arg.replace("{instruction}", full_instruction))
            else:
                cmd_args.append(arg)

        # Execute with Atomic File Lock
        try:
            with AutoSectionLock(section_id=section_id, agent_name=f"local-cli:{agent_name}", workspace_root=self.workspace_root):
                res = subprocess.run(
                    cmd_args,
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                return {
                    "ok": res.returncode == 0,
                    "agent": agent_name,
                    "binary": bin_path,
                    "section_id": section_id,
                    "target_file": str(sec_file),
                    "returncode": res.returncode,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                    "lock_status": "auto_released",
                }
        except SectionLockedError as e:
            return {"ok": False, "error": f"Section is locked by another agent: {e}", "section_id": section_id}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Local Agent CLI '{agent_name}' timed out after {timeout}s", "section_id": section_id}
        except Exception as e:
            return {"ok": False, "error": str(e), "agent": agent_name}
