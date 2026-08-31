"""
Multi-Channel Notification Dispatcher for SynapseForge.
Alerts the human commander across Email, Webhooks, and GitHub when agent tasks complete.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class NotificationDispatcher:
    """Dispatches milestone alerts and reports to human author via Email, Webhooks, or CLI."""

    def __init__(self, user_email: str = "361487867@qq.com"):
        self.user_email = user_email
        self.has_agently = shutil.which("agently-cli") is not None

    def send_notification(
        self,
        title: str,
        message: str,
        channel: str = "email",
        attachments: Optional[List[Path]] = None,
    ) -> Dict[str, Any]:
        """Dispatches notification to designated channel."""
        if channel == "email" and self.has_agently:
            cmd = [
                "agently-cli", "message", "+send",
                "--to", self.user_email,
                "--subject", f"[SynapseForge Alert] {title}",
                "--body", message,
                "--confirmed"
            ]
            if attachments:
                for att in attachments:
                    if att.exists():
                        cmd.extend(["--attachment", str(att)])

            try:
                res = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if res.returncode != 0:
                    err_summary = (res.stderr or res.stdout or "no output").strip()[:500]
                    return {
                        "ok": False,
                        "channel": "email",
                        "error": f"agently-cli exited with code {res.returncode}: {err_summary}",
                    }
                return {"ok": True, "channel": "email", "recipient": self.user_email, "title": title}
            except Exception as e:
                return {"ok": False, "channel": "email", "error": str(e)}

        # Fallback: agently-cli unavailable or non-email channel; nothing was actually delivered
        return {
            "ok": False,
            "channel": channel,
            "title": title,
            "message": message,
            "status": "not_sent",
            "error": "agently-cli not found; notification was not sent (no delivery channel available)",
        }
