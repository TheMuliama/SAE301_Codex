from __future__ import annotations

import numpy as np
import pytest

from sae301.config import DspConfig
from sae301.framing import bytes_to_bits
from sae301.protocol import CrcMismatch, data_frame, serialize_frame
from sae301.qpsk import bits_to_symbols, modulate_bytes, rrc_taps, symbols_to_bits
from sae301.synchronization import SynchronizationError, decode_burst


def test_qpsk_mapping_and_hard_decision_round_trip() -> None:
    bits = np.asarray([0, 0, 0, 1, 1, 1, 1, 0], dtype=np.uint8)
    symbols = bits_to_symbols(bits)
    expected = np.asarray([1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j]) / np.sqrt(2)
    np.testing.assert_allclose(symbols, expected)
    np.testing.assert_array_equal(symbols_to_bits(symbols), bits)


def test_rrc_has_unit_energy_and_odd_symmetric_length() -> None:
    taps = rrc_taps(8, 0.35, 8)
    assert taps.size == 65
    np.testing.assert_allclose(taps, taps[::-1], atol=1e-14)
    assert np.sum(taps**2) == pytest.approx(1.0)


def test_complete_dsp_round_trip_with_timing_and_phase() -> None:
    config = DspConfig()
    frame = data_frame(301, "message reçu ✓".encode())
    samples = modulate_bytes(serialize_frame(frame))
    impaired = np.pad(samples * np.exp(1j * np.deg2rad(117)), (5, 0))
    decoded = decode_burst(impaired, config)
    assert decoded.frame == frame
    assert decoded.synchronization.correlation > 0.95
    assert decoded.synchronization.phase_offset_radians == pytest.approx(
        np.deg2rad(117), abs=0.04
    )


def test_noise_tolerance_at_10_db_with_deterministic_seed() -> None:
    config = DspConfig()
    frame = data_frame(99, bytes(range(128)))
    samples = modulate_bytes(serialize_frame(frame)).astype(np.complex128)
    rng = np.random.default_rng(301)
    active_power = float(np.mean(np.abs(samples[np.abs(samples) > 1e-6]) ** 2))
    noise_power = active_power / (10 ** (10 / 10))
    noise = np.sqrt(noise_power / 2) * (
        rng.standard_normal(samples.size) + 1j * rng.standard_normal(samples.size)
    )
    impaired = np.pad((samples + noise) * np.exp(1j * 0.41), (11, 0))
    assert decode_burst(impaired, config).frame == frame


def test_preamble_detection_rejects_unrelated_noise() -> None:
    rng = np.random.default_rng(123)
    samples = rng.standard_normal(4096) + 1j * rng.standard_normal(4096)
    with pytest.raises(SynchronizationError, match="correlation"):
        decode_burst(samples, DspConfig(sync_threshold=0.9))


def test_corrupted_frame_is_rejected_after_valid_synchronization() -> None:
    raw = bytearray(serialize_frame(data_frame(22, b"integrity")))
    raw[-1] ^= 0x80
    samples = modulate_bytes(bytes(raw))
    with pytest.raises(CrcMismatch):
        decode_burst(samples, DspConfig())


def test_preamble_itself_maps_to_an_integral_number_of_symbols() -> None:
    assert bytes_to_bits(bytes.fromhex("f35ac7196d84b2e1")).size % 2 == 0

