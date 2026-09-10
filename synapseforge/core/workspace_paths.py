"""Workspace-bound path checks for the local collaboration bus."""

from pathlib import Path
import os


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
