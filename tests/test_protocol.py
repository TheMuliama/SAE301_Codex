from __future__ import annotations

import zlib

import pytest

from sae301.framing import bits_to_bytes, bytes_to_bits, decode_text, encode_text
from sae301.protocol import (
    PREAMBLE,
    CrcMismatch,
    Frame,
    FrameType,
    MessageIdGenerator,
    ProtocolError,
    ack_frame,
    ack_matches,
    data_frame,
    expected_frame_size,
    parse_frame,
    serialize_frame,
)


def test_utf8_round_trip() -> None:
    text = "Bonjour Réunion 🌋 — QPSK"
    assert decode_text(encode_text(text)) == text


def test_utf8_limit_is_applied_to_bytes_not_characters() -> None:
    with pytest.raises(ValueError, match="maximum"):
        encode_text("éé", maximum_bytes=3)


def test_bit_packing_msb_first_round_trip() -> None:
    payload = bytes.fromhex("80a55a01ff")
    bits = bytes_to_bits(payload)
    assert bits[:8].tolist() == [1, 0, 0, 0, 0, 0, 0, 0]
    assert bits_to_bytes(bits) == payload


def test_incomplete_or_invalid_bits_are_rejected() -> None:
    with pytest.raises(ValueError, match="multiple"):
        bits_to_bytes([0, 1, 0])
    with pytest.raises(ValueError, match="only"):
        bits_to_bytes([0, 2, 0, 0, 0, 0, 0, 0])


@pytest.mark.parametrize(
    "frame",
    [data_frame(0x10203040, "QPSK ✓".encode()), ack_frame(0xFFFFFFFF)],
)
def test_frame_round_trip(frame: Frame) -> None:
    serialized = serialize_frame(frame)
    assert serialized.startswith(PREAMBLE)
    assert expected_frame_size(serialized) == len(serialized)
    assert parse_frame(serialized) == frame


def test_crc_covers_header_and_payload() -> None:
    serialized = bytearray(serialize_frame(data_frame(7, b"hello")))
    serialized[-5] ^= 0x01
    with pytest.raises(CrcMismatch):
        parse_frame(bytes(serialized))


def test_crc_is_standard_crc32_network_order() -> None:
    serialized = serialize_frame(data_frame(1, b"x"))
    protected = serialized[len(PREAMBLE) : -4]
    assert int.from_bytes(serialized[-4:], "big") == zlib.crc32(protected) & 0xFFFFFFFF


def test_ack_validation_requires_type_identifier_and_empty_payload() -> None:
    assert ack_matches(ack_frame(41), 41)
    assert not ack_matches(ack_frame(42), 41)
    assert not ack_matches(data_frame(41, b""), 41)
    with pytest.raises(ProtocolError, match="empty"):
        serialize_frame(Frame(FrameType.ACK, 41, b"not allowed"))


def test_oversized_payload_and_bad_identifier_are_rejected() -> None:
    with pytest.raises(ProtocolError, match="exceeds"):
        serialize_frame(data_frame(1, b"12345"), maximum_payload=4)
    with pytest.raises(ProtocolError, match="32 bits"):
        serialize_frame(data_frame(2**32, b""))


def test_declared_oversized_payload_is_rejected_before_crc() -> None:
    raw = (
        PREAMBLE
        + bytes([1, int(FrameType.DATA)])
        + (7).to_bytes(4, "big")
        + (5000).to_bytes(2, "big")
    )
    with pytest.raises(ProtocolError, match="exceeds"):
        expected_frame_size(raw, maximum_payload=1024)


def test_message_identifier_sequence_and_wrap() -> None:
    identifiers = MessageIdGenerator(initial=0xFFFFFFFE)
    assert [identifiers.next() for _ in range(3)] == [0xFFFFFFFE, 0xFFFFFFFF, 0]
