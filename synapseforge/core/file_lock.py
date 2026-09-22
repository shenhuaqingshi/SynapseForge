"""
Atomic section file locking for SynapseForge.

The previous acquire path checked a JSON lease, then opened the lock file
with ``w+`` (truncating it) and only then took an OS lock. Two agents could
pass the JSON check, the second truncate could wipe the first writer's
metadata, and a dead PID could hold a lease until wall-clock expiry.

This implementation:
- Opens without truncating, then takes an exclusive OS lock (fcntl / msvcrt)
- Reads existing metadata under that lock
- Treats a dead holder PID as stale even if the lease has not expired
- Refreshes ``expires_at`` via ``heartbeat()``
- Releases on context-manager exit, including exceptions
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def pid_alive(pid: Any) -> Optional[bool]:
    """Return True if pid is alive, False if known-dead, None if unknown."""
    try:
        pid_i = int(pid or 0)
    except (TypeError, ValueError):
        return None
    if pid_i <= 0:
        return None
    try:
        os.kill(pid_i, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def _holder_is_live(data: Dict[str, Any], now: float) -> bool:
    if float(data.get("expires_at") or 0) <= now:
        return False
    alive = pid_alive(data.get("pid"))
    if alive is False:
        return False
    return True


class AutoSectionLock:
    """
    Context manager for atomic section file locking across Windows, macOS, and Linux.

    Usage::

        with AutoSectionLock("sec_04_consensus", "Drafter-Narrative", workspace) as lock:
            lock.heartbeat()
            lock.write_draft("# New Section Draft\\n\\n...")
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
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.timeout_seconds = timeout_seconds

        self.locks_dir = self.workspace_root / ".synapse" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file_path = self.locks_dir / f"{section_id}.lock"
        self._file_handle = None
        self._acquired = False

    def _os_lock(self) -> None:
        assert self._file_handle is not None
        if HAS_FCNTL and fcntl is not None:
            try:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (BlockingIOError, OSError) as exc:
                raise SectionLockedError(
                    f"Section '{self.section_id}' is concurrently locked at the OS level."
                ) from exc
        if HAS_MSVCRT and msvcrt is not None:
            try:
                self._file_handle.seek(0)
                msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except (BlockingIOError, OSError, IOError) as exc:
                raise SectionLockedError(
                    f"Section '{self.section_id}' is concurrently locked at the Windows OS level."
                ) from exc

    def _os_unlock(self) -> None:
        if self._file_handle is None:
            return
        try:
            if HAS_FCNTL and fcntl is not None:
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT and msvcrt is not None:
                self._file_handle.seek(0)
                msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass

    def _read_metadata(self) -> Optional[Dict[str, Any]]:
        assert self._file_handle is not None
        try:
            self._file_handle.seek(0)
            raw = self._file_handle.read()
            if not raw.strip():
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None

    def _write_metadata(self, now: Optional[float] = None) -> Dict[str, Any]:
        assert self._file_handle is not None
        now = time.time() if now is None else now
        metadata = {
            "section_id": self.section_id,
            "agent_name": self.agent_name,
            "locked_at": now,
            "expires_at": now + self.timeout_seconds,
            "last_heartbeat": now,
            "pid": os.getpid(),
            "platform": sys.platform,
        }
        payload = json.dumps(metadata, indent=2)
        self._file_handle.seek(0)
        self._file_handle.truncate()
        self._file_handle.write(payload)
        self._file_handle.flush()
        try:
            os.fsync(self._file_handle.fileno())
        except OSError:
            pass
        return metadata

    def acquire(self) -> bool:
        """Atomically acquire the section lock. Raises SectionLockedError on conflict."""
        now = time.time()
        self._file_handle = open(self.lock_file_path, "a+", encoding="utf-8")
        try:
            self._os_lock()
        except SectionLockedError:
            self._file_handle.close()
            self._file_handle = None
            raise

        existing = self._read_metadata()
        if existing:
            holder = existing.get("agent_name", "unknown")
            if holder != self.agent_name and _holder_is_live(existing, now):
                remaining = int(float(existing.get("expires_at", 0)) - now)
                self._os_unlock()
                self._file_handle.close()
                self._file_handle = None
                raise SectionLockedError(
                    f"Section '{self.section_id}' is locked by agent '{holder}'. "
                    f"Lock expires in {max(remaining, 0)}s."
                )

        self._write_metadata(now)
        self._acquired = True
        return True

    def heartbeat(self) -> Dict[str, Any]:
        """Refresh lease expiry so long-running agents are not stolen mid-edit."""
        if not self._acquired or self._file_handle is None:
            raise SectionLockedError(f"Section '{self.section_id}' is not held by this lock.")
        return self._write_metadata()

    def release(self) -> bool:
        """Release the section lock and clean up the lock file if we still own it."""
        owned = self._acquired
        agent = self.agent_name
        handle = self._file_handle
        self._acquired = False
        self._file_handle = None

        if handle is not None:
            try:
                handle.seek(0)
                raw = handle.read()
                data = json.loads(raw) if raw.strip() else {}
                still_ours = data.get("agent_name") == agent
            except Exception:
                still_ours = True
            self._file_handle = handle
            self._os_unlock()
            try:
                handle.close()
            except Exception:
                pass
            self._file_handle = None
            if owned and still_ours and self.lock_file_path.exists():
                try:
                    self.lock_file_path.unlink(missing_ok=True)
                except OSError:
                    pass
        elif owned and self.lock_file_path.exists():
            try:
                data = json.loads(self.lock_file_path.read_text(encoding="utf-8"))
                if data.get("agent_name") == agent:
                    self.lock_file_path.unlink(missing_ok=True)
            except Exception:
                try:
                    self.lock_file_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return True

    def write_draft(self, content: str, target_file_path: Optional[Path] = None) -> Dict[str, Any]:
        """Safely write drafted content to a section file while the lock is held."""
        if not self._acquired:
            raise SectionLockedError(
                f"Section '{self.section_id}' must be locked before writing."
            )
        if target_file_path:
            path = Path(target_file_path)
        else:
            from synapseforge.core.section_paths import resolve_section_path
            path = resolve_section_path(self.workspace_root, self.section_id)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.heartbeat()
        return {
            "ok": True,
            "section_id": self.section_id,
            "target_file": str(path),
            "bytes_written": len(content.encode("utf-8")),
            "agent_name": self.agent_name,
        }

    def __enter__(self) -> AutoSectionLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


class SectionLockManager:
    """Inspect, query, heartbeat-aware reclaim, and list active section locks."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.locks_dir = self.workspace_root / ".synapse" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def _load(self, lock_file: Path) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def is_locked(self, section_id: str) -> Optional[Dict[str, Any]]:
        """Return lock metadata if the section is actively locked, else None."""
        lock_file = self.locks_dir / f"{section_id}.lock"
        if not lock_file.exists():
            return None
        data = self._load(lock_file)
        if not data:
            return None
        if _holder_is_live(data, time.time()):
            return data
        try:
            lock_file.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    def list_active_locks(self) -> List[Dict[str, Any]]:
        """List currently live (non-expired, non-dead-PID) section locks."""
        active: List[Dict[str, Any]] = []
        now = time.time()
        for path in self.locks_dir.glob("*.lock"):
            data = self._load(path)
            if not data:
                continue
            if _holder_is_live(data, now):
                data["remaining_seconds"] = int(float(data.get("expires_at", 0)) - now)
                active.append(data)
            else:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        return active

    def reclaim_stale(self) -> Dict[str, Any]:
        """Drop expired or dead-PID locks. Returns how many were reclaimed."""
        reclaimed = 0
        remaining = []
        now = time.time()
        for path in self.locks_dir.glob("*.lock"):
            data = self._load(path)
            if not data or not _holder_is_live(data, now):
                try:
                    path.unlink(missing_ok=True)
                    reclaimed += 1
                except OSError:
                    pass
            else:
                remaining.append(data)
        return {"reclaimed": reclaimed, "remaining": remaining}
