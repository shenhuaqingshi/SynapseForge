"""
Node Access Control and Room Authentication Tokens for SynapseForge.
Guarantees only authorized humans and designated swarm agents can join Tailscale collaboration rooms.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AccessToken:
    room_id: str
    node_id: str
    role: str  # "commander" | "drafter" | "reviewer" | "observer"
    issued_at: float
    expires_at: float
    signature: str


class NodeAccessController:
    """Issues and verifies HMAC-SHA256 signed access tokens for distributed rooms."""

    def __init__(self, secret_key: Optional[str] = None, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.secret_file = self.workspace_root / ".synapse" / "acl_secret.key"
        self.secret_key = secret_key or self._get_or_create_secret()

    def _get_or_create_secret(self) -> str:
        self.secret_file.parent.mkdir(parents=True, exist_ok=True)
        if self.secret_file.exists():
            return self.secret_file.read_text(encoding="utf-8").strip()
        key = base64.b64encode(hashlib.sha256(str(time.time()).encode()).digest()).decode("utf-8")
        self.secret_file.write_text(key, encoding="utf-8")
        return key

    def generate_token(
        self,
        room_id: str,
        node_id: str,
        role: str = "drafter",
        valid_duration_seconds: int = 86400,
    ) -> Dict[str, Any]:
        """Generates a cryptographically signed room join token."""
        now = time.time()
        payload = {
            "room_id": room_id,
            "node_id": node_id,
            "role": role,
            "issued_at": now,
            "expires_at": now + valid_duration_seconds,
        }
        raw_msg = f"{room_id}:{node_id}:{role}:{payload['issued_at']}:{payload['expires_at']}"
        sig = hmac.new(self.secret_key.encode("utf-8"), raw_msg.encode("utf-8"), hashlib.sha256).hexdigest()
        payload["signature"] = sig
        token_str = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        return {
            "ok": True,
            "token": token_str,
            "room_id": room_id,
            "node_id": node_id,
            "role": role,
            "expires_in_hours": valid_duration_seconds / 3600,
        }

    def verify_token(self, token_str: str) -> Dict[str, Any]:
        """Verifies room access token validity, signature, and expiration."""
        try:
            raw_json = base64.b64decode(token_str.encode("utf-8")).decode("utf-8")
            data = json.loads(raw_json)
            raw_msg = f"{data['room_id']}:{data['node_id']}:{data['role']}:{data['issued_at']}:{data['expires_at']}"
            computed_sig = hmac.new(self.secret_key.encode("utf-8"), raw_msg.encode("utf-8"), hashlib.sha256).hexdigest()

            if not hmac.compare_digest(computed_sig, data.get("signature", "")):
                return {"valid": False, "error": "Invalid token signature"}

            if time.time() > data.get("expires_at", 0):
                return {"valid": False, "error": "Token has expired"}

            return {"valid": True, "payload": data}
        except Exception as e:
            return {"valid": False, "error": str(e)}
