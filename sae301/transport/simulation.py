"""UDP transport carrying packetized complex64 baseband samples."""

from __future__ import annotations

import itertools
import math
import secrets
import socket
import struct
import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..config import SimulationConfig
from .base import IQTransport, TransportError, TransportTimeout

_MAGIC = b"S301"
_HEADER = struct.Struct("!4sIHHI")
_MAX_DATAGRAM = 60_000
_SAMPLE_BYTES = np.dtype("<c8").itemsize
_SAMPLES_PER_PACKET = (_MAX_DATAGRAM - _HEADER.size) // _SAMPLE_BYTES
_MAX_BURST_SAMPLES = 4_000_000


@dataclass(slots=True)
class _Assembly:
    packet_count: int
    sample_count: int
    created: float
    parts: dict[int, bytes] = field(default_factory=dict)


def apply_impairments(
    samples: ArrayLike, config: SimulationConfig, rng: np.random.Generator
) -> NDArray[np.complex64]:
    """Apply deterministic constant phase, timing delay, and complex AWGN."""

    output = np.asarray(samples, dtype=np.complex128).reshape(-1).copy()
    output *= np.exp(1j * np.deg2rad(config.phase_offset_deg))
    if config.noise_snr_db is not None:
        active = np.abs(output) > 1e-8
        signal_power = float(np.mean(np.abs(output[active]) ** 2)) if np.any(active) else 0.0
        if signal_power:
            noise_power = signal_power / (10 ** (config.noise_snr_db / 10))
            noise = np.sqrt(noise_power / 2) * (
                rng.standard_normal(output.size) + 1j * rng.standard_normal(output.size)
            )
            output += noise
    delayed = (
        np.pad(output, (config.timing_offset_samples, 0))
        if config.timing_offset_samples
        else output
    )
    return delayed.astype(np.complex64)


class SimulationTransport(IQTransport):
    """Exchange actual baseband samples over UDP, with burst fragmentation."""

    def __init__(self, config: SimulationConfig) -> None:
        config.validate()
        self._config = config
        self._rng = np.random.default_rng(config.random_seed)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((config.bind_host, config.bind_port))
        self._peer = (socket.gethostbyname(config.peer_host), config.peer_port)
        self._assemblies: dict[int, _Assembly] = {}
        start = secrets.randbits(32)
        self._burst_ids = itertools.count(start)
        self._closed = False

    @property
    def local_address(self) -> tuple[str, int]:
        host, port = self._socket.getsockname()
        return str(host), int(port)

    def send_samples(self, samples: NDArray[np.complexfloating]) -> None:
        self._ensure_open()
        impaired = apply_impairments(samples, self._config, self._rng)
        if impaired.size == 0:
            raise TransportError("cannot send an empty I/Q burst")
        if impaired.size > _MAX_BURST_SAMPLES:
            raise TransportError(f"I/Q burst exceeds {_MAX_BURST_SAMPLES} samples")
        little_endian = np.ascontiguousarray(impaired.astype("<c8", copy=False))
        raw = little_endian.tobytes()
        packet_count = math.ceil(impaired.size / _SAMPLES_PER_PACKET)
        if packet_count > 0xFFFF:
            raise TransportError("I/Q burst needs too many UDP fragments")
        burst_id = next(self._burst_ids) & 0xFFFFFFFF
        for index in range(packet_count):
            start = index * _SAMPLES_PER_PACKET * _SAMPLE_BYTES
            end = min(len(raw), (index + 1) * _SAMPLES_PER_PACKET * _SAMPLE_BYTES)
            header = _HEADER.pack(_MAGIC, burst_id, index, packet_count, impaired.size)
            self._socket.sendto(header + raw[start:end], self._peer)

    def receive_samples(self, timeout: float | None = None) -> NDArray[np.complex64]:
        self._ensure_open()
        deadline = None if timeout is None else time.monotonic() + max(timeout, 0.0)
        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise TransportTimeout("timed out waiting for an I/Q burst")
            self._socket.settimeout(remaining)
            try:
                datagram, address = self._socket.recvfrom(65_535)
            except TimeoutError as exc:
                raise TransportTimeout("timed out waiting for an I/Q burst") from exc
            if address[0] != self._peer[0] or address[1] != self._peer[1]:
                continue
            decoded = self._accept_datagram(datagram)
            if decoded is not None:
                return decoded

    def _accept_datagram(self, datagram: bytes) -> NDArray[np.complex64] | None:
        if len(datagram) < _HEADER.size:
            return None
        magic, burst_id, index, packet_count, sample_count = _HEADER.unpack(
            datagram[: _HEADER.size]
        )
        payload = datagram[_HEADER.size :]
        if (
            magic != _MAGIC
            or packet_count == 0
            or index >= packet_count
            or sample_count == 0
            or sample_count > _MAX_BURST_SAMPLES
            or len(payload) % _SAMPLE_BYTES
        ):
            return None
        now = time.monotonic()
        self._assemblies = {
            key: value for key, value in self._assemblies.items() if now - value.created < 10.0
        }
        assembly = self._assemblies.get(burst_id)
        if assembly is None:
            assembly = _Assembly(packet_count, sample_count, now)
            self._assemblies[burst_id] = assembly
        if assembly.packet_count != packet_count or assembly.sample_count != sample_count:
            del self._assemblies[burst_id]
            return None
        assembly.parts.setdefault(index, payload)
        if len(assembly.parts) != packet_count:
            return None
        raw = b"".join(assembly.parts[i] for i in range(packet_count))
        del self._assemblies[burst_id]
        if len(raw) != sample_count * _SAMPLE_BYTES:
            return None
        return np.frombuffer(raw, dtype="<c8").astype(np.complex64, copy=True)

    def flush_input(self) -> None:
        self._ensure_open()
        self._assemblies.clear()
        self._socket.setblocking(False)
        try:
            while True:
                self._socket.recvfrom(65_535)
        except BlockingIOError:
            pass
        finally:
            self._socket.setblocking(True)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._socket.close()
            self._assemblies.clear()

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransportError("simulation transport is closed")
