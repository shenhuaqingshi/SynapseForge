"""
SynapseForge: GitOps Swarm Framework for Distributed Multi-Agent & Multi-Human Collaborative Writing
"""

__version__ = "0.1.0"
__author__ = "SynapseForge Contributors"
__license__ = "MIT"

from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.engine import SwarmEngine
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.core.conflict_resolver import SemanticConflictResolver
from synapseforge.core.team_bus import TeamBus
from synapseforge.core.workspace_paths import patch_team_bus

patch_team_bus(TeamBus)

__all__ = [
    "ProjectConfig",
    "load_config",
    "SwarmEngine",
    "MarkdownASTParser",
    "SemanticConflictResolver",
]
