"""
Atomic Section File Locking and Auto-Unlock Context Manager for SynapseForge.
Guarantees strict exclusivity when an AI Agent modifies a document section.
Cross-Platform Support for Windows (msvcrt), macOS (fcntl), and Linux (fcntl).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Cross-platform OS lock imports
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    fcntl = None  # type: ignore
    HAS_FCNTL = False

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    msvcrt = None  # type: ignore
    HAS_MSVCRT = False


class SectionLockedError(Exception):
    """Raised when an agent attempts to modify a section currently locked by another actor."""
    pass


class AutoSectionLock:
    """
    Context manager for atomic section file locking across Windows, macOS, and Linux.
    
    Usage:
        with AutoSectionLock("sec_04_consensus", "Drafter-Narrative") as lock:
            lock.write_draft("# New Section Draft\n\n...")
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
        """Atomically acquires the section lock across Windows, macOS, and Linux."""
        now = time.time()

        # 1. Check logical JSON lease
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

        # 2. Open lock file with exclusive OS file lock
        self._file_handle = open(self.lock_file_path, "w+", encoding="utf-8")

        # POSIX (Linux / macOS)
        if HAS_FCNTL and fcntl is not None:
            try:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                self._file_handle.close()
                self._file_handle = None
                raise SectionLockedError(f"Section '{self.section_id}' is concurrently locked at the OS level.")

        # Windows (msvcrt)
        elif HAS_MSVCRT and msvcrt is not None:
            try:
                self._file_handle.seek(0)
                msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
            except (BlockingIOError, OSError, IOError):
                self._file_handle.close()
                self._file_handle = None
                raise SectionLockedError(f"Section '{self.section_id}' is concurrently locked at the Windows OS level.")

        # 3. Write lock metadata
        metadata = {
            "section_id": self.section_id,
            "agent_name": self.agent_name,
            "locked_at": now,
            "expires_at": now + self.timeout_seconds,
            "pid": os.getpid(),
            "platform": sys.platform,
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
                if HAS_FCNTL and fcntl is not None:
                    fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                elif HAS_MSVCRT and msvcrt is not None:
                    self._file_handle.seek(0)
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
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
        sec_dir = self.workspace_root / "sections"
        sec_dir.mkdir(parents=True, exist_ok=True)

        if target_file_path:
            p = Path(target_file_path)
        else:
            # Find matching file in sections/
            matches = list(sec_dir.glob(f"*{self.section_id}*.md"))
            p = matches[0] if matches else (sec_dir / f"{self.section_id}.md")

        p.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "section_id": self.section_id,
            "target_file": str(p),
            "bytes_written": len(content.encode("utf-8")),
            "agent_name": self.agent_name,
        }

    def __enter__(self) -> AutoSectionLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


class SectionLockManager:
    """Utility class to inspect, query, and manage active section locks across Windows, macOS, and Linux."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.locks_dir = self.workspace_root / ".synapse" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def is_locked(self, section_id: str) -> Optional[Dict[str, Any]]:
        """Returns lock metadata if section is actively locked, or None."""
        lock_file = self.locks_dir / f"{section_id}.lock"
        if not lock_file.exists():
            return None

        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) > time.time():
                return data
            else:
                # Expired lock
                lock_file.unlink(missing_ok=True)
                return None
        except Exception:
            return None

    def list_active_locks(self) -> List[Dict[str, Any]]:
        """Lists all currently active non-expired section locks."""
        active = []
        now = time.time()
        for p in self.locks_dir.glob("*.lock"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("expires_at", 0) > now:
                    data["remaining_seconds"] = int(data["expires_at"] - now)
                    active.append(data)
                else:
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        return active
