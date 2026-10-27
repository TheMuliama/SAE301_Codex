"""Byte/bit and UTF-8 conversion helpers shared by the protocol and DSP."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def encode_text(text: str, maximum_bytes: int = 1024) -> bytes:
    """Encode text as strict UTF-8 while enforcing the on-air payload limit."""

    payload = text.encode("utf-8", errors="strict")
    if len(payload) > maximum_bytes:
        raise ValueError(f"UTF-8 payload is {len(payload)} bytes; maximum is {maximum_bytes}")
    return payload


def decode_text(payload: bytes) -> str:
    """Decode a protocol payload as strict UTF-8."""

    return payload.decode("utf-8", errors="strict")


def bytes_to_bits(data: bytes) -> NDArray[np.uint8]:
    """Return bits in network order (most-significant bit first)."""

    if not data:
        return np.empty(0, dtype=np.uint8)
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="big")


def bits_to_bytes(bits: NDArray[np.integer] | list[int], *, strict: bool = True) -> bytes:
    """Pack MSB-first bits; optionally discard an incomplete final byte."""

    array = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if np.any(array > 1):
        raise ValueError("bits must contain only 0 and 1")
    remainder = array.size % 8
    if remainder and strict:
        raise ValueError("bit count must be a multiple of 8")
    usable = array[: array.size - remainder] if remainder else array
    return np.packbits(usable, bitorder="big").tobytes()
