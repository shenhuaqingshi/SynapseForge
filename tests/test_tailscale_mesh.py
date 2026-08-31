import pytest
from synapseforge.network.tailscale_mesh import TailscaleMeshManager, MeshNode, MeshTopology


def test_tailscale_mesh_manager_fallback():
    mgr = TailscaleMeshManager(tailnet_name="synapseforge.ts.net")
    topo = mgr.get_mesh_status()
    assert topo.tailnet_name == "synapseforge.ts.net"
    assert len(topo.connected_nodes) >= 4
    assert topo.direct_p2p_ratio == 1.0
    
    ips = [n.tailscale_ip for n in topo.connected_nodes]
    assert "100.64.0.1" in ips
    assert "100.64.0.2" in ips


def test_tailscale_mesh_ping():
    mgr = TailscaleMeshManager(tailnet_name="synapseforge.ts.net")
    pings = mgr.ping_mesh()
    assert "node-beijing" in pings
    assert pings["node-beijing"] < 10.0
