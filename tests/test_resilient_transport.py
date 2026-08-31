import pytest
from pathlib import Path
from synapseforge.network.resilient_transport import OutboxQueue, ResilientTransportManager, SyncEvent


def test_outbox_queue_buffering_and_delivery(tmp_path):
    outbox = OutboxQueue(workspace_root=tmp_path)
    
    # 1. Buffer event during network disconnection
    evt = outbox.enqueue(
        event_type="doc_patch",
        payload={"section": "sec_04", "content": "Proof of Theorem 2"},
    )
    assert evt.status == "pending"
    assert len(outbox.list_pending()) == 1

    # 2. Simulate failure attempt with exponential retry
    evt_failed = outbox.mark_failed_attempt(evt.event_id, "Connection timed out")
    assert evt_failed.retry_count == 1
    assert evt_failed.status == "pending"

    # 3. Simulate successful reconnection and delivery
    outbox.mark_delivered(evt.event_id)
    assert len(outbox.list_pending()) == 0


def test_resilient_transport_flush_and_backoff(tmp_path):
    mgr = ResilientTransportManager(workspace_root=tmp_path)
    
    # Check exponential backoff delay with jitter
    delay_0 = mgr.compute_backoff_delay(0)
    delay_3 = mgr.compute_backoff_delay(3)
    assert 1.0 <= delay_0 <= 2.5
    assert 8.0 <= delay_3 <= 10.0

    # Enqueue events
    mgr.outbox.enqueue("room_message", {"text": "Hello swarm"})
    mgr.outbox.enqueue("lease_renew", {"section": "sec_02"})
    assert len(mgr.outbox.list_pending()) == 2

    # Flush all events with successful network sender
    res = mgr.flush_outbox(network_sender=lambda e: True)
    assert res["ok"] is True
    assert res["flushed_count"] == 2
    assert res["remaining_count"] == 0


def test_lease_grace_period_during_jitter(tmp_path):
    mgr = ResilientTransportManager(workspace_root=tmp_path)
    now = 1000.0
    expires_at = 990.0  # Expired 10s ago according to hard deadline
    last_heartbeat = 950.0  # 50s ago (within 300s grace period)

    # In grace period -> Still valid to prevent lock stealing during WAN latency spikes!
    check = mgr.check_lease_validity_with_grace(expires_at=expires_at, last_heartbeat=now - 50.0, current_time=now)
    assert check["valid"] is True
    assert check["in_grace_period"] is True
    assert check["grace_remaining_seconds"] > 200
