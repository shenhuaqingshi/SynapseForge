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


def test_outbox_load_events_backs_up_corrupt_file(tmp_path):
    """A corrupted queue file must be preserved as .corrupt backup, not dropped."""
    outbox = OutboxQueue(workspace_root=tmp_path)
    outbox.queue_file.write_text("{corrupted json!!", encoding="utf-8")

    assert outbox._load_events() == []

    corrupt_backup = outbox.outbox_dir / "pending_events.json.corrupt"
    assert corrupt_backup.exists()
    assert corrupt_backup.read_text(encoding="utf-8") == "{corrupted json!!"
    assert not outbox.queue_file.exists()

    # Queue is usable again after the backup
    outbox.enqueue("doc_patch", {"section": "sec_01"})
    assert len(outbox.list_pending()) == 1


def test_outbox_save_events_is_atomic_no_tmp_leftover(tmp_path):
    """_save_events must write via tmp + os.replace and leave no temp file behind."""
    outbox = OutboxQueue(workspace_root=tmp_path)
    outbox.enqueue("doc_patch", {"section": "sec_01"})
    outbox.enqueue("lease_renew", {"section": "sec_02"})

    assert not (outbox.outbox_dir / "pending_events.json.tmp").exists()
    assert outbox.queue_file.exists()
    assert len(outbox.list_pending()) == 2
