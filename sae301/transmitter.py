"""DATA sender and strict matching-ACK state machine."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass

from .config import AppConfig
from .framing import encode_text
from .protocol import MessageIdGenerator, ProtocolError, ack_matches, data_frame, serialize_frame
from .qpsk import modulate_bytes
from .synchronization import SynchronizationError, decode_burst
from .transport.base import IQTransport, TransportTimeout

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    delivered: bool
    message_id: int
    ignored_bursts: int
    reason: str | None = None


class Transmitter:
    def __init__(
        self,
        transport: IQTransport,
        config: AppConfig,
        identifiers: MessageIdGenerator | None = None,
    ) -> None:
        self.transport = transport
        self.config = config
        self.identifiers = identifiers or MessageIdGenerator()

    def send_text(self, text: str) -> DeliveryResult:
        payload = encode_text(text, self.config.maximum_payload_bytes)
        message_id = self.identifiers.next()
        raw = serialize_frame(data_frame(message_id, payload), self.config.maximum_payload_bytes)
        samples = modulate_bytes(
            raw,
            samples_per_symbol=self.config.dsp.samples_per_symbol,
            rolloff=self.config.dsp.rrc_rolloff,
            span_symbols=self.config.dsp.rrc_span_symbols,
        )
        # Anything received before this DATA cannot acknowledge this transaction.
        self.transport.flush_input()
        self.transport.send_samples(samples)
        deadline = time.monotonic() + self.config.ack_timeout_seconds
        ignored = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return DeliveryResult(False, message_id, ignored, "ACK timeout")
            try:
                response = self.transport.receive_samples(remaining)
            except TransportTimeout:
                return DeliveryResult(False, message_id, ignored, "ACK timeout")
            try:
                decoded = decode_burst(response, self.config.dsp, self.config.maximum_payload_bytes)
            except (SynchronizationError, ProtocolError) as exc:
                LOGGER.warning("Ignoring invalid ACK burst: %s", exc)
                ignored += 1
                continue
            if ack_matches(decoded.frame, message_id):
                return DeliveryResult(True, message_id, ignored)
            LOGGER.info(
                "Ignoring non-matching frame type=%s id=%u while waiting for id=%u",
                decoded.frame.frame_type.name,
                decoded.frame.message_id,
                message_id,
            )
            ignored += 1


def _create_transport(config: AppConfig, mode: str, rf_authorized: bool) -> IQTransport:
    if mode == "simulation":
        from .transport.simulation import SimulationTransport

        return SimulationTransport(config.simulation)
    from .transport.pluto import PlutoTransport

    return PlutoTransport(config.radio, allow_transmit=rf_authorized)


def run_transmitter(config: AppConfig, args: argparse.Namespace) -> int:
    transport = _create_transport(config, args.mode, args.rf_authorized)
    try:
        label = (
            "ADALM-Pluto connected."
            if args.mode == "hardware"
            else "Simulation transport ready."
        )
        print(label)
        print("Ready to transmit.")
        sender = Transmitter(transport, config)
        one_message = args.message
        while True:
            try:
                message = one_message if one_message is not None else input("\nEnter message: ")
            except EOFError:
                return 0
            if not message:
                if one_message is not None:
                    print("Message is empty; nothing sent.")
                    return 2
                continue
            print("Encoding message...")
            print("Transmitting QPSK signal...")
            print("Waiting for acknowledgment...")
            result = sender.send_text(message)
            if result.delivered:
                print("ACK received.")
                print("Message successfully delivered.")
            else:
                print(f"Delivery failed: {result.reason}.")
            if one_message is not None:
                return 0 if result.delivered else 1
    except KeyboardInterrupt:
        print("\nTransmitter stopped.")
        return 130
    finally:
        transport.close()
