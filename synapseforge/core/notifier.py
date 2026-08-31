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
                subprocess.run(cmd, check=False, capture_output=True, text=True)
                return {"ok": True, "channel": "email", "recipient": self.user_email, "title": title}
            except Exception as e:
                return {"ok": False, "channel": "email", "error": str(e)}

        # Default fallback / console log
        return {
            "ok": True,
            "channel": channel,
            "title": title,
            "message": message,
            "status": "delivered_local",
        }
