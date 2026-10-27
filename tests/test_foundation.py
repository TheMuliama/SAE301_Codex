from __future__ import annotations

import json

import pytest

import sae301
from sae301.cli import build_parser, load_runtime_config, main
from sae301.config import AppConfig, ConfigurationError


def test_package_import_and_version() -> None:
    assert sae301.__version__ == "0.1.0"


def test_default_configuration_is_valid() -> None:
    config = AppConfig()
    config.validate()
    assert config.radio.carrier_frequency_hz == 868_000_000
    assert config.dsp.samples_per_symbol == 8


def test_json_configuration_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"ack_timeout_seconds": 1.5, "dsp": {"sync_threshold": 0.8}}))
    config = AppConfig.from_json(path)
    assert config.ack_timeout_seconds == 1.5
    assert config.dsp.sync_threshold == 0.8


def test_unknown_configuration_key_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="unknown"):
        AppConfig.from_dict({"surprise": True})


def test_invalid_radio_bandwidth_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="bandwidth"):
        AppConfig.from_dict({"radio": {"rf_bandwidth_hz": 1}})


def test_cli_role_specific_simulation_ports() -> None:
    parser = build_parser()
    tx = load_runtime_config(parser.parse_args(["transmitter"]))
    rx = load_runtime_config(parser.parse_args(["receiver"]))
    assert (tx.simulation.bind_port, tx.simulation.peer_port) == (9001, 9000)
    assert (rx.simulation.bind_port, rx.simulation.peer_port) == (9000, 9001)


def test_check_command_is_non_transmitting(capsys) -> None:
    assert main(["check", "--mode", "simulation"]) == 0
    output = capsys.readouterr().out
    assert "Configuration: OK" in output
    assert "RF transmission: not requested" in output


def test_hardware_runtime_requires_explicit_rf_authorization(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["transmitter", "--mode", "hardware", "--message", "unsafe"])
    assert raised.value.code == 2
    assert "--rf-authorized" in capsys.readouterr().err


def test_runtime_overrides_are_applied() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["transmitter", "--bind-port", "12001", "--peer-port", "12000", "--ack-timeout", "0.5"]
    )
    config = load_runtime_config(args)
    assert config.simulation.bind_port == 12001
    assert config.simulation.peer_port == 12000
    assert config.ack_timeout_seconds == 0.5


def test_json_simulation_ports_are_not_replaced_by_role_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"simulation": {"bind_port": 13001, "peer_port": 13000}}))
    parser = build_parser()
    config = load_runtime_config(parser.parse_args(["transmitter", "--config", str(path)]))
    assert (config.simulation.bind_port, config.simulation.peer_port) == (13001, 13000)


def test_receive_buffer_must_hold_maximum_frame() -> None:
    with pytest.raises(ConfigurationError, match="rx_buffer_size"):
        AppConfig.from_dict({"radio": {"rx_buffer_size": 1024}})
