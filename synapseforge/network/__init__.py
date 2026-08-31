"""
SynapseForge Network Layer:
- TailscaleMeshManager: WireGuard P2P encrypted mesh telemetry & discovery
- DistributedRoomManager: Multi-node collaborative room sync
- OutboxQueue, ResilientTransportManager: Network jitter tolerance, local outbox buffer & auto-reconnect
"""

from synapseforge.network.resilient_transport import OutboxQueue, ResilientTransportManager, SyncEvent
from synapseforge.network.room_sync import DistributedRoomManager
from synapseforge.network.tailscale_mesh import TailscaleMeshManager

__all__ = [
    "TailscaleMeshManager",
    "DistributedRoomManager",
    "OutboxQueue",
    "ResilientTransportManager",
    "SyncEvent",
]
