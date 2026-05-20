import pytest
from epc.db import EPCRepository
from epc.models import BearerConfig, ThroughputStats

_repo = EPCRepository()

def test_list_all_ues():
    _repo.reset_all()
    _repo.attach_ue(1)
    _repo.attach_ue(3)
    _repo.attach_ue(2)

    ues = list(_repo.list_ues())
    assert len(ues) == 3
    assert ues == [1, 2, 3]

def test_list_ues_empty():
    _repo.reset_all()
    assert list(_repo.list_ues()) == []

def test_ue_exists_returns_false_when_missing():
    _repo.reset_all()
    assert _repo.ue_exists(1) is False

def test_ue_exists_returns_true_after_attach():
    _repo.reset_all()
    _repo.attach_ue(1)
    assert _repo.ue_exists(1) is True

def test_attach_ue_creates_default_bearer():
    _repo.reset_all()
    _repo.attach_ue(1)
    ue = _repo.get_ue(1)
    assert 9 in ue.bearers

def test_attach_ue_already_attached_raises():
    _repo.reset_all()
    _repo.attach_ue(1)
    with pytest.raises(ValueError, match="UE already attached"):
        _repo.attach_ue(1)

def test_detach_ue_removes_it():
    _repo.reset_all()
    _repo.attach_ue(1)
    _repo.detach_ue(1)
    assert _repo.ue_exists(1) is False

def test_detach_ue_not_found_raises():
    _repo.reset_all()
    with pytest.raises(ValueError, match="UE not found"):
        _repo.detach_ue(99)

def test_get_ue_returns_correct_ue():
    _repo.reset_all()
    _repo.attach_ue(1)
    ue = _repo.get_ue(1)
    assert ue.ue_id == 1

def test_get_ue_not_found_raises():
    _repo.reset_all()
    with pytest.raises(ValueError, match="UE not found"):
        _repo.get_ue(99)

def test_add_bearer_success():
    _repo.reset_all()
    _repo.attach_ue(1)
    _repo.add_bearer(1, bearer_id=5)
    ue = _repo.get_ue(1)
    assert 5 in ue.bearers

def test_add_bearer_duplicate_raises():
    _repo.reset_all()
    _repo.attach_ue(1)
    _repo.add_bearer(1, bearer_id=5)
    with pytest.raises(ValueError, match="Bearer already exists"):
        _repo.add_bearer(1, bearer_id=5)

def test_cannot_delete_default_bearer():
    _repo.reset_all()
    _repo.attach_ue(1)
    with pytest.raises(ValueError, match="Cannot remove default bearer"):
        _repo.delete_bearer(1, 9)

def test_cannot_delete_nonexistent_bearer():
    _repo.reset_all()
    _repo.attach_ue(1)
    with pytest.raises(ValueError, match="Bearer not found"):
        _repo.delete_bearer(1, 99)

def test_delete_bearer_success():
    _repo.reset_all()
    _repo.attach_ue(1)
    _repo.add_bearer(1, bearer_id=5)
    _repo.delete_bearer(1, 5)
    ue = _repo.get_ue(1)
    assert 5 not in ue.bearers

def test_update_bearer_persists_changes():
    _repo.reset_all()
    _repo.attach_ue(1)
    bearer = BearerConfig(bearer_id=9, target_bps=1000, protocol="tcp")
    _repo.update_bearer(1, bearer)
    ue = _repo.get_ue(1)
    assert ue.bearers[9].target_bps == 1000
    assert ue.bearers[9].protocol == "tcp"

def test_update_stats_persists():
    _repo.reset_all()
    _repo.attach_ue(1)
    stats = ThroughputStats(bearer_id=9, ue_id=1, bytes_tx=500, bytes_rx=300)
    _repo.update_stats(1, stats)
    ue = _repo.get_ue(1)
    assert ue.stats[9].bytes_tx == 500
    assert ue.stats[9].bytes_rx == 300

def test_reset_all_removes_all_ues():
    _repo.reset_all()
    _repo.attach_ue(1)
    _repo.attach_ue(2)
    _repo.reset_all()
    assert list(_repo.list_ues()) == []