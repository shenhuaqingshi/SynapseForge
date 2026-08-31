import shutil
from pathlib import Path
import pytest
from synapseforge.network.room_sync import DistributedRoomManager, SharedRoom


@pytest.fixture
def temp_room_dir(tmp_path):
    storage = tmp_path / "rooms"
    storage.mkdir(parents=True, exist_ok=True)
    yield storage
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_create_and_list_shared_room(temp_room_dir):
    mgr = DistributedRoomManager(storage_dir=temp_room_dir)
    room = mgr.create_shared_room(
        name="Test Collaborative Room",
        document_title="A Test Document on CRDT",
        document_type="tech_spec",
        owner_name="xb",
    )
    assert room.slug == "test-collaborative-room"
    assert len(room.synced_nodes) >= 1
    assert len(room.members) >= 1

    rooms = mgr.list_rooms()
    assert len(rooms) == 1
    assert rooms[0].room_id == room.room_id


def test_join_shared_room(temp_room_dir):
    mgr = DistributedRoomManager(storage_dir=temp_room_dir)
    room = mgr.create_shared_room(name="Multi Node Room", document_title="Multi Node Title")
    
    updated_room = mgr.join_shared_room(room.slug, member_name="Dr_Chen", role="reviewer")
    assert updated_room is not None
    assert any(m.name == "Dr_Chen" for m in updated_room.members)
    assert updated_room.state_version >= 2
