import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from epc.api import (
    attach_ue,
    add_bearer,
    delete_bearer,
    start_traffic,
    stop_traffic,
    get_traffic_stats,
    get_ues_stats,
    reset_all,
)
from epc.models import (
    AddBearerRequest,
    AttachUERequest,
    BearerConfig,
    StartTrafficRequest,
    ThroughputStats,
    UEState,
)


# Helpers

def _ue(ue_id: int = 1, bearer_ids: list[int] | None = None) -> UEState:
    state = UEState(ue_id=ue_id)
    for bid in (bearer_ids or [9]):
        state.bearers[bid] = BearerConfig(bearer_id=bid)
    return state


def _ue_with_stats(ue_id: int = 1, bytes_tx: int = 800, bytes_rx: int = 800,
                   start_ts: float = 1.0, last_update_ts: float = 9.0) -> UEState:
    state = _ue(ue_id=ue_id)
    state.stats[9] = ThroughputStats(
        bearer_id=9, ue_id=ue_id,
        bytes_tx=bytes_tx, bytes_rx=bytes_rx,
        start_ts=start_ts, last_update_ts=last_update_ts,
        protocol="tcp", target_bps=1000,
    )
    return state


# attach_ue — verifies ue_id from body is forwarded to repo correctly

def test_attach_ue_forwards_ue_id_to_repo():
    repo = MagicMock()
    attach_ue(body=AttachUERequest(ue_id=7), repo=repo)
    repo.attach_ue.assert_called_once_with(7)


# add_bearer — verifies both ue_id and bearer_id are forwarded

def test_add_bearer_forwards_both_ids_to_repo():
    repo = MagicMock()
    add_bearer(ue_id=1, body=AddBearerRequest(bearer_id=3), repo=repo)
    repo.add_bearer.assert_called_once_with(1, 3)


# delete_bearer — must stop running traffic before deleting

def test_delete_bearer_stops_running_traffic_before_deleting():
    state = _ue(ue_id=1, bearer_ids=[9, 3])
    repo = MagicMock()
    repo.get_ue.return_value = state
    mock_tm = MagicMock()
    mock_tm.is_running.return_value = True
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        delete_bearer(ue_id=1, bearer_id=3, repo=repo)
    mock_tm.stop.assert_called_once_with(1, 3)
    repo.delete_bearer.assert_called_once_with(1, 3)


# start_traffic — target_bps from body must reach the response

def test_start_traffic_propagates_mbps_conversion_to_response():
    state = _ue(ue_id=1, bearer_ids=[9])
    repo = MagicMock()
    repo.get_ue.return_value = state
    mock_tm = MagicMock()
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        result = start_traffic(
            ue_id=1, bearer_id=9,
            body=StartTrafficRequest(protocol="tcp", Mbps=1.0),
            repo=repo,
        )
    assert result.target_bps == 1_000_000


def test_start_traffic_already_running_raises_400():
    state = _ue(ue_id=1, bearer_ids=[9])
    repo = MagicMock()
    repo.get_ue.return_value = state
    mock_tm = MagicMock()
    mock_tm.start.side_effect = ValueError("Traffic already running")
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        with pytest.raises(HTTPException) as exc:
            start_traffic(
                ue_id=1, bearer_id=9,
                body=StartTrafficRequest(protocol="tcp", Mbps=2.0),
                repo=repo,
            )
    assert exc.value.status_code == 400
    assert "already running" in exc.value.detail


# stop_traffic — tm.stop must be called with correct (ue_id, bearer_id)

def test_stop_traffic_calls_tm_stop_with_correct_ids():
    state = _ue(ue_id=1, bearer_ids=[9])
    state.bearers[9].active = True
    repo = MagicMock()
    repo.get_ue.return_value = state
    mock_tm = MagicMock()
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        stop_traffic(ue_id=1, bearer_id=9, repo=repo)
    mock_tm.stop.assert_called_once_with(1, 9)


# get_traffic_stats — bps calculation and no-stats edge case

def test_get_traffic_stats_returns_zeros_when_no_stats_recorded():
    repo = MagicMock()
    repo.get_ue.return_value = _ue(ue_id=1)  # state.stats is empty
    mock_tm = MagicMock()
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        result = get_traffic_stats(ue_id=1, bearer_id=9, repo=repo)
    assert result.tx_bps == 0
    assert result.rx_bps == 0
    assert result.duration == 0


def test_get_traffic_stats_computes_bps_from_byte_counts():
    # 800 bytes in 8 s -> tx_bps = 800 * 8 / 8 = 800
    repo = MagicMock()
    repo.get_ue.return_value = _ue_with_stats(bytes_tx=800, bytes_rx=800,
                                               start_ts=1.0, last_update_ts=9.0)
    mock_tm = MagicMock()
    mock_tm.is_running.return_value = False  # use last_update_ts as end_ts
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        result = get_traffic_stats(ue_id=1, bearer_id=9, repo=repo)
    assert result.tx_bps == 800
    assert result.rx_bps == 800
    assert result.duration == pytest.approx(8.0)


# get_ues_stats — aggregation logic and details dict structure

def test_get_ues_stats_aggregates_bps_across_all_ues():
    repo = MagicMock()
    repo.list_ues.return_value = [1]
    repo.get_ue.return_value = _ue_with_stats(bytes_tx=800, bytes_rx=800,
                                               start_ts=1.0, last_update_ts=9.0)
    mock_tm = MagicMock()
    mock_tm.is_running.return_value = False
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        result = get_ues_stats(repo=repo, ue_id=None, include_details=False)
    assert result.total_tx_bps == 800
    assert result.total_rx_bps == 800
    assert result.bearer_count == 1


def test_get_ues_stats_details_uses_string_keys():
    # Keys are str(ue_id) and str(bearer_id) — not ints
    repo = MagicMock()
    repo.list_ues.return_value = [1]
    repo.get_ue.return_value = _ue_with_stats(ue_id=1, bytes_tx=800,
                                               start_ts=1.0, last_update_ts=9.0)
    mock_tm = MagicMock()
    mock_tm.is_running.return_value = False
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        result = get_ues_stats(repo=repo, ue_id=None, include_details=True)
    assert result.details is not None
    assert "1" in result.details
    assert "9" in result.details["1"]
    assert result.details["1"]["9"] == 800


# reset_all — must call stop_all AND repo.reset_all (both steps required)

def test_reset_all_stops_all_traffic_and_clears_repo():
    repo = MagicMock()
    mock_tm = MagicMock()
    with patch("epc.api.get_traffic_manager", return_value=mock_tm):
        reset_all(repo=repo)
    mock_tm.stop_all.assert_called_once()
    repo.reset_all.assert_called_once()
