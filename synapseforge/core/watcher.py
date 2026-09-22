"""
Live Document Watcher & Automated Quality Gate Daemon for SynapseForge.
Monitors sections and bibliography for modifications, executes automated lint checks,
creates auto-snapshots, and dispatches activity events to the collaboration bus.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from synapseforge.core.scorecard import QualityScorecard
from synapseforge.core.snapshot import SnapshotManager
from synapseforge.linters import LintSuite


class FileChangeType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class WatchEvent:
    path: Path
    change_type: FileChangeType
    timestamp: float = field(default_factory=time.time)
    linter_passed: bool = True
    linter_issues_count: int = 0
    snapshot_created: bool = False
    snapshot_hash: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": str(self.path.name),
            "change_type": self.change_type.value,
            "timestamp": self.timestamp,
            "linter_passed": self.linter_passed,
            "linter_issues_count": self.linter_issues_count,
            "snapshot_created": self.snapshot_created,
            "snapshot_hash": self.snapshot_hash,
            "details": self.details,
        }


class DocumentWatcher:
    """Watches document sections and triggers live linting, score updates, and snapshots."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        auto_snapshot: bool = False,
        debounce_seconds: float = 0.5,
    ):
        self.workspace_root = workspace_root or Path.cwd()
        self.auto_snapshot = auto_snapshot
        self.debounce_seconds = debounce_seconds
        self.linter = LintSuite()
        self.scorecard = QualityScorecard(self.workspace_root)
        self.snapshot_mgr = SnapshotManager(self.workspace_root)
        self._file_hashes: Dict[str, str] = {}
        self._last_event_time: Dict[str, float] = {}
        self._initialize_hashes()

    def _get_watched_files(self) -> List[Path]:
        files: List[Path] = []
        sec_dir = self.workspace_root / "sections"
        if sec_dir.exists():
            files.extend(sec_dir.glob("*.md"))
            files.extend(sec_dir.glob("*.typ"))
        
        bib_file = self.workspace_root / "bibliography.bib"
        if bib_file.exists():
            files.append(bib_file)

        cfg_file = self.workspace_root / "synapseforge.yaml"
        if cfg_file.exists():
            files.append(cfg_file)

        return sorted(files)

    def _hash_file(self, path: Path) -> str:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _initialize_hashes(self):
        for f in self._get_watched_files():
            self._file_hashes[str(f)] = self._hash_file(f)

    def poll_once(self) -> List[WatchEvent]:
        """Polls watched files once and returns all detected change events."""
        events: List[WatchEvent] = []
        current_files = self._get_watched_files()
        current_paths_str = set(str(f) for f in current_files)
        old_paths_str = set(self._file_hashes.keys())

        # Check for deleted files
        for deleted_str in (old_paths_str - current_paths_str):
            del self._file_hashes[deleted_str]
            events.append(WatchEvent(
                path=Path(deleted_str),
                change_type=FileChangeType.DELETED,
            ))

        # Check for modified or created files
        for f in current_files:
            f_str = str(f)
            new_hash = self._hash_file(f)
            old_hash = self._file_hashes.get(f_str)

            if old_hash is None:
                # Created
                self._file_hashes[f_str] = new_hash
                event = self._process_file_change(f, FileChangeType.CREATED)
                events.append(event)
            elif new_hash != old_hash:
                # Modified
                now = time.time()
                last_time = self._last_event_time.get(f_str, 0.0)
                if now - last_time >= self.debounce_seconds:
                    self._file_hashes[f_str] = new_hash
                    self._last_event_time[f_str] = now
                    event = self._process_file_change(f, FileChangeType.MODIFIED)
                    events.append(event)

        return events

    def _process_file_change(self, file_path: Path, change_type: FileChangeType) -> WatchEvent:
        linter_passed = True
        issues_count = 0
        details = {}

        if file_path.suffix == ".md" and file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                report = self.linter.lint_text(content, filename=str(file_path.name))
                linter_passed = report.passed
                issues_count = len(report.all_issues)
                details["errors"] = len(report.errors)
                details["warnings"] = len(report.warnings)
            except Exception as e:
                details["lint_error"] = str(e)

        snap_created = False
        snap_hash = None
        if self.auto_snapshot and change_type == FileChangeType.MODIFIED:
            try:
                snap_res = self.snapshot_mgr.create_checkpoint(
                    message=f"Auto-snapshot on {file_path.name} {change_type.value}",
                    author="SynapseWatcher",
                )
                if snap_res.get("ok"):
                    snap_created = snap_res.get("created", True)
                    snap_hash = snap_res.get("commit_hash") or snap_res.get("hash")
            except Exception as e:
                details["snapshot_error"] = str(e)

        return WatchEvent(
            path=file_path,
            change_type=change_type,
            linter_passed=linter_passed,
            linter_issues_count=issues_count,
            snapshot_created=snap_created,
            snapshot_hash=snap_hash,
            details=details,
        )

    def watch_loop(
        self,
        interval: float = 1.0,
        max_iterations: Optional[int] = None,
        on_event: Optional[Callable[[WatchEvent], None]] = None,
    ) -> List[WatchEvent]:
        """Runs continuous watching loop until interrupted or max_iterations reached."""
        all_events: List[WatchEvent] = []
        iterations = 0
        try:
            while True:
                events = self.poll_once()
                for ev in events:
                    all_events.append(ev)
                    if on_event:
                        on_event(ev)

                iterations += 1
                if max_iterations is not None and iterations >= max_iterations:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass

        return all_events
