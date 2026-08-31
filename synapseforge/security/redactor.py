"""
Confidentiality Redaction and Anti-Exfiltration Engine for SynapseForge.
Scans and masks API keys, secrets, PII, and user-defined proprietary keywords
before dispatching prompts to LLM agents or syncing across public networks.
Supports authorized local rehydration.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Common secret patterns
SECRET_PATTERNS = [
    (r'sk-[a-zA-Z0-9_\-]{20,}', "API_KEY"),
    (r'ghp_[a-zA-Z0-9]{36}', "GITHUB_TOKEN"),
    (r'AKIA[0-9A-Z]{16}', "AWS_ACCESS_KEY"),
    (r'-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----', "SSH_PRIVATE_KEY"),
    (r'(?i)(?:password|secret|token|api_key)\s*[:=]\s*["\']([^"\'\s]{8,})["\']', "GENERIC_SECRET"),
    (r'\b1[3-9]\d{9}\b', "PHONE_NUMBER_CN"),
    (r'\b\d{17}[\dXx]\b', "NATIONAL_ID_CN"),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', "EMAIL_ADDRESS"),
]


@dataclass
class RedactionIssue:
    line_number: int
    matched_type: str
    redacted_preview: str
    original_snippet: str


class ConfidentialityRedactor:
    """Manages secret scanning, masking, and two-way deterministic rehydration."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.config_file = self.workspace_root / ".synapse" / "classified_keywords.json"
        self.mapping_file = self.workspace_root / ".synapse" / "redaction_vault.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_custom_keywords(self) -> List[str]:
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text(encoding="utf-8"))
                return data.get("classified_terms", [])
            except Exception:
                return []
        return []

    def add_classified_term(self, term: str) -> None:
        """User registers a custom confidential keyword or project codename."""
        terms = self._load_custom_keywords()
        if term not in terms:
            terms.append(term)
            self.config_file.write_text(json.dumps({"classified_terms": terms}, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_classified_terms(self) -> List[str]:
        return self._load_custom_keywords()

    def scan_for_secrets(self, text: str) -> List[RedactionIssue]:
        """Audits document text for secrets, PII, and custom classified terms."""
        issues = []
        lines = text.split("\n")

        # 1. Check regex secret patterns
        for line_idx, line in enumerate(lines, start=1):
            for pattern, p_name in SECRET_PATTERNS:
                for match in re.finditer(pattern, line):
                    val = match.group(0)
                    issues.append(RedactionIssue(
                        line_number=line_idx,
                        matched_type=p_name,
                        redacted_preview=f"[REDACTED_{p_name}]",
                        original_snippet=val[:4] + "***" + val[-4:] if len(val) > 8 else "***",
                    ))

        # 2. Check user classified terms
        custom_terms = self._load_custom_keywords()
        for line_idx, line in enumerate(lines, start=1):
            for term in custom_terms:
                if term and term in line:
                    issues.append(RedactionIssue(
                        line_number=line_idx,
                        matched_type="CUSTOM_CLASSIFIED_TERM",
                        redacted_preview=f"[CONFIDENTIAL:{term[0]}***]",
                        original_snippet=term,
                    ))

        return issues

    def redact(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Masks all sensitive data with reversible placeholder tokens.
        Returns the sanitized text and the token lookup table.
        """
        sanitized = text
        token_map: Dict[str, str] = {}

        # 1. Custom Classified terms first
        custom_terms = self._load_custom_keywords()
        for term in custom_terms:
            if term and term in sanitized:
                token = f"⟦SEC_TERM_{hashlib.sha256(term.encode()).hexdigest()[:8]}⟧"
                token_map[token] = term
                sanitized = sanitized.replace(term, token)

        # 2. Regex Patterns
        for pattern, p_name in SECRET_PATTERNS:
            def repl(match):
                original = match.group(0)
                token = f"⟦SEC_{p_name}_{hashlib.sha256(original.encode()).hexdigest()[:8]}⟧"
                token_map[token] = original
                return token

            sanitized = re.sub(pattern, repl, sanitized)

        return sanitized, token_map

    def unredact(self, sanitized_text: str, token_map: Dict[str, str]) -> str:
        """Rehydrates masked tokens back into their original values."""
        rehydrated = sanitized_text
        for token, original in token_map.items():
            rehydrated = rehydrated.replace(token, original)
        return rehydrated
