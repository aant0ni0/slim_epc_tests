import pytest
from pydantic import ValidationError

from epc.models import StartTrafficRequest, UEState, BearerConfig, AddBearerRequest, AttachUERequest, ThroughputStats

@pytest.mark.parametrize(
    "invalid_bearer_id",
    [0, 10]
)
def test_bearer_config_validates_bearer_id_boundaries(invalid_bearer_id):
    with pytest.raises(ValidationError):
        BearerConfig(bearer_id=invalid_bearer_id)


def test_bearer_config_validates_protocol_pattern_incorrect():
    with pytest.raises(ValidationError):
        BearerConfig(bearer_id=1, protocol="icmp")


def test_bearer_config_validates_protocol_pattern_correctly():
    bearer = BearerConfig(bearer_id=1, protocol="tcp")
    assert bearer.protocol == "tcp"


def test_bearer_config_initializes_with_defaults():
    bearer = BearerConfig(bearer_id=1)

    assert bearer.bearer_id == 1
    assert bearer.protocol is None
    assert bearer.target_bps is None
    assert bearer.active is False


def test_throughput_stats_initializes_with_defaults():
    stats = ThroughputStats(bearer_id=1, ue_id=10)

    assert stats.bytes_tx == 0
    assert stats.bytes_rx == 0
    assert stats.start_ts is None
    assert stats.last_update_ts is None
    assert stats.protocol is None
    assert stats.target_bps is None


@pytest.mark.parametrize(
    "invalid_ue_id",
    [0, 101]
)
def test_ue_state_validates_ue_id_boundaries(invalid_ue_id):
    with pytest.raises(ValidationError):
        UEState(ue_id=invalid_ue_id)


def test_ue_state_handles_none_bearers():
    state = UEState(ue_id=1, bearers=None)
    assert state.bearers == {}


def test_ue_state_handles_none_stats():
    state = UEState(ue_id=1, stats=None)
    assert state.stats == {}


def test_ue_state_handles_none_for_both_optional_fields():
    state = UEState(ue_id=1, stats=None, bearers=None)
    assert state.bearers == {}
    assert state.stats == {}


def test_ue_state_initializes_with_nested_objects():
    bearer = BearerConfig(bearer_id=1, protocol="tcp", active=True)
    stats = ThroughputStats(bearer_id=1, ue_id=10, bytes_tx=100)

    state = UEState(
        ue_id=10,
        bearers={1: bearer},
        stats={1: stats}
    )

    assert 1 in state.bearers
    assert state.bearers[1].active is True
    assert 1 in state.stats
    assert state.stats[1].bytes_tx == 100


def test_start_traffic_request_validates_one_throughput():
    with pytest.raises(ValidationError):
        StartTrafficRequest(protocol="tcp", Mbps=1.0, kbps=1.0)


def test_start_traffic_request_raises_error_when_no_throughput_provided():
    with pytest.raises(ValidationError, match="Provide exactly one throughput value"):
        StartTrafficRequest(protocol="tcp")


def test_target_bps_converts_mbps_correctly():
    req = StartTrafficRequest(protocol="tcp", Mbps=2.0)
    assert req.target_bps() == 2_000_000


def test_target_bps_converts_kbps_correctly():
    req = StartTrafficRequest(protocol="tcp", kbps=2.0)
    assert req.target_bps() == 2_000


def test_target_bps_returns_bps_correctly():
    req = StartTrafficRequest(protocol="tcp", bps=150.5)
    # Rzutowanie int() ucina część ułamkową
    assert req.target_bps() == 150


@pytest.mark.parametrize(
    "invalid_protocol",
    ["icmp", "TCP", "Udp", " tcp", "tcp ", ""]
)
def test_start_traffic_request_rejects_invalid_protocols(invalid_protocol):
    with pytest.raises(ValidationError):
        StartTrafficRequest(protocol=invalid_protocol, Mbps=1.0)


def test_start_traffic_request_accepts_integers_as_floats():
    req = StartTrafficRequest(protocol="udp", Mbps=10)
    assert req.Mbps == 10.0
    assert isinstance(req.Mbps, float)


def test_start_traffic_request_rejects_invalid_types():
    with pytest.raises(ValidationError):
        StartTrafficRequest(protocol="udp", Mbps="nie_liczba")


@pytest.mark.parametrize(
    "invalid_ue_id",
    [0, 101]
)
def test_attach_ue_request_validates_boundaries(invalid_ue_id):
    with pytest.raises(ValidationError):
        AttachUERequest(ue_id=invalid_ue_id)


@pytest.mark.parametrize(
    "invalid_bearer_id",
    [0, 10]
)
def test_add_bearer_request_validates_boundaries(invalid_bearer_id):
    with pytest.raises(ValidationError):
        AddBearerRequest(bearer_id=invalid_bearer_id)