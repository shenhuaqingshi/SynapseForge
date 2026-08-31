"""
Configuration manager for SynapseForge collaborative projects.
Loads and validates synapseforge.yaml project configuration files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class SwarmAgentConfig:
    role: str
    name: str
    model: str = "inherit"
    responsibilities: List[str] = field(default_factory=list)
    system_prompt_override: Optional[str] = None


@dataclass
class QualityGateConfig:
    anti_ai: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "ban_cliches": True,
            "ban_formulaic_lists": True,
            "require_narrative_prose": True,
            "max_buzzword_density": 0.015,
        }
    )
    coherence: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "enforce_glossary": True,
            "check_cross_references": True,
            "validate_citation_anchors": True,
        }
    )
    style: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "enforce_cjk_latin_spacing": True,
            "enforce_booktabs_tables": True,
            "max_paragraph_words": 350,
            "min_paragraph_words": 50,
        }
    )
    citations: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "bib_file": "bibliography.bib",
            "require_verified_sources": True,
        }
    )


@dataclass
class GitOpsConfig:
    base_branch: str = "main"
    branch_prefix: str = "synapse/"
    enable_draft_prs: bool = True
    auto_assign_reviewers: bool = True
    required_agent_reviews: int = 2
    bot_identity: str = "synapseforge-swarm[bot]"
    bot_email: str = "synapseforge-swarm[bot]@users.noreply.github.com"


@dataclass
class TailscaleConfig:
    enabled: bool = True
    tailnet: str = "synapseforge.ts.net"
    mesh_port: int = 8765
    p2p_direct_udp: bool = True
    auto_discovery: bool = True
    nodes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RenderConfig:
    formats: List[str] = field(default_factory=lambda: ["html", "typst", "markdown"])
    output_dir: str = "dist"
    theme: str = "academic_clean"
    cjk_font: str = "KaiTi"
    latin_font: str = "Times New Roman"
    include_toc: bool = True
    numbered_headings: bool = True


@dataclass
class SectionSpec:
    id: str
    title: str
    file: str
    assigned_role: str
    assigned_human: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    word_count_target: int = 1000
    description: str = ""


@dataclass
class ProjectConfig:
    name: str = "Unnamed Project"
    version: str = "0.1.0"
    document_title: str = "Collaborative Document"
    document_type: str = "whitepaper"  # whitepaper | research_paper | technical_spec | book
    language: str = "zh-CN"
    authors: List[str] = field(default_factory=lambda: ["SynapseForge Swarm"])
    glossary: Dict[str, str] = field(default_factory=dict)
    sections: List[SectionSpec] = field(default_factory=list)
    swarm: List[SwarmAgentConfig] = field(default_factory=list)
    quality_gates: QualityGateConfig = field(default_factory=QualityGateConfig)
    gitops: GitOpsConfig = field(default_factory=GitOpsConfig)
    tailscale: TailscaleConfig = field(default_factory=TailscaleConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    root_dir: Path = field(default_factory=Path.cwd)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], root_dir: Optional[Path] = None) -> ProjectConfig:
        root = root_dir or Path.cwd()
        
        # Parse sections
        raw_sections = data.get("sections", [])
        sections = [
            SectionSpec(
                id=s.get("id", f"sec_{idx}"),
                title=s.get("title", ""),
                file=s.get("file", ""),
                assigned_role=s.get("assigned_role", "drafter"),
                assigned_human=s.get("assigned_human"),
                dependencies=s.get("dependencies", []),
                word_count_target=s.get("word_count_target", 1000),
                description=s.get("description", ""),
            )
            for idx, s in enumerate(raw_sections)
        ]

        # Parse swarm agents
        raw_swarm = data.get("swarm", [])
        swarm = [
            SwarmAgentConfig(
                role=a.get("role", "general"),
                name=a.get("name", "Agent"),
                model=a.get("model", "inherit"),
                responsibilities=a.get("responsibilities", []),
                system_prompt_override=a.get("system_prompt_override"),
            )
            for a in raw_swarm
        ]

        # Parse quality gates
        raw_qg = data.get("quality_gates", {})
        quality_gates = QualityGateConfig(
            anti_ai=raw_qg.get("anti_ai", QualityGateConfig().anti_ai),
            coherence=raw_qg.get("coherence", QualityGateConfig().coherence),
            style=raw_qg.get("style", QualityGateConfig().style),
            citations=raw_qg.get("citations", QualityGateConfig().citations),
        )

        # Parse GitOps
        raw_gitops = data.get("gitops", {})
        gitops = GitOpsConfig(
            base_branch=raw_gitops.get("base_branch", "main"),
            branch_prefix=raw_gitops.get("branch_prefix", "synapse/"),
            enable_draft_prs=raw_gitops.get("enable_draft_prs", True),
            auto_assign_reviewers=raw_gitops.get("auto_assign_reviewers", True),
            required_agent_reviews=raw_gitops.get("required_agent_reviews", 2),
            bot_identity=raw_gitops.get("bot_identity", "synapseforge-swarm[bot]"),
            bot_email=raw_gitops.get("bot_email", "synapseforge-swarm[bot]@users.noreply.github.com"),
        )

        # Parse Tailscale
        raw_ts = data.get("tailscale", {})
        tailscale = TailscaleConfig(
            enabled=raw_ts.get("enabled", True),
            tailnet=raw_ts.get("tailnet", "synapseforge.ts.net"),
            mesh_port=raw_ts.get("mesh_port", 8765),
            p2p_direct_udp=raw_ts.get("p2p_direct_udp", True),
            auto_discovery=raw_ts.get("auto_discovery", True),
            nodes=raw_ts.get("nodes", []),
        )

        # Parse Render
        raw_render = data.get("render", {})
        render = RenderConfig(
            formats=raw_render.get("formats", ["html", "typst", "markdown"]),
            output_dir=raw_render.get("output_dir", "dist"),
            theme=raw_render.get("theme", "academic_clean"),
            cjk_font=raw_render.get("cjk_font", "KaiTi"),
            latin_font=raw_render.get("latin_font", "Times New Roman"),
            include_toc=raw_render.get("include_toc", True),
            numbered_headings=raw_render.get("numbered_headings", True),
        )

        return cls(
            name=data.get("name", "Unnamed Project"),
            version=data.get("version", "0.1.0"),
            document_title=data.get("document_title", "Collaborative Document"),
            document_type=data.get("document_type", "whitepaper"),
            language=data.get("language", "zh-CN"),
            authors=data.get("authors", ["SynapseForge Swarm"]),
            glossary=data.get("glossary", {}),
            sections=sections,
            swarm=swarm,
            quality_gates=quality_gates,
            gitops=gitops,
            tailscale=tailscale,
            render=render,
            root_dir=root,
        )


def load_config(config_path: Optional[Path | str] = None) -> ProjectConfig:
    if config_path:
        p = Path(config_path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found at: {p}")
    else:
        curr = Path.cwd()
        p = curr / "synapseforge.yaml"
        if not p.exists():
            p = curr / "synapseforge.yml"
        if not p.exists():
            return ProjectConfig()

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    return ProjectConfig.from_dict(data, root_dir=p.parent)
