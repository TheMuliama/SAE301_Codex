"""PyADI-IIO transport for a single ADALM-Pluto in half-duplex burst use."""

from __future__ import annotations

import time
from contextlib import suppress
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..config import RadioConfig
from .base import IQTransport, TransportError, TransportTimeout

_TX_DAC_SCALE = (2**14) * 0.70


def _pluto_device(uri: str) -> Any:
    try:
        import adi
    except Exception as exc:
        raise TransportError(
            "PyADI-IIO/libiio cannot be loaded; install a compatible libiio runtime "
            f"and requirements-pluto.txt ({exc})"
        ) from exc
    try:
        return adi.Pluto(uri=uri)
    except Exception as exc:
        raise TransportError(f"cannot connect to ADALM-Pluto at {uri}: {exc}") from exc


def check_pluto_connectivity(config: RadioConfig) -> None:
    """Open and identify the IIO context without configuring or transmitting."""

    device = _pluto_device(config.uri)
    try:
        # Property reads ensure the expected AD936x control interface is present.
        _ = (device.sample_rate, device.rx_lo, device.tx_lo)
    except Exception as exc:
        raise TransportError(f"ADALM-Pluto at {config.uri} lacks expected controls: {exc}") from exc
    finally:
        close = getattr(device, "close", None)
        if callable(close):
            close()


class PlutoTransport(IQTransport):
    """Finite-burst I/Q transport with explicit TX authorization."""

    def __init__(self, config: RadioConfig, *, allow_transmit: bool = False) -> None:
        # The caller validates the complete AppConfig; validate radio constraints
        # here as a defensive API boundary with the default waveform parameters.
        from ..config import DspConfig

        config.validate(DspConfig())
        self._config = config
        self._allow_transmit = allow_transmit
        self._device = _pluto_device(config.uri)
        self._closed = False
        try:
            self._configure()
        except Exception as exc:
            self.close()
            raise TransportError(f"cannot configure ADALM-Pluto at {config.uri}: {exc}") from exc

    def _configure(self) -> None:
        device = self._device
        device.sample_rate = int(self._config.sample_rate_hz)
        device.rx_lo = int(self._config.carrier_frequency_hz)
        device.tx_lo = int(self._config.carrier_frequency_hz)
        device.rx_rf_bandwidth = int(self._config.rf_bandwidth_hz)
        device.tx_rf_bandwidth = int(self._config.rf_bandwidth_hz)
        device.gain_control_mode_chan0 = "manual"
        device.rx_hardwaregain_chan0 = float(self._config.rx_gain_db)
        device.tx_hardwaregain_chan0 = float(self._config.tx_gain_db)
        device.rx_buffer_size = int(self._config.rx_buffer_size)
        device.rx_enabled_channels = [0]
        device.tx_enabled_channels = [0]
        device.tx_cyclic_buffer = False

    def send_samples(self, samples: NDArray[np.complexfloating]) -> None:
        self._ensure_open()
        if not self._allow_transmit:
            raise TransportError(
                "RF transmission is disabled; explicit attenuation, power, device, "
                "laboratory, and regulatory authorization is required"
            )
        waveform = np.asarray(samples, dtype=np.complex128).reshape(-1)
        if waveform.size == 0:
            raise TransportError("cannot transmit an empty I/Q burst")
        peak = float(np.max(np.abs(waveform)))
        normalized = waveform / max(1.0, peak)
        dac_samples = np.asarray(normalized * _TX_DAC_SCALE, dtype=np.complex64)
        try:
            self._device.tx_destroy_buffer()
            self._device.tx(dac_samples)
            # A non-cyclic push returns after queuing. Keep the host-side buffer
            # alive for at least the on-air duration before releasing it.
            time.sleep(waveform.size / self._config.sample_rate_hz + 0.010)
        except Exception as exc:
            raise TransportError(f"ADALM-Pluto TX failed: {exc}") from exc
        finally:
            with suppress(Exception):
                self._device.tx_destroy_buffer()

    def receive_samples(self, timeout: float | None = None) -> NDArray[np.complex64]:
        self._ensure_open()
        context = getattr(self._device, "ctx", None)
        deadline = None if timeout is None else time.monotonic() + timeout
        captures: list[NDArray[np.complex128]] = []
        try:
            # Two adjacent buffers guarantee that a <= one-buffer burst wholly
            # appears in a returned window even when it crosses a buffer edge.
            for _ in range(2):
                if deadline is not None and context is not None and hasattr(context, "set_timeout"):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("capture deadline expired")
                    context.set_timeout(max(1, int(remaining * 1000)))
                raw = self._device.rx()
                if isinstance(raw, list):
                    raw = raw[0]
                captures.append(np.asarray(raw, dtype=np.complex128).reshape(-1))
        except Exception as exc:
            message = str(exc).lower()
            if isinstance(exc, TimeoutError) or "timed out" in message or "timeout" in message:
                raise TransportTimeout("timed out while capturing ADALM-Pluto samples") from exc
            raise TransportError(f"ADALM-Pluto RX failed: {exc}") from exc
        combined = np.concatenate(captures)
        if combined.size:
            combined -= np.mean(combined)  # Remove the usual zero-IF DC component.
        return combined.astype(np.complex64)

    def flush_input(self) -> None:
        self._ensure_open()
        try:
            self._device.rx_destroy_buffer()
        except Exception as exc:
            raise TransportError(f"cannot clear ADALM-Pluto RX buffer: {exc}") from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for method_name in ("tx_destroy_buffer", "rx_destroy_buffer"):
            method = getattr(self._device, method_name, None)
            if callable(method):
                with suppress(Exception):
                    method()
        close = getattr(self._device, "close", None)
        if callable(close):
            close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransportError("ADALM-Pluto transport is closed")
