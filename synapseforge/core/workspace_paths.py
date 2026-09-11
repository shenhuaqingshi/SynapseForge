"""Workspace-bound path checks for the local collaboration bus."""

import os
from pathlib import Path


def path_inside(resolved, root):
    if not root:
        return False
    try:
        left = Path(resolved).resolve()
        base = Path(root).resolve()
        return left == base or left.is_relative_to(base)
    except (ValueError, OSError):
        left = str(Path(resolved))
        base = str(Path(root)).rstrip("/")
        return left == base or left.startswith(base + os.sep)


def resolve_against(root, raw):
    candidate = Path(str(raw)).expanduser()
    if not candidate.is_absolute() and root:
        candidate = Path(root) / candidate
    return str(candidate.resolve())


def patch_team_bus(team_bus_cls):
    """Bind share/lock/unlock/claim paths to the room workspace."""
    if getattr(team_bus_cls, "_workspace_paths_patched", False):
        return team_bus_cls

    original_share = team_bus_cls.share_document
    original_unlock = team_bus_cls.unlock_files

    def _resolve_room_path(self, conn, room, raw, allow_shared=True):
        workspace = self._room_workspace(conn, room)
        allowed = self._shared_document_paths(conn, room) if allow_shared else set()
        resolved = resolve_against(workspace, raw)
        if workspace and not path_inside(resolved, workspace) and resolved not in allowed:
            raise ValueError(
                "path is outside the room workspace: %s (workspace=%s)"
                % (resolved, workspace)
            )
        return resolved

    def _normalize_lock_paths(self, conn, room, paths):
        return [self._resolve_room_path(conn, room, raw, allow_shared=True) for raw in (paths or [])]

    def share_document(self, room, agent, path, title="", copy_content=True):
        with self.connection() as conn:
            room_name = self._ensure_room(conn, room)
            path = self._resolve_room_path(conn, room_name, path, allow_shared=True)
        return original_share(self, room, agent, path, title=title, copy_content=copy_content)

    def unlock_files(self, room, agent, paths=None):
        if not paths:
            return original_unlock(self, room, agent, paths)
        with self.connection() as conn:
            room_name = self._ensure_room(conn, room)
            normalized = self._normalize_lock_paths(conn, room_name, paths)
        return original_unlock(self, room, agent, normalized)

    team_bus_cls._path_inside = staticmethod(path_inside)
    team_bus_cls._resolve_room_path = _resolve_room_path
    team_bus_cls._normalize_lock_paths = _normalize_lock_paths
    team_bus_cls.share_document = share_document
    team_bus_cls.unlock_files = unlock_files
    team_bus_cls._workspace_paths_patched = True
    return team_bus_cls
