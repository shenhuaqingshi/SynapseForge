"""Exact section-file resolution.

Substring globs such as ``*{section_id}*.md`` treat ``1`` as a match for both
``01_abstract.md`` and ``10_conclusion.md``. Callers must use this helper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


def numeric_key(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if raw.startswith("sec_"):
        raw = raw[4:]
    head = raw.split("_")[0]
    if head.isdigit():
        return str(int(head))
    return None


def resolve_section_path(workspace_root: PathLike, section_id: str, create_dir: bool = True) -> Path:
    """Return the markdown file for ``section_id`` under ``<workspace>/sections``.

    Matching order:
    1. Exact stem (``sec_01`` or ``01_abstract_introduction``)
    2. Unique numeric prefix (``1`` / ``sec_01`` / ``01`` → ``01_*.md``, never ``10_*.md``)
    3. Fallback path ``sections/{section_id}.md`` (may not exist yet)
    """
    root = Path(workspace_root)
    sec_dir = root / "sections"
    if create_dir:
        sec_dir.mkdir(parents=True, exist_ok=True)
    section_id = (section_id or "").strip()
    if not section_id:
        return sec_dir / "untitled.md"
    # Never let section_id walk out of sections/ via ../ or absolute paths.
    if "/" in section_id or "\\" in section_id or section_id in {".", ".."}:
        section_id = Path(section_id).name
    if (not section_id) or section_id in {".", ".."} or "/" in section_id or "\\" in section_id:
        return sec_dir / "untitled.md"
    clean = section_id[4:] if section_id.startswith("sec_") else section_id
    files = sorted(sec_dir.glob("*.md")) if sec_dir.exists() else []
    for path in files:
        if path.stem == section_id or path.stem == clean:
            return path
    wanted = numeric_key(section_id)
    if wanted is not None:
        matches = [path for path in files if numeric_key(path.stem) == wanted]
        if len(matches) == 1:
            return matches[0]
        padded = wanted.zfill(2)
        for path in matches:
            prefix = path.stem.split("_")[0]
            if prefix in {wanted, padded}:
                return path
    return sec_dir / f"{section_id}.md"
