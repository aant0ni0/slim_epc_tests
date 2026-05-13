import pytest
from pydantic import ValidationError

from epc.models import StartTrafficRequest


def test_target_bps_converts_mbps_correctly():
    req = StartTrafficRequest(protocol="tcp", Mbps=2.0)
    assert req.target_bps() == 2_000_000
