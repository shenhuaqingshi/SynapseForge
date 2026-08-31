"""
Atomic Section File Locking and Auto-Unlock Context Manager for SynapseForge.
Guarantees strict exclusivity when an AI Agent modifies a document section.
Automatically unlocks the file upon completion or exception.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional


class SectionLockedError(Exception):
    """Raised when an agent attempts to modify a section currently locked by another actor."""
    pass


class AutoSectionLock:
    """
    Context manager for atomic section file locking.
    
    Usage:
        with AutoSectionLock("sec_04_consensus", "Drafter-Narrative") as lock:
            lock.write_draft("# New Section Draft\\n\\n...")
            # Auto-unlocked upon exiting context!
    """

    def __init__(
        self,
        section_id: str,
        agent_name: str,
        workspace_root: Optional[Path] = None,
        timeout_seconds: int = 3600,
    ):
        self.section_id = section_id
        self.agent_name = agent_name
        self.workspace_root = workspace_root or Path.cwd()
        self.timeout_seconds = timeout_seconds

        self.locks_dir = self.workspace_root / ".synapse" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file_path = self.locks_dir / f"{section_id}.lock"
        self._file_handle = None

    def acquire(self) -> bool:
        """Atomically acquires the section lock. Raises SectionLockedError if held by another agent."""
        now = time.time()

        # Check if lock file exists and is still valid
        if self.lock_file_path.exists():
            try:
                data = json.loads(self.lock_file_path.read_text(encoding="utf-8"))
                holder = data.get("agent_name", "unknown")
                expires_at = data.get("expires_at", 0)

                # If held by another agent and not expired
                if holder != self.agent_name and expires_at > now:
                    remaining = int(expires_at - now)
                    raise SectionLockedError(
                        f"Section '{self.section_id}' is locked by agent '{holder}'. Lock expires in {remaining}s."
                    )
            except (json.JSONDecodeError, KeyError):
                pass  # Corrupted lock file, will overwrite

        # Create/open lock file with exclusive OS file lock
        self._file_handle = open(self.lock_file_path, "w+", encoding="utf-8")
        try:
            fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            self._file_handle.close()
            self._file_handle = None
            raise SectionLockedError(f"Section '{self.section_id}' is concurrently locked at the OS level.")

        # Write lock metadata
        metadata = {
            "section_id": self.section_id,
            "agent_name": self.agent_name,
            "locked_at": now,
            "expires_at": now + self.timeout_seconds,
            "pid": os.getpid(),
        }
        self._file_handle.seek(0)
        self._file_handle.truncate()
        self._file_handle.write(json.dumps(metadata, indent=2))
        self._file_handle.flush()

        return True

    def release(self) -> bool:
        """Releases the section lock and cleans up lock file."""
        if self._file_handle is not None:
            try:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

        if self.lock_file_path.exists():
            try:
                # Only delete if we own it
                data = json.loads(self.lock_file_path.read_text(encoding="utf-8"))
                if data.get("agent_name") == self.agent_name:
                    self.lock_file_path.unlink(missing_ok=True)
            except Exception:
                self.lock_file_path.unlink(missing_ok=True)

        return True

    def write_draft(self, content: str, target_file_path: Optional[Path] = None) -> Dict[str, Any]:
        """Safely writes drafted content to section file under lock."""
        if not target_file_path:
            sec_dir = self.workspace_root / "sections"
            # Find matching section file
            for p in sec_dir.glob("*.md"):
                if p.stem.startswith(self.section_id.replace("sec_", "")) or self.section_id in p.stem:
                    target_file_path = p
                    break
            if not target_file_path:
                target_file_path = sec_dir / f"{self.section_id}.md"

        target_file_path.parent.mkdir(parents=True, exist_ok=True)
        target_file_path.write_text(content, encoding="utf-8")

        return {
            "ok": True,
            "section_id": self.section_id,
            "agent": self.agent_name,
            "file": str(target_file_path.relative_to(self.workspace_root)),
            "words": len(content.split()),
        }

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False  # Do not suppress exceptions


class SectionLockManager:
    """Manager for querying, inspecting, and breaking locks."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.locks_dir = self.workspace_root / ".synapse" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def list_active_locks(self) -> List[Dict[str, Any]]:
        """Returns all currently active unexpired section locks."""
        now = time.time()
        active = []
        for p in sorted(self.locks_dir.glob("*.lock")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                expires_at = data.get("expires_at", 0)
                if expires_at > now:
                    data["remaining_seconds"] = int(expires_at - now)
                    active.append(data)
                else:
                    # Clean up expired stale lock
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        return active

    def is_locked(self, section_id: str) -> Optional[Dict[str, Any]]:
        """Checks if a section is currently locked."""
        lock_file = self.locks_dir / f"{section_id}.lock"
        if not lock_file.exists():
            return None

        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) > time.time():
                return data
            else:
                lock_file.unlink(missing_ok=True)
                return None
        except Exception:
            return None

    def force_unlock(self, section_id: str) -> bool:
        """Force releases a section lock (for administrator or emergency recovery)."""
        lock_file = self.locks_dir / f"{section_id}.lock"
        if lock_file.exists():
            lock_file.unlink(missing_ok=True)
            return True
        return False
