"""
Local Agent CLI adapter and runner for SynapseForge.

Dispatches section work to host Agent CLIs actually installed on the machine
(Antigravity ``agy``, Claude Code ``claude``, Codex ``codex``, Grok Build
``grok``, Aider). Command templates match the real CLIs:

- grok: ``grok -p PROMPT`` / ``grok --prompt-file PATH`` (not ``grok build``)
- agy:  ``agy -p PROMPT``
- claude: ``claude -p PROMPT``
- codex: ``codex exec PROMPT``
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError
from synapseforge.core.user_prompts import UserPromptManager

PROMPT_INLINE_LIMIT = 3500


@dataclass
class LocalAgentCLISpec:
    name: str
    binary: str
    description: str
    args_pattern: List[str]
    prompt_file_args: Optional[List[str]] = None
    is_installed: bool = False
    resolved_path: Optional[str] = None


DEFAULT_LOCAL_AGENTS: Dict[str, Dict[str, Any]] = {
    "antigravity": {
        "binary": "agy",
        "description": "Google Antigravity CLI (agy)",
        "args_pattern": ["-p", "{instruction}"],
        "prompt_file_args": None,
    },
    "claude": {
        "binary": "claude",
        "description": "Anthropic Claude Code CLI (claude)",
        "args_pattern": ["-p", "{instruction}"],
        "prompt_file_args": None,
    },
    "codex": {
        "binary": "codex",
        "description": "OpenAI Codex CLI (codex)",
        "args_pattern": ["exec", "{instruction}"],
        "prompt_file_args": None,
    },
    "grok": {
        "binary": "grok",
        "description": "xAI Grok Build CLI (grok)",
        "args_pattern": ["-p", "{instruction}"],
        "prompt_file_args": ["--prompt-file", "{prompt_file}"],
    },
    "aider": {
        "binary": "aider",
        "description": "Aider Pair Programming CLI (aider)",
        "args_pattern": ["--message", "{instruction}", "--yes"],
        "prompt_file_args": None,
    },
}

EXTRA_BIN_DIRS = [
    Path.home() / ".local" / "bin",
    Path.home() / ".grok" / "bin",
    Path.home() / ".npm-global" / "bin",
    Path.home() / ".cargo" / "bin",
    Path("/usr/local/bin"),
    Path("/usr/bin"),
    Path("/opt/homebrew/bin"),
]


def extra_search_dirs() -> List[Path]:
    dirs = list(EXTRA_BIN_DIRS)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        userprofile = os.environ.get("USERPROFILE", "")
        if local_appdata:
            dirs.append(Path(local_appdata) / "Programs")
            dirs.append(Path(local_appdata) / "Microsoft" / "WindowsApps")
        if appdata:
            dirs.append(Path(appdata) / "npm")
        if userprofile:
            dirs.append(Path(userprofile) / ".local" / "bin")
    path_env = os.environ.get("PATH") or ""
    for part in path_env.split(os.pathsep):
        if part:
            dirs.append(Path(part))
    seen = set()
    unique: List[Path] = []
    for item in dirs:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def resolve_binary(bin_name: str) -> Optional[str]:
    """Resolve a CLI binary across PATH plus common install prefixes."""
    if os.path.isabs(bin_name) and os.path.isfile(bin_name) and os.access(bin_name, os.X_OK):
        return bin_name
    found = shutil.which(bin_name)
    if found:
        return found
    extensions = ["", ".exe", ".cmd", ".bat"] if sys.platform == "win32" else [""]
    for directory in extra_search_dirs():
        if not directory.exists():
            continue
        for ext in extensions:
            candidate = directory / f"{bin_name}{ext}"
            if candidate.is_file() and (sys.platform == "win32" or os.access(str(candidate), os.X_OK)):
                return str(candidate)
    return None


def render_args(pattern: List[str], mapping: Dict[str, str]) -> List[str]:
    rendered: List[str] = []
    for arg in pattern:
        value = arg
        for key, replacement in mapping.items():
            value = value.replace("{" + key + "}", replacement)
        rendered.append(value)
    return rendered


class LocalAgentCLIManager:
    """Detects, registers, and dispatches writing tasks to local Agent CLI binaries."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.config_file = self.workspace_root / ".synapse" / "agent_clis.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.user_prompts = UserPromptManager(self.workspace_root)

    def _load_custom_registry(self) -> Dict[str, Dict[str, Any]]:
        if self.config_file.exists():
            try:
                loaded = json.loads(self.config_file.read_text(encoding="utf-8"))
                return loaded if isinstance(loaded, dict) else {}
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
        prompt_file_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register or override a local Agent CLI configuration."""
        registry = self._load_custom_registry()
        entry: Dict[str, Any] = {
            "binary": binary,
            "description": description or f"Local CLI agent for {name}",
            "args_pattern": args_pattern,
        }
        if prompt_file_args:
            entry["prompt_file_args"] = prompt_file_args
        registry[name] = entry
        self._save_custom_registry(registry)
        return {"ok": True, "agent_name": name, "binary": binary, "args_pattern": args_pattern}

    def _merged_specs(self) -> Dict[str, Dict[str, Any]]:
        all_specs = {k: dict(v) for k, v in DEFAULT_LOCAL_AGENTS.items()}
        for name, spec in self._load_custom_registry().items():
            merged = dict(all_specs.get(name) or {})
            merged.update(spec)
            all_specs[name] = merged
        return all_specs

    def detect_available_clis(self) -> List[Dict[str, Any]]:
        """Scan the host for installed Agent CLIs."""
        detected = []
        for name, spec in self._merged_specs().items():
            bin_name = spec["binary"]
            resolved = resolve_binary(bin_name)
            detected.append(
                {
                    "agent_name": name,
                    "binary": bin_name,
                    "description": spec.get("description", ""),
                    "args_pattern": spec.get("args_pattern") or [],
                    "prompt_file_args": spec.get("prompt_file_args"),
                    "installed": resolved is not None,
                    "executable_path": resolved,
                    "platform": sys.platform,
                }
            )
        return detected

    def build_command(
        self,
        spec: Dict[str, Any],
        instruction: str,
        prompt_file: Optional[Path] = None,
    ) -> List[str]:
        """Build argv for a host CLI, preferring a prompt file for long grok/codex prompts."""
        bin_path = spec.get("executable_path") or resolve_binary(spec["binary"])
        if not bin_path:
            raise FileNotFoundError(spec["binary"])
        mapping = {
            "instruction": instruction,
            "cwd": str(self.workspace_root),
            "prompt_file": str(prompt_file) if prompt_file else "",
        }
        prompt_file_args = spec.get("prompt_file_args")
        use_file = bool(prompt_file) and bool(prompt_file_args) and (
            len(instruction) > PROMPT_INLINE_LIMIT or spec.get("agent_name") == "grok" or spec.get("prefer_prompt_file")
        )
        if use_file and prompt_file_args:
            return [bin_path] + render_args(prompt_file_args, mapping)
        return [bin_path] + render_args(spec.get("args_pattern") or ["{instruction}"], mapping)

    def _resolve_section_file(self, section_id: str) -> Path:
        sec_dir = self.workspace_root / "sections"
        sec_dir.mkdir(parents=True, exist_ok=True)
        for path in sec_dir.glob("*.md"):
            if section_id in path.name or path.stem == section_id:
                return path
        return sec_dir / f"{section_id}.md"

    def compose_instruction(
        self,
        section_id: str,
        sec_file: Path,
        user_instruction: str,
        role_preset: Optional[str] = None,
        extra_protocol: str = "",
    ) -> str:
        system_prompt = ""
        if role_preset:
            system_prompt = self.user_prompts.get_prompt(role_preset) or ""
        try:
            rel = sec_file.relative_to(self.workspace_root)
        except ValueError:
            rel = Path(sec_file.name)
        parts = [
            "[SynapseForge Task Directive]",
            f"Workspace: {self.workspace_root}",
            f"Target Section File: {rel}",
            f"Section ID: {section_id}",
        ]
        if system_prompt:
            parts.extend(["", "Role Guidelines:", system_prompt])
        if extra_protocol:
            parts.extend(["", "Collaboration Protocol:", extra_protocol])
        parts.extend(
            [
                "",
                "User Instruction:",
                user_instruction,
                "",
                "Requirement: Edit the target section file directly. Keep rigorous academic prose, KaTeX formulas, and Booktabs tables. Do not invent a parallel copy of the file outside sections/.",
            ]
        )
        return "\n".join(parts)

    def run_agent_cli(
        self,
        agent_name: str,
        section_id: str,
        user_instruction: str,
        role_preset: Optional[str] = None,
        timeout: int = 120,
        extra_protocol: str = "",
    ) -> Dict[str, Any]:
        """
        Dispatch a section writing or editing task to a local Agent CLI.
        Locks the section atomically during execution, then returns the CLI result.
        """
        clis = {c["agent_name"]: c for c in self.detect_available_clis()}
        if agent_name not in clis:
            return {
                "ok": False,
                "error": f"Agent CLI '{agent_name}' not recognized. Available: {list(clis.keys())}",
            }

        spec = dict(clis[agent_name])
        spec["agent_name"] = agent_name
        bin_path = spec["executable_path"]
        if not spec["installed"] or not bin_path:
            return {
                "ok": False,
                "error": (
                    f"Agent CLI binary '{spec['binary']}' not found on host machine. "
                    f"Install '{spec['binary']}' or add it to PATH."
                ),
            }

        sec_file = self._resolve_section_file(section_id)
        full_instruction = self.compose_instruction(
            section_id, sec_file, user_instruction, role_preset, extra_protocol
        )

        run_dir = self.workspace_root / ".synapse" / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = run_dir / f"{agent_name}-{section_id}.prompt.txt"
        prompt_file.write_text(full_instruction, encoding="utf-8")

        prefer_file = bool(spec.get("prompt_file_args")) and (
            agent_name == "grok" or len(full_instruction) > PROMPT_INLINE_LIMIT
        )
        cmd_args = self.build_command(
            spec, full_instruction, prompt_file if prefer_file else None
        )

        try:
            with AutoSectionLock(
                section_id=section_id,
                agent_name=f"local-cli:{agent_name}",
                workspace_root=self.workspace_root,
            ) as lock:
                lock.heartbeat()
                result = subprocess.run(
                    cmd_args,
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                lock.heartbeat()
                return {
                    "ok": result.returncode == 0,
                    "agent": agent_name,
                    "binary": bin_path,
                    "argv": cmd_args,
                    "section_id": section_id,
                    "target_file": str(sec_file),
                    "prompt_file": str(prompt_file) if prefer_file else None,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "lock_status": "auto_released",
                }
        except SectionLockedError as exc:
            return {"ok": False, "error": f"Section is locked by another agent: {exc}", "section_id": section_id}
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"Local Agent CLI '{agent_name}' timed out after {timeout}s",
                "section_id": section_id,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "agent": agent_name}
