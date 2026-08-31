"""
GitOps State Manager and Section Lease Ledger for Distributed Multi-Agent Swarms.
Tracks section assignments, lock leases, SHA256 hashes, and topological dependency graphs.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from synapseforge.config import ProjectConfig, SectionSpec


class SectionStatus(str):
    IDLE = "idle"
    CLAIMED = "claimed"
    DRAFTING = "drafting"
    REVIEW_PENDING = "review_pending"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    MERGED = "merged"


@dataclass
class SectionState:
    id: str
    title: str
    file: str
    status: str = SectionStatus.IDLE
    assigned_role: str = "drafter"
    assigned_actor: str = "unassigned"  # agent name or human github handle
    lock_expires_at: float = 0.0
    current_hash: str = ""
    word_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    pr_number: Optional[int] = None
    branch_name: Optional[str] = None
    last_updated: float = field(default_factory=time.time)


@dataclass
class SwarmState:
    project_name: str
    version: str
    sections: Dict[str, SectionState] = field(default_factory=dict)
    contributor_matrix: Dict[str, List[str]] = field(default_factory=dict)  # actor -> list of section_ids
    active_locks: Dict[str, str] = field(default_factory=dict)  # section_id -> actor


class StateManager:
    """Manages persistent project state in .synapse/state.json with lease locks and dependency tracking."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.synapse_dir = project_root / ".synapse"
        self.state_file = self.synapse_dir / "state.json"
        self.synapse_dir.mkdir(parents=True, exist_ok=True)
        self.state = self._load_or_init()

    def _load_or_init(self) -> SwarmState:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sections = {
                    k: SectionState(**v) for k, v in data.get("sections", {}).items()
                }
                return SwarmState(
                    project_name=data.get("project_name", "SynapseForge Project"),
                    version=data.get("version", "0.1.0"),
                    sections=sections,
                    contributor_matrix=data.get("contributor_matrix", {}),
                    active_locks=data.get("active_locks", {}),
                )
            except Exception:
                pass
        return SwarmState(project_name="SynapseForge Project", version="0.1.0")

    def save(self) -> None:
        data = {
            "project_name": self.state.project_name,
            "version": self.state.version,
            "sections": {k: asdict(v) for k, v in self.state.sections.items()},
            "contributor_matrix": self.state.contributor_matrix,
            "active_locks": self.state.active_locks,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def sync_from_config(self, config: ProjectConfig) -> None:
        """Syncs declared sections in synapseforge.yaml into state machine."""
        self.state.project_name = config.name
        self.state.version = config.version

        for sec in config.sections:
            target_file = self.project_root / sec.file
            f_hash = self.compute_file_hash(target_file) if target_file.exists() else ""
            
            if sec.id not in self.state.sections:
                self.state.sections[sec.id] = SectionState(
                    id=sec.id,
                    title=sec.title,
                    file=sec.file,
                    status=SectionStatus.IDLE,
                    assigned_role=sec.assigned_role,
                    assigned_actor=sec.assigned_human or sec.assigned_role,
                    dependencies=sec.dependencies,
                    current_hash=f_hash,
                )
            else:
                s = self.state.sections[sec.id]
                s.title = sec.title
                s.file = sec.file
                s.dependencies = sec.dependencies
                s.current_hash = f_hash
        self.save()

    def claim_section(self, section_id: str, actor: str, lease_duration_seconds: int = 3600) -> bool:
        """Acquire lease lock on section for agent or human."""
        now = time.time()
        if section_id not in self.state.sections:
            raise KeyError(f"Section {section_id} not defined in state.")

        sec = self.state.sections[section_id]
        current_lock_holder = self.state.active_locks.get(section_id)

        # Check if currently locked by someone else and not expired
        if current_lock_holder and current_lock_holder != actor and sec.lock_expires_at > now:
            return False

        sec.status = SectionStatus.CLAIMED
        sec.assigned_actor = actor
        sec.lock_expires_at = now + lease_duration_seconds
        sec.last_updated = now
        self.state.active_locks[section_id] = actor

        # Update contributor matrix
        if actor not in self.state.contributor_matrix:
            self.state.contributor_matrix[actor] = []
        if section_id not in self.state.contributor_matrix[actor]:
            self.state.contributor_matrix[actor].append(section_id)

        self.save()
        return True

    def release_section(self, section_id: str, actor: str) -> bool:
        """Release lease lock on section."""
        if section_id in self.state.active_locks:
            if self.state.active_locks[section_id] == actor:
                del self.state.active_locks[section_id]
                if section_id in self.state.sections:
                    self.state.sections[section_id].lock_expires_at = 0.0
                self.save()
                return True
        return False

    def update_section_status(self, section_id: str, status: str, word_count: int = 0) -> None:
        if section_id in self.state.sections:
            sec = self.state.sections[section_id]
            sec.status = status
            sec.word_count = word_count
            sec.last_updated = time.time()
            target_file = self.project_root / sec.file
            if target_file.exists():
                sec.current_hash = self.compute_file_hash(target_file)
            self.save()

    def get_ready_sections(self) -> List[SectionState]:
        """Returns sections whose dependencies are all MERGED or APPROVED."""
        ready = []
        completed_ids = {
            s_id for s_id, s in self.state.sections.items()
            if s.status in (SectionStatus.APPROVED, SectionStatus.MERGED)
        }

        for s_id, s in self.state.sections.items():
            if s.status in (SectionStatus.IDLE, SectionStatus.CLAIMED):
                # Check all dependencies
                deps_met = all(dep in completed_ids for dep in s.dependencies)
                if deps_met:
                    ready.append(s)
        return ready

    def get_topological_order(self) -> List[str]:
        """Calculates topological execution order of sections."""
        graph: Dict[str, List[str]] = {k: list(v.dependencies) for k, v in self.state.sections.items()}
        visited: Set[str] = set()
        temp: Set[str] = set()
        order: List[str] = []

        def visit(node: str):
            if node in temp:
                raise ValueError(f"Cyclic section dependency detected around '{node}'")
            if node not in visited:
                temp.add(node)
                for dep in graph.get(node, []):
                    if dep in graph:
                        visit(dep)
                temp.remove(node)
                visited.add(node)
                order.append(node)

        for node in graph:
            if node not in visited:
                visit(node)

        return order

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        if not file_path.exists():
            return ""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()
