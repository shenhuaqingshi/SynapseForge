"""
SynapseForge Remote Web Server and Control Daemon.
Provides web-based remote control, live document editing, and REST API for mobile/remote humans
over Tailscale WireGuard Mesh or local networks.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from synapseforge.config import load_config
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.core.engine import SwarmEngine
from synapseforge.tools.pdf_tool import PDFTool
from synapseforge.tools.sci_plot_tool import SciPlotTool


class SynapseForgeRemoteHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for SynapseForge Remote Control Web UI and REST API."""

    def __init__(self, *args, **kwargs):
        self.root_dir = Path.cwd()
        super().__init__(*args, directory=str(self.root_dir), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html", "/studio"):
            ui_file = self.root_dir / "synapseforge" / "ui" / "index.html"
            if ui_file.exists():
                content = ui_file.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        elif path == "/api/status":
            self._handle_api_status()
            return

        elif path == "/api/sections":
            self._handle_api_sections()
            return

        elif path.startswith("/assets/") or path.startswith("/dist/"):
            super().do_GET()
            return

        # Default fallback to parent SimpleHTTPRequestHandler
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/doc/save":
            self._handle_api_save(data)
        elif path == "/api/agent/dispatch":
            self._handle_api_dispatch(data)
        elif path == "/api/pdf/build":
            self._handle_api_pdf_build(data)
        else:
            self._send_json({"ok": False, "error": f"Unknown endpoint: {path}"}, status=HTTPStatus.NOT_FOUND)

    def _send_json(self, data: Dict[str, Any], status: int = HTTPStatus.OK):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_api_status(self):
        engine = SwarmEngine()
        tree = engine.get_document_tree()
        config = load_config()
        self._send_json({
            "ok": True,
            "project_name": config.name,
            "document_title": config.document_title,
            "tailscale_mesh": config.tailscale.tailnet,
            "sections_count": len(tree),
            "tree": tree,
        })

    def _handle_api_sections(self):
        sec_dir = self.root_dir / "sections"
        sections = {}
        for p in sorted(sec_dir.glob("*.md")):
            sec_num = p.stem.split("_")[0]
            sections[f"sec_{sec_num}"] = {
                "name": p.name,
                "content": p.read_text(encoding="utf-8"),
            }
        self._send_json({"ok": True, "sections": sections})

    def _handle_api_save(self, data: Dict[str, Any]):
        section_id = data.get("section_id", "")
        content = data.get("content", "")
        if not section_id or not content:
            self._send_json({"ok": False, "error": "Missing section_id or content"}, status=HTTPStatus.BAD_REQUEST)
            return

        sec_dir = self.root_dir / "sections"
        target_file = None
        for p in sec_dir.glob("*.md"):
            if p.stem.startswith(section_id.replace("sec_", "")) or section_id in p.stem:
                target_file = p
                break

        if not target_file:
            target_file = sec_dir / f"{section_id}.md"

        target_file.write_text(content, encoding="utf-8")
        parser = MarkdownASTParser()
        words = parser.count_words(content)

        self._send_json({
            "ok": True,
            "file": str(target_file.relative_to(self.root_dir)),
            "word_count": words,
            "message": "Saved successfully",
        })

    def _handle_api_dispatch(self, data: Dict[str, Any]):
        agent_name = data.get("agent", "Drafter-Narrative")
        section_id = data.get("section_id", "sec_04")
        prompt = data.get("prompt", "")

        # Simulate agent execution response
        self._send_json({
            "ok": True,
            "agent": agent_name,
            "section_id": section_id,
            "task_id": f"task-{os.urandom(4).hex()}",
            "status": "completed",
            "message": f"Agent {agent_name} processed directive for {section_id}",
        })

    def _handle_api_pdf_build(self, data: Dict[str, Any]):
        tool = PDFTool()
        input_file = self.root_dir / "sections" / "01_abstract_introduction.md"
        output_pdf = self.root_dir / "dist" / "remote_build_report.pdf"
        res = tool.compile_markdown_to_pdf(input_file, output_pdf, title=data.get("title", "SynapseForge Remote Build"))
        self._send_json(res)


def start_server(host: str = "0.0.0.0", port: int = 8765) -> ThreadingHTTPServer:
    """Starts the SynapseForge remote daemon HTTP server."""
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, SynapseForgeRemoteHandler)
    return httpd
