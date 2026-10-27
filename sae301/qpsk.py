"""Gray-coded QPSK mapping and root-raised-cosine pulse shaping."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .framing import bytes_to_bits

ComplexArray = NDArray[np.complex128]
FloatArray = NDArray[np.float64]

_NORMALIZATION = math.sqrt(2.0)
# Bit pairs 00, 01, 10, 11. Adjacent quadrants differ by one bit.
_CONSTELLATION = np.asarray(
    [1 + 1j, -1 + 1j, 1 - 1j, -1 - 1j], dtype=np.complex128
) / _NORMALIZATION


def bits_to_symbols(bits: ArrayLike) -> ComplexArray:
    array = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if array.size % 2:
        raise ValueError("QPSK requires an even number of bits")
    if np.any(array > 1):
        raise ValueError("bits must contain only 0 and 1")
    indexes = (array[0::2] << 1) | array[1::2]
    # Convert binary indexes 00/01/10/11 to our explicit Gray quadrant table.
    lookup = np.asarray([0, 1, 2, 3], dtype=np.uint8)
    return _CONSTELLATION[lookup[indexes]]


def symbols_to_bits(symbols: ArrayLike) -> NDArray[np.uint8]:
    array = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    bits = np.empty(array.size * 2, dtype=np.uint8)
    bits[0::2] = np.imag(array) < 0
    bits[1::2] = np.real(array) < 0
    return bits


def rrc_taps(
    samples_per_symbol: int = 8, rolloff: float = 0.35, span_symbols: int = 8
) -> FloatArray:
    """Return an odd-length, unit-energy root-raised-cosine FIR."""

    if samples_per_symbol < 2:
        raise ValueError("samples_per_symbol must be at least 2")
    if not 0 < rolloff <= 1:
        raise ValueError("rolloff must be in (0, 1]")
    if span_symbols < 4 or span_symbols % 2:
        raise ValueError("span_symbols must be even and at least 4")

    count = span_symbols * samples_per_symbol + 1
    times = (np.arange(count, dtype=np.float64) - (count - 1) / 2) / samples_per_symbol
    taps = np.empty(count, dtype=np.float64)
    beta = rolloff
    singular = 1 / (4 * beta)
    for index, time in enumerate(times):
        if abs(time) < 1e-12:
            taps[index] = 1 + beta * (4 / math.pi - 1)
        elif abs(abs(time) - singular) < 1e-12:
            taps[index] = (beta / math.sqrt(2)) * (
                (1 + 2 / math.pi) * math.sin(math.pi / (4 * beta))
                + (1 - 2 / math.pi) * math.cos(math.pi / (4 * beta))
            )
        else:
            numerator = math.sin(math.pi * time * (1 - beta)) + 4 * beta * time * math.cos(
                math.pi * time * (1 + beta)
            )
            denominator = math.pi * time * (1 - (4 * beta * time) ** 2)
            taps[index] = numerator / denominator
    taps /= np.sqrt(np.sum(taps**2))
    return taps


def pulse_shape(symbols: ArrayLike, taps: ArrayLike, samples_per_symbol: int) -> ComplexArray:
    array = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    impulse_train = np.zeros(array.size * samples_per_symbol, dtype=np.complex128)
    impulse_train[::samples_per_symbol] = array
    shaped = np.convolve(impulse_train, np.asarray(taps, dtype=np.float64), mode="full")
    return np.asarray(shaped, dtype=np.complex128)


def modulate_bytes(
    data: bytes,
    *,
    samples_per_symbol: int = 8,
    rolloff: float = 0.35,
    span_symbols: int = 8,
    guard_symbols: int = 8,
) -> NDArray[np.complex64]:
    """Convert serialized frame bytes into a guarded QPSK baseband burst."""

    symbols = bits_to_symbols(bytes_to_bits(data))
    taps = rrc_taps(samples_per_symbol, rolloff, span_symbols)
    waveform = pulse_shape(symbols, taps, samples_per_symbol)
    guarded = np.pad(waveform, (guard_symbols * samples_per_symbol,) * 2)
    return guarded.astype(np.complex64)
