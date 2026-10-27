"""DATA receiver, duplicate tracking, UTF-8 validation, and automatic ACK."""

from __future__ import annotations

import argparse
import logging
import time
from collections import deque
from dataclasses import dataclass

from .config import AppConfig
from .framing import decode_text
from .protocol import FrameType, ProtocolError, ack_frame, serialize_frame
from .qpsk import modulate_bytes
from .synchronization import SynchronizationError, decode_burst
from .transport.base import IQTransport, TransportTimeout

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReceivedMessage:
    text: str
    message_id: int
    duplicate: bool
    correlation: float


class Receiver:
    def __init__(
        self, transport: IQTransport, config: AppConfig, duplicate_window: int = 256
    ) -> None:
        if duplicate_window < 1:
            raise ValueError("duplicate_window must be positive")
        self.transport = transport
        self.config = config
        self._recent_order: deque[int] = deque()
        self._recent_ids: set[int] = set()
        self._duplicate_window = duplicate_window

    def receive_once(self, timeout: float | None = None) -> ReceivedMessage:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise TransportTimeout("timed out waiting for a valid DATA frame")
            samples = self.transport.receive_samples(remaining)
            try:
                decoded = decode_burst(samples, self.config.dsp, self.config.maximum_payload_bytes)
            except (SynchronizationError, ProtocolError) as exc:
                LOGGER.warning("Rejected invalid DATA burst: %s", exc)
                continue
            frame = decoded.frame
            if frame.frame_type is not FrameType.DATA:
                LOGGER.info(
                    "Ignoring non-DATA frame type=%s id=%u",
                    frame.frame_type.name,
                    frame.message_id,
                )
                continue
            try:
                text = decode_text(frame.payload)
            except UnicodeDecodeError as exc:
                LOGGER.warning("Rejected DATA id=%u with invalid UTF-8: %s", frame.message_id, exc)
                continue
            duplicate = frame.message_id in self._recent_ids
            if not duplicate:
                self._remember(frame.message_id)
            if self.config.ack_turnaround_seconds:
                time.sleep(self.config.ack_turnaround_seconds)
            ack = serialize_frame(ack_frame(frame.message_id), self.config.maximum_payload_bytes)
            ack_samples = modulate_bytes(
                ack,
                samples_per_symbol=self.config.dsp.samples_per_symbol,
                rolloff=self.config.dsp.rrc_rolloff,
                span_symbols=self.config.dsp.rrc_span_symbols,
            )
            self.transport.send_samples(ack_samples)
            return ReceivedMessage(
                text, frame.message_id, duplicate, decoded.synchronization.correlation
            )

    def _remember(self, message_id: int) -> None:
        if len(self._recent_order) >= self._duplicate_window:
            expired = self._recent_order.popleft()
            self._recent_ids.remove(expired)
        self._recent_order.append(message_id)
        self._recent_ids.add(message_id)


def _create_transport(config: AppConfig, mode: str, rf_authorized: bool) -> IQTransport:
    if mode == "simulation":
        from .transport.simulation import SimulationTransport

        return SimulationTransport(config.simulation)
    from .transport.pluto import PlutoTransport

    return PlutoTransport(config.radio, allow_transmit=rf_authorized)


def run_receiver(config: AppConfig, args: argparse.Namespace) -> int:
    transport = _create_transport(config, args.mode, args.rf_authorized)
    try:
        label = (
            "ADALM-Pluto connected."
            if args.mode == "hardware"
            else "Simulation transport ready."
        )
        print(label)
        print("Listening for messages...")
        receiver = Receiver(transport, config)
        while True:
            message = receiver.receive_once()
            duplicate = " (duplicate)" if message.duplicate else ""
            print(f"\nMessage received{duplicate}: {message.text}")
            print("CRC verification: PASSED")
            print("ACK transmitted.")
            if args.once:
                return 0
            print("\nListening for messages...")
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
        return 130
    finally:
        transport.close()
