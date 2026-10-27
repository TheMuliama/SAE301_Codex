"""Validated, platform-independent application configuration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    """Raised when configuration is invalid or contains unknown fields."""


@dataclass(slots=True)
class DspConfig:
    samples_per_symbol: int = 8
    rrc_rolloff: float = 0.35
    rrc_span_symbols: int = 8
    sync_threshold: float = 0.72

    def validate(self) -> None:
        if self.samples_per_symbol < 2:
            raise ConfigurationError("samples_per_symbol must be at least 2")
        if not 0.0 < self.rrc_rolloff <= 1.0:
            raise ConfigurationError("rrc_rolloff must be in (0, 1]")
        if self.rrc_span_symbols < 4 or self.rrc_span_symbols % 2:
            raise ConfigurationError("rrc_span_symbols must be even and at least 4")
        if not 0.0 < self.sync_threshold <= 1.0:
            raise ConfigurationError("sync_threshold must be in (0, 1]")


@dataclass(slots=True)
class RadioConfig:
    carrier_frequency_hz: int = 868_000_000
    sample_rate_hz: int = 1_000_000
    rf_bandwidth_hz: int = 500_000
    tx_gain_db: float = -30.0
    rx_gain_db: float = 30.0
    rx_buffer_size: int = 65_536
    uri: str = "ip:192.168.2.1"

    def validate(self, dsp: DspConfig) -> None:
        if self.carrier_frequency_hz <= 0:
            raise ConfigurationError("carrier_frequency_hz must be positive")
        if self.sample_rate_hz < 521_000:
            raise ConfigurationError("Pluto sample_rate_hz must be at least 521000")
        if self.rf_bandwidth_hz <= 0 or self.rf_bandwidth_hz > self.sample_rate_hz:
            raise ConfigurationError("rf_bandwidth_hz must be positive and <= sample_rate_hz")
        if not -89.75 <= self.tx_gain_db <= 0:
            raise ConfigurationError("tx_gain_db must be between -89.75 and 0 dB")
        if not -3 <= self.rx_gain_db <= 73:
            raise ConfigurationError("rx_gain_db must be between -3 and 73 dB")
        if self.rx_buffer_size < 1024:
            raise ConfigurationError("rx_buffer_size must be at least 1024")
        occupied = (self.sample_rate_hz / dsp.samples_per_symbol) * (1 + dsp.rrc_rolloff)
        if self.rf_bandwidth_hz < occupied:
            raise ConfigurationError("rf_bandwidth_hz is too narrow for the configured waveform")


@dataclass(slots=True)
class SimulationConfig:
    bind_host: str = "127.0.0.1"
    bind_port: int = 9000
    peer_host: str = "127.0.0.1"
    peer_port: int = 9001
    noise_snr_db: float | None = None
    phase_offset_deg: float = 0.0
    timing_offset_samples: int = 0
    random_seed: int = 301

    def validate(self) -> None:
        for name, port in (("bind_port", self.bind_port), ("peer_port", self.peer_port)):
            if not 1 <= port <= 65535:
                raise ConfigurationError(f"{name} must be between 1 and 65535")
        if self.timing_offset_samples < 0:
            raise ConfigurationError("timing_offset_samples must not be negative")


@dataclass(slots=True)
class AppConfig:
    dsp: DspConfig = field(default_factory=DspConfig)
    radio: RadioConfig = field(default_factory=RadioConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    ack_timeout_seconds: float = 3.0
    maximum_payload_bytes: int = 1024
    ack_turnaround_seconds: float = 0.08

    def validate(self) -> None:
        self.dsp.validate()
        self.radio.validate(self.dsp)
        self.simulation.validate()
        if self.ack_timeout_seconds <= 0:
            raise ConfigurationError("ack_timeout_seconds must be positive")
        if not 1 <= self.maximum_payload_bytes <= 65535:
            raise ConfigurationError("maximum_payload_bytes must be in [1, 65535]")
        if self.ack_turnaround_seconds < 0:
            raise ConfigurationError("ack_turnaround_seconds must not be negative")
        # A complete maximum-size frame must fit within one physical RX buffer;
        # PlutoTransport concatenates two buffers to cover boundary crossings.
        serialized_bytes = self.maximum_payload_bytes + 20
        shaped_samples = (
            serialized_bytes * 4 * self.dsp.samples_per_symbol
            + self.dsp.rrc_span_symbols * self.dsp.samples_per_symbol
            + 16 * self.dsp.samples_per_symbol
        )
        if self.radio.rx_buffer_size < shaped_samples:
            raise ConfigurationError(
                "rx_buffer_size is too small for maximum_payload_bytes and the DSP waveform"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> AppConfig:
        allowed = {
            "dsp",
            "radio",
            "simulation",
            "ack_timeout_seconds",
            "maximum_payload_bytes",
            "ack_turnaround_seconds",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ConfigurationError(f"unknown top-level configuration keys: {sorted(unknown)}")
        try:
            config = cls(
                dsp=_section(DspConfig, values.get("dsp", {})),
                radio=_section(RadioConfig, values.get("radio", {})),
                simulation=_section(SimulationConfig, values.get("simulation", {})),
                ack_timeout_seconds=values.get("ack_timeout_seconds", 3.0),
                maximum_payload_bytes=values.get("maximum_payload_bytes", 1024),
                ack_turnaround_seconds=values.get("ack_turnaround_seconds", 0.08),
            )
        except TypeError as exc:
            raise ConfigurationError(str(exc)) from exc
        config.validate()
        return config

    @classmethod
    def from_json(cls, path: str | Path) -> AppConfig:
        source = Path(path)
        try:
            values = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"cannot read configuration {source}: {exc}") from exc
        if not isinstance(values, dict):
            raise ConfigurationError("configuration root must be a JSON object")
        return cls.from_dict(values)


def _section(section_type: type[Any], values: Any) -> Any:
    if not isinstance(values, dict):
        raise ConfigurationError(f"{section_type.__name__} must be a JSON object")
    allowed = set(section_type.__dataclass_fields__)
    unknown = set(values) - allowed
    if unknown:
        raise ConfigurationError(f"unknown {section_type.__name__} keys: {sorted(unknown)}")
    return section_type(**values)
