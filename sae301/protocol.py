"""Binary DATA/ACK protocol, identifiers, and CRC validation."""

from __future__ import annotations

import secrets
import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum

PREAMBLE = bytes.fromhex("f35ac7196d84b2e1")
PROTOCOL_VERSION = 1
DEFAULT_MAXIMUM_PAYLOAD = 1024
_HEADER = struct.Struct("!BBIH")
_CRC = struct.Struct("!I")
MINIMUM_FRAME_BYTES = len(PREAMBLE) + _HEADER.size + _CRC.size


class ProtocolError(ValueError):
    """Raised for a malformed or unsupported on-air frame."""


class CrcMismatch(ProtocolError):
    """Raised when the received CRC-32 does not match the frame contents."""


class FrameType(IntEnum):
    DATA = 1
    ACK = 2


@dataclass(frozen=True, slots=True)
class Frame:
    frame_type: FrameType
    message_id: int
    payload: bytes = b""


class MessageIdGenerator:
    """Generate process-local 32-bit identifiers with a randomized initial value."""

    def __init__(self, initial: int | None = None) -> None:
        self._next = secrets.randbits(32) if initial is None else initial
        if not 0 <= self._next <= 0xFFFFFFFF:
            raise ValueError("initial message identifier must fit in 32 bits")

    def next(self) -> int:
        value = self._next
        self._next = (self._next + 1) & 0xFFFFFFFF
        return value


def data_frame(message_id: int, payload: bytes) -> Frame:
    return Frame(FrameType.DATA, message_id, payload)


def ack_frame(message_id: int) -> Frame:
    return Frame(FrameType.ACK, message_id)


def ack_matches(frame: Frame, message_id: int) -> bool:
    return (
        frame.frame_type is FrameType.ACK
        and frame.message_id == message_id
        and not frame.payload
    )


def serialize_frame(frame: Frame, maximum_payload: int = DEFAULT_MAXIMUM_PAYLOAD) -> bytes:
    _validate_frame(frame, maximum_payload)
    header = _HEADER.pack(
        PROTOCOL_VERSION, int(frame.frame_type), frame.message_id, len(frame.payload)
    )
    protected = header + frame.payload
    checksum = _CRC.pack(zlib.crc32(protected) & 0xFFFFFFFF)
    return PREAMBLE + protected + checksum


def expected_frame_size(prefix: bytes, maximum_payload: int = DEFAULT_MAXIMUM_PAYLOAD) -> int:
    """Read a validated header and return the complete serialized frame size."""

    header_end = len(PREAMBLE) + _HEADER.size
    if len(prefix) < header_end:
        raise ProtocolError("frame is shorter than the preamble and header")
    if prefix[: len(PREAMBLE)] != PREAMBLE:
        raise ProtocolError("preamble mismatch")
    version, raw_type, _message_id, payload_length = _HEADER.unpack(
        prefix[len(PREAMBLE) : header_end]
    )
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    try:
        frame_type = FrameType(raw_type)
    except ValueError as exc:
        raise ProtocolError(f"unknown frame type {raw_type}") from exc
    if payload_length > maximum_payload:
        raise ProtocolError(f"payload length {payload_length} exceeds maximum {maximum_payload}")
    if frame_type is FrameType.ACK and payload_length:
        raise ProtocolError("ACK frames must have an empty payload")
    return header_end + payload_length + _CRC.size


def parse_frame(raw: bytes, maximum_payload: int = DEFAULT_MAXIMUM_PAYLOAD) -> Frame:
    expected = expected_frame_size(raw, maximum_payload)
    if len(raw) != expected:
        raise ProtocolError(f"frame length is {len(raw)} bytes; expected {expected}")
    header_start = len(PREAMBLE)
    header_end = header_start + _HEADER.size
    version, raw_type, message_id, payload_length = _HEADER.unpack(raw[header_start:header_end])
    protected = raw[header_start:-_CRC.size]
    received_crc = _CRC.unpack(raw[-_CRC.size :])[0]
    calculated_crc = zlib.crc32(protected) & 0xFFFFFFFF
    if received_crc != calculated_crc:
        raise CrcMismatch(
            f"CRC mismatch: received 0x{received_crc:08x}, calculated 0x{calculated_crc:08x}"
        )
    frame = Frame(FrameType(raw_type), message_id, raw[header_end : header_end + payload_length])
    _validate_frame(frame, maximum_payload)
    if version != PROTOCOL_VERSION:  # Defensive; expected_frame_size already checks this.
        raise ProtocolError(f"unsupported protocol version {version}")
    return frame


def _validate_frame(frame: Frame, maximum_payload: int) -> None:
    if not isinstance(frame.frame_type, FrameType):
        raise ProtocolError("frame_type must be a FrameType")
    if not 0 <= frame.message_id <= 0xFFFFFFFF:
        raise ProtocolError("message identifier must fit in 32 bits")
    if len(frame.payload) > maximum_payload:
        raise ProtocolError(
            f"payload length {len(frame.payload)} exceeds maximum {maximum_payload}"
        )
    if frame.frame_type is FrameType.ACK and frame.payload:
        raise ProtocolError("ACK frames must have an empty payload")
