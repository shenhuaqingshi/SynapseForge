"""
Multi-Model LLM Swarm Router for SynapseForge.
Manages provider routing (DeepSeek, Ollama, vLLM, OpenAI, Gemini, Claude) and GPU node connectivity.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMProviderSpec:
    name: str
    provider_type: str  # "ollama", "vllm", "deepseek", "openai", "gemini", "anthropic"
    endpoint_url: str
    model: str
    latency_ms: float = 0.0
    status: str = "configured"  # "ready", "unreachable", "configured"


class LLMRouter:
    """Manages AI model providers, API routing, and local/remote GPU node latency."""

    def __init__(self):
        self.providers: Dict[str, LLMProviderSpec] = {
            "deepseek": LLMProviderSpec(
                name="DeepSeek Cloud",
                provider_type="deepseek",
                endpoint_url="https://api.deepseek.com/v1",
                model="deepseek-reasoner",
            ),
            "ollama_local": LLMProviderSpec(
                name="Local Ollama Node",
                provider_type="ollama",
                endpoint_url="http://127.0.0.1:11434",
                model="deepseek-r1:14b",
            ),
            "vllm_gpu_mesh": LLMProviderSpec(
                name="Tailscale GPU Cluster",
                provider_type="vllm",
                endpoint_url="http://100.64.0.10:8000/v1",
                model="Qwen2.5-72B-Instruct",
            ),
            "gemini": LLMProviderSpec(
                name="Google Gemini",
                provider_type="gemini",
                endpoint_url="https://generativelanguage.googleapis.com",
                model="gemini-2.0-flash",
            ),
        }

    def list_providers(self) -> List[Dict[str, Any]]:
        """Returns all configured LLM providers and their capabilities."""
        return [
            {
                "id": k,
                "name": p.name,
                "type": p.provider_type,
                "endpoint": p.endpoint_url,
                "model": p.model,
                "status": p.status,
            }
            for k, p in self.providers.items()
        ]

    def ping_provider(self, provider_id: str) -> Dict[str, Any]:
        """Pings provider endpoint and returns round-trip latency."""
        if provider_id not in self.providers:
            return {"ok": False, "error": f"Provider '{provider_id}' not found"}

        p = self.providers[provider_id]
        # Check endpoint
        import urllib.request
        start_t = time.time()
        try:
            req = urllib.request.Request(p.endpoint_url, method="HEAD")
            with urllib.request.urlopen(req, timeout=3) as resp:
                latency = (time.time() - start_t) * 1000
                p.latency_ms = round(latency, 1)
                p.status = "ready"
                return {"ok": True, "provider": p.name, "latency_ms": p.latency_ms, "status": "online"}
        except Exception:
            p.status = "unreachable"
            return {"ok": False, "provider": p.name, "latency_ms": None, "status": "unreachable",
                    "error": f"Provider '{provider_id}' endpoint unreachable: {p.endpoint_url}"}
