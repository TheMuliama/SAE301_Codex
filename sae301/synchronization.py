"""Matched filtering, timing/preamble search, and constant-phase correction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .config import DspConfig
from .framing import bits_to_bytes, bytes_to_bits
from .protocol import PREAMBLE, Frame, ProtocolError, expected_frame_size, parse_frame
from .qpsk import bits_to_symbols, rrc_taps, symbols_to_bits


class SynchronizationError(ValueError):
    """Raised when no sufficiently strong preamble can be synchronized."""


@dataclass(frozen=True, slots=True)
class SynchronizationResult:
    symbols: NDArray[np.complex128]
    correlation: float
    sampling_phase: int
    symbol_index: int
    phase_offset_radians: float
    channel_gain: float


@dataclass(frozen=True, slots=True)
class DecodedBurst:
    frame: Frame
    synchronization: SynchronizationResult


def synchronize_symbols(
    samples: ArrayLike,
    known_preamble: ArrayLike,
    *,
    samples_per_symbol: int,
    matched_filter_taps: ArrayLike,
    threshold: float = 0.72,
) -> SynchronizationResult:
    """Find timing phase and preamble, then correct one constant complex gain."""

    received = np.asarray(samples, dtype=np.complex128).reshape(-1)
    preamble = np.asarray(known_preamble, dtype=np.complex128).reshape(-1)
    if received.size == 0 or preamble.size == 0:
        raise SynchronizationError("received samples and preamble must not be empty")
    matched = np.convolve(received, np.asarray(matched_filter_taps, dtype=np.float64), mode="full")
    preamble_energy = float(np.vdot(preamble, preamble).real)
    best: tuple[float, int, int, NDArray[np.complex128]] | None = None

    for phase in range(samples_per_symbol):
        candidate_symbols = np.asarray(
            matched[phase::samples_per_symbol], dtype=np.complex128
        )
        if candidate_symbols.size < preamble.size:
            continue
        numerator = np.abs(np.correlate(candidate_symbols, preamble, mode="valid"))
        window_energy = np.convolve(
            np.abs(candidate_symbols) ** 2, np.ones(preamble.size), mode="valid"
        )
        denominator = np.sqrt(np.maximum(window_energy * preamble_energy, 1e-24))
        correlations = numerator / denominator
        index = int(np.argmax(correlations))
        score = float(correlations[index])
        if best is None or score > best[0]:
            best = (score, phase, index, candidate_symbols)

    if best is None or best[0] < threshold:
        score = 0.0 if best is None else best[0]
        raise SynchronizationError(
            f"preamble correlation {score:.3f} is below threshold {threshold:.3f}"
        )
    score, phase, index, candidate_symbols = best
    observed = candidate_symbols[index : index + preamble.size]
    channel = np.vdot(preamble, observed) / preamble_energy
    if abs(channel) < 1e-12:
        raise SynchronizationError("estimated channel gain is zero")
    corrected = candidate_symbols[index:] / channel
    return SynchronizationResult(
        symbols=corrected,
        correlation=score,
        sampling_phase=phase,
        symbol_index=index,
        phase_offset_radians=float(np.angle(channel)),
        channel_gain=float(abs(channel)),
    )


def decode_burst(
    samples: ArrayLike, config: DspConfig, maximum_payload: int = 1024
) -> DecodedBurst:
    taps = rrc_taps(config.samples_per_symbol, config.rrc_rolloff, config.rrc_span_symbols)
    preamble_symbols = bits_to_symbols(bytes_to_bits(PREAMBLE))
    sync = synchronize_symbols(
        samples,
        preamble_symbols,
        samples_per_symbol=config.samples_per_symbol,
        matched_filter_taps=taps,
        threshold=config.sync_threshold,
    )
    raw = bits_to_bytes(symbols_to_bits(sync.symbols), strict=False)
    try:
        size = expected_frame_size(raw, maximum_payload)
    except ProtocolError:
        raise
    if len(raw) < size:
        raise ProtocolError(f"demodulated burst has {len(raw)} bytes; frame requires {size}")
    return DecodedBurst(parse_frame(raw[:size], maximum_payload), sync)
