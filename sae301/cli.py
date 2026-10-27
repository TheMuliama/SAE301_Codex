"""Terminal interface for transmitter, receiver, and safe diagnostics."""

from __future__ import annotations

import argparse
import importlib.util
import platform
import sys
from collections.abc import Sequence

from . import __version__
from .config import AppConfig, ConfigurationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sae301", description="Liaison QPSK DATA/ACK SAÉ 3.01")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for role in ("transmitter", "receiver"):
        command = subparsers.add_parser(role, help=f"run the {role}")
        _add_runtime_arguments(command, role)
        if role == "transmitter":
            command.add_argument("--message", help="send one message non-interactively")
        else:
            command.add_argument(
                "--once", action="store_true", help="exit after one valid DATA frame"
            )

    check = subparsers.add_parser("check", help="verify configuration without transmitting RF")
    check.add_argument("--mode", choices=("simulation", "hardware"), default="simulation")
    check.add_argument("--config", metavar="PATH")
    check.add_argument("--pluto-uri", metavar="URI")
    return parser


def _add_runtime_arguments(parser: argparse.ArgumentParser, role: str) -> None:
    parser.add_argument("--mode", choices=("simulation", "hardware"), default="simulation")
    parser.add_argument("--config", metavar="PATH")
    parser.add_argument("--bind-host")
    parser.add_argument("--bind-port", type=int)
    parser.add_argument("--peer-host")
    parser.add_argument("--peer-port", type=int)
    parser.add_argument("--snr-db", type=float)
    parser.add_argument("--phase-offset-deg", type=float)
    parser.add_argument("--timing-offset-samples", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--ack-timeout", type=float)
    parser.add_argument("--pluto-uri")
    parser.add_argument(
        "--rf-authorized",
        action="store_true",
        help="confirm attenuation, power, device, laboratory, and regulatory checks",
    )
    parser.set_defaults(role=role)


def load_runtime_config(args: argparse.Namespace) -> AppConfig:
    config = AppConfig.from_json(args.config) if args.config else AppConfig()
    simulation = config.simulation
    role_defaults = (
        (9001, 9000)
        if getattr(args, "role", "receiver") == "transmitter"
        else (9000, 9001)
    )
    if args.bind_port is not None:
        simulation.bind_port = args.bind_port
    elif not args.config:
        simulation.bind_port = role_defaults[0]
    if args.peer_port is not None:
        simulation.peer_port = args.peer_port
    elif not args.config:
        simulation.peer_port = role_defaults[1]
    for argument, attribute in (
        ("bind_host", "bind_host"),
        ("peer_host", "peer_host"),
        ("snr_db", "noise_snr_db"),
        ("phase_offset_deg", "phase_offset_deg"),
        ("timing_offset_samples", "timing_offset_samples"),
        ("seed", "random_seed"),
    ):
        value = getattr(args, argument, None)
        if value is not None:
            setattr(simulation, attribute, value)
    if getattr(args, "ack_timeout", None) is not None:
        config.ack_timeout_seconds = args.ack_timeout
    if getattr(args, "pluto_uri", None):
        config.radio.uri = args.pluto_uri
    config.validate()
    return config


def run_check(args: argparse.Namespace) -> int:
    config = AppConfig.from_json(args.config) if args.config else AppConfig()
    if args.pluto_uri:
        config.radio.uri = args.pluto_uri
    config.validate()
    print(f"sae301 {__version__}")
    print(f"Python {platform.python_version()} on {platform.system()}")
    print("Configuration: OK")
    try:
        import numpy as np
    except ImportError:
        print("NumPy: MISSING", file=sys.stderr)
        return 2
    print(f"NumPy: OK ({np.__version__})")
    if args.mode == "simulation":
        print("Simulation dependencies: OK")
        print("RF transmission: not requested")
        return 0
    if importlib.util.find_spec("adi") is None:
        print("PyADI-IIO: MISSING (install the 'pluto' extra)", file=sys.stderr)
        return 2
    from .transport.pluto import check_pluto_connectivity

    check_pluto_connectivity(config.radio)
    print(f"ADALM-Pluto connectivity: OK ({config.radio.uri})")
    print("RF transmission: not requested")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return run_check(args)
        config = load_runtime_config(args)
        if args.mode == "hardware" and not args.rf_authorized:
            parser.error(
                "hardware operation requires --rf-authorized after verifying coaxial attenuation, "
                "power levels, Pluto limits, and laboratory/regulatory conditions"
            )
        if args.command == "transmitter":
            from .transmitter import run_transmitter

            return run_transmitter(config, args)
        from .receiver import run_receiver

        return run_receiver(config, args)
    except (ConfigurationError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
