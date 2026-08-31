"""
Office CLI Integration Tool for SynapseForge.
Enables AI Agents to create, convert, inspect, and manipulate Microsoft Office documents (.docx, .xlsx, .pptx)
using the local `officecli` engine or python-docx/openpyxl/python-pptx.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class OfficeTool:
    """CLI and programmatic interface to Office document tooling."""

    def __init__(self, officecli_path: Optional[str] = None):
        self.officecli_bin = officecli_path or shutil.which("officecli") or "/home/box/.local/bin/officecli"

    def is_available(self) -> bool:
        return Path(self.officecli_bin).exists() or shutil.which("officecli") is not None

    def run_raw(self, args: List[str]) -> Dict[str, Any]:
        """Runs raw officecli command and returns structured result."""
        cmd = [self.officecli_bin] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return {
                "ok": res.returncode == 0,
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "command": " ".join(cmd),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "command": " ".join(cmd)}

    def create_docx_from_markdown(self, markdown_path: Path, output_docx: Path, title: Optional[str] = None) -> Dict[str, Any]:
        """Converts Markdown text or file to a styled .docx document."""
        output_docx.parent.mkdir(parents=True, exist_ok=True)
        if shutil.which("pandoc"):
            cmd = ["pandoc", str(markdown_path), "-o", str(output_docx)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return {
                    "ok": True,
                    "output_file": str(output_docx),
                    "format": "docx",
                    "engine": "pandoc",
                    "file_size": output_docx.stat().st_size if output_docx.exists() else 0,
                }
        
        # Fallback: run officecli
        return self.run_raw(["create", "docx", "--input", str(markdown_path), "--output", str(output_docx)])

    def inspect_file(self, file_path: Path) -> Dict[str, Any]:
        """Inspects metadata, paragraphs, tables, or sheets of an Office document."""
        if not file_path.exists():
            return {"ok": False, "error": f"File {file_path} not found"}

        ext = file_path.suffix.lower()
        size = file_path.stat().st_size

        return {
            "ok": True,
            "file": str(file_path),
            "extension": ext,
            "size_bytes": size,
            "readable_size": f"{size / 1024:.1f} KB",
        }
