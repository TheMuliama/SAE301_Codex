from __future__ import annotations

import numpy as np
import pytest

from sae301.config import RadioConfig
from sae301.transport import pluto
from sae301.transport.base import TransportError, TransportTimeout


class FakeContext:
    def __init__(self) -> None:
        self.timeouts: list[int] = []

    def set_timeout(self, milliseconds: int) -> None:
        self.timeouts.append(milliseconds)


class FakePluto:
    def __init__(self) -> None:
        self.sample_rate = 800_000
        self.rx_lo = 100_000_000
        self.tx_lo = 100_000_000
        self.ctx = FakeContext()
        self.tx_calls: list[np.ndarray] = []
        self.tx_destroy_calls = 0
        self.rx_destroy_calls = 0
        self.closed = False
        self.fail_rx: Exception | None = None
        self._capture_index = 0

    def tx(self, samples) -> None:
        self.tx_calls.append(np.asarray(samples).copy())

    def rx(self):
        if self.fail_rx:
            raise self.fail_rx
        start = self._capture_index * 16
        self._capture_index += 1
        return np.arange(start, start + 16, dtype=np.float64) + 1j

    def tx_destroy_buffer(self) -> None:
        self.tx_destroy_calls += 1

    def rx_destroy_buffer(self) -> None:
        self.rx_destroy_calls += 1

    def close(self) -> None:
        self.closed = True


def test_connectivity_check_only_reads_and_closes(monkeypatch) -> None:
    fake = FakePluto()
    monkeypatch.setattr(pluto, "_pluto_device", lambda _uri: fake)
    pluto.check_pluto_connectivity(RadioConfig())
    assert not fake.tx_calls
    assert fake.closed


def test_pluto_configuration_receive_flush_and_close(monkeypatch) -> None:
    fake = FakePluto()
    monkeypatch.setattr(pluto, "_pluto_device", lambda _uri: fake)
    transport = pluto.PlutoTransport(RadioConfig(), allow_transmit=False)
    assert fake.sample_rate == 1_000_000
    assert fake.rx_lo == fake.tx_lo == 868_000_000
    assert fake.rx_rf_bandwidth == fake.tx_rf_bandwidth == 500_000
    assert fake.gain_control_mode_chan0 == "manual"
    assert fake.tx_cyclic_buffer is False

    capture = transport.receive_samples(timeout=0.75)
    assert capture.shape == (32,)
    assert np.mean(capture) == pytest.approx(0)
    assert len(fake.ctx.timeouts) == 2
    assert all(1 <= value <= 750 for value in fake.ctx.timeouts)
    transport.flush_input()
    assert fake.rx_destroy_calls == 1
    transport.close()
    assert fake.closed


def test_transmission_requires_explicit_authorization(monkeypatch) -> None:
    fake = FakePluto()
    monkeypatch.setattr(pluto, "_pluto_device", lambda _uri: fake)
    transport = pluto.PlutoTransport(RadioConfig(), allow_transmit=False)
    with pytest.raises(TransportError, match="disabled"):
        transport.send_samples(np.ones(16, dtype=np.complex64))
    assert not fake.tx_calls
    transport.close()


def test_authorized_transmission_is_scaled_finite_and_destroyed(monkeypatch) -> None:
    fake = FakePluto()
    monkeypatch.setattr(pluto, "_pluto_device", lambda _uri: fake)
    monkeypatch.setattr(pluto.time, "sleep", lambda _seconds: None)
    transport = pluto.PlutoTransport(RadioConfig(), allow_transmit=True)
    transport.send_samples(np.asarray([0, 2 + 2j, -2 - 2j], dtype=np.complex64))
    assert len(fake.tx_calls) == 1
    assert np.max(np.abs(fake.tx_calls[0])) == pytest.approx((2**14) * 0.70, rel=1e-6)
    assert fake.tx_destroy_calls == 2
    transport.close()


def test_receive_timeout_is_translated(monkeypatch) -> None:
    fake = FakePluto()
    fake.fail_rx = TimeoutError("backend timed out")
    monkeypatch.setattr(pluto, "_pluto_device", lambda _uri: fake)
    transport = pluto.PlutoTransport(RadioConfig())
    with pytest.raises(TransportTimeout):
        transport.receive_samples(0.1)
    transport.close()
