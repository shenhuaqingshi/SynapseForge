"""
Tailscale Mesh Networking & Multi-Node Shared Room Sync Layer for SynapseForge.
"""

from synapseforge.network.room_sync import DistributedRoomManager, RoomMember, SharedRoom
from synapseforge.network.tailscale_mesh import MeshNode, MeshTopology, TailscaleMeshManager

__all__ = [
    "MeshNode",
    "MeshTopology",
    "TailscaleMeshManager",
    "DistributedRoomManager",
    "SharedRoom",
    "RoomMember",
]
