from __future__ import annotations

import queue
import socket
import threading

import numpy as np
import pytest

from sae301.config import AppConfig, SimulationConfig
from sae301.framing import encode_text
from sae301.protocol import MessageIdGenerator, ack_frame, data_frame, serialize_frame
from sae301.qpsk import modulate_bytes
from sae301.receiver import Receiver
from sae301.synchronization import decode_burst
from sae301.transmitter import Transmitter
from sae301.transport.base import IQTransport, TransportTimeout
from sae301.transport.simulation import SimulationTransport, apply_impairments


class QueueTransport(IQTransport):
    def __init__(self) -> None:
        self.incoming: queue.Queue[np.ndarray] = queue.Queue()
        self.peer: QueueTransport | None = None
        self.closed = False

    def send_samples(self, samples) -> None:
        assert self.peer is not None
        self.peer.incoming.put(np.asarray(samples, dtype=np.complex64).copy())

    def receive_samples(self, timeout=None):
        try:
            return self.incoming.get(timeout=timeout)
        except queue.Empty as exc:
            raise TransportTimeout("test timeout") from exc

    def flush_input(self) -> None:
        while True:
            try:
                self.incoming.get_nowait()
            except queue.Empty:
                break

    def close(self) -> None:
        self.closed = True


def transport_pair() -> tuple[QueueTransport, QueueTransport]:
    left, right = QueueTransport(), QueueTransport()
    left.peer, right.peer = right, left
    return left, right


def quick_config() -> AppConfig:
    config = AppConfig(ack_timeout_seconds=0.25, ack_turnaround_seconds=0)
    config.validate()
    return config


def test_complete_data_ack_exchange_and_message_reconstruction() -> None:
    tx_transport, rx_transport = transport_pair()
    config = quick_config()
    sender = Transmitter(tx_transport, config, MessageIdGenerator(initial=301))
    receiver = Receiver(rx_transport, config)
    received = []

    thread = threading.Thread(target=lambda: received.append(receiver.receive_once(1)))
    thread.start()
    result = sender.send_text("Bonjour du Pluto A 🌋")
    thread.join(timeout=2)

    assert result.delivered
    assert result.message_id == 301
    assert received[0].text == "Bonjour du Pluto A 🌋"
    assert not received[0].duplicate


@pytest.mark.parametrize("corrupt", [False, True])
def test_incorrect_or_corrupted_ack_never_reports_success(corrupt: bool) -> None:
    tx_transport, responder_transport = transport_pair()
    config = quick_config()
    sender = Transmitter(tx_transport, config, MessageIdGenerator(initial=55))

    def respond() -> None:
        responder_transport.receive_samples(1)
        raw = bytearray(serialize_frame(ack_frame(999)))
        if corrupt:
            raw[-1] ^= 0x01
        responder_transport.send_samples(modulate_bytes(bytes(raw)))

    thread = threading.Thread(target=respond)
    thread.start()
    result = sender.send_text("must time out")
    thread.join(timeout=2)
    assert not result.delivered
    assert result.reason == "ACK timeout"
    assert result.ignored_bursts == 1


def test_ack_timeout_when_no_receiver_exists() -> None:
    tx_transport, _unused = transport_pair()
    config = quick_config()
    result = Transmitter(tx_transport, config, MessageIdGenerator(initial=1)).send_text("alone")
    assert not result.delivered
    assert result.reason == "ACK timeout"


def test_stale_matching_ack_is_flushed_before_new_data() -> None:
    tx_transport, _unused = transport_pair()
    config = quick_config()
    tx_transport.incoming.put(modulate_bytes(serialize_frame(ack_frame(7))))
    result = Transmitter(tx_transport, config, MessageIdGenerator(initial=7)).send_text("new")
    assert not result.delivered
    assert result.ignored_bursts == 0


def test_corrupted_data_is_rejected_without_ack() -> None:
    sender_transport, rx_transport = transport_pair()
    config = quick_config()
    receiver = Receiver(rx_transport, config)
    raw = bytearray(serialize_frame(data_frame(9, b"broken")))
    raw[-2] ^= 0x40
    sender_transport.send_samples(modulate_bytes(bytes(raw)))
    with pytest.raises(TransportTimeout):
        receiver.receive_once(0.05)
    with pytest.raises(TransportTimeout):
        sender_transport.receive_samples(0.01)


def test_invalid_utf8_data_is_rejected_without_ack() -> None:
    sender_transport, rx_transport = transport_pair()
    config = quick_config()
    receiver = Receiver(rx_transport, config)
    sender_transport.send_samples(modulate_bytes(serialize_frame(data_frame(10, b"\xff"))))
    with pytest.raises(TransportTimeout):
        receiver.receive_once(0.05)
    with pytest.raises(TransportTimeout):
        sender_transport.receive_samples(0.01)


def test_multiple_messages_and_duplicate_data_are_acknowledged() -> None:
    sender_transport, rx_transport = transport_pair()
    config = quick_config()
    receiver = Receiver(rx_transport, config, duplicate_window=4)
    messages = []
    raw = serialize_frame(data_frame(77, encode_text("same")))
    for _ in range(2):
        sender_transport.send_samples(modulate_bytes(raw))
        messages.append(receiver.receive_once(0.5))
        ack = decode_burst(sender_transport.receive_samples(0.5), config.dsp).frame
        assert ack == ack_frame(77)
    assert [message.duplicate for message in messages] == [False, True]

    for identifier, text in ((78, "second"), (79, "third")):
        raw = serialize_frame(data_frame(identifier, text.encode()))
        sender_transport.send_samples(modulate_bytes(raw))
        assert receiver.receive_once(0.5).text == text
        sender_transport.receive_samples(0.5)


def test_two_successive_transmitter_transactions() -> None:
    tx_transport, rx_transport = transport_pair()
    config = quick_config()
    sender = Transmitter(tx_transport, config, MessageIdGenerator(initial=500))
    receiver = Receiver(rx_transport, config)
    received = []

    def receive_twice() -> None:
        received.extend(receiver.receive_once(1) for _ in range(2))

    thread = threading.Thread(target=receive_twice)
    thread.start()
    first = sender.send_text("one")
    second = sender.send_text("two")
    thread.join(timeout=2)
    assert first.delivered and second.delivered
    assert [first.message_id, second.message_id] == [500, 501]
    assert [message.text for message in received] == ["one", "two"]


def _free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def test_real_udp_transport_fragments_iq_and_supports_impairments() -> None:
    rx_port, tx_port = _free_udp_port(), _free_udp_port()
    while tx_port == rx_port:
        tx_port = _free_udp_port()
    rx_config = SimulationConfig(bind_port=rx_port, peer_port=tx_port, random_seed=1)
    tx_config = SimulationConfig(
        bind_port=tx_port,
        peer_port=rx_port,
        random_seed=301,
        noise_snr_db=14,
        phase_offset_deg=83,
        timing_offset_samples=5,
    )
    receiver_transport = SimulationTransport(rx_config)
    transmitter_transport = SimulationTransport(tx_config)
    try:
        payload = bytes(range(256)) + bytes(range(64))
        samples = modulate_bytes(serialize_frame(data_frame(123, payload)))
        assert samples.nbytes > 60_000  # Exercises UDP fragmentation.
        transmitter_transport.send_samples(samples)
        received = receiver_transport.receive_samples(1)
        assert decode_burst(received, AppConfig().dsp).frame == data_frame(123, payload)
    finally:
        transmitter_transport.close()
        receiver_transport.close()


def test_real_udp_complete_data_ack_exchange_with_impairments() -> None:
    rx_port, tx_port = _free_udp_port(), _free_udp_port()
    while tx_port == rx_port:
        tx_port = _free_udp_port()
    receiver_config = AppConfig(
        simulation=SimulationConfig(
            bind_port=rx_port,
            peer_port=tx_port,
            noise_snr_db=16,
            phase_offset_deg=-61,
            timing_offset_samples=3,
            random_seed=11,
        ),
        ack_turnaround_seconds=0,
    )
    transmitter_config = AppConfig(
        simulation=SimulationConfig(
            bind_port=tx_port,
            peer_port=rx_port,
            noise_snr_db=14,
            phase_offset_deg=83,
            timing_offset_samples=5,
            random_seed=301,
        ),
        ack_timeout_seconds=2,
        ack_turnaround_seconds=0,
    )
    receiver_transport = SimulationTransport(receiver_config.simulation)
    transmitter_transport = SimulationTransport(transmitter_config.simulation)
    received = []
    try:
        receiver = Receiver(receiver_transport, receiver_config)
        sender = Transmitter(
            transmitter_transport, transmitter_config, MessageIdGenerator(initial=808)
        )
        thread = threading.Thread(target=lambda: received.append(receiver.receive_once(2)))
        thread.start()
        result = sender.send_text("UDP I/Q dans les deux sens")
        thread.join(timeout=3)
        assert result.delivered
        assert result.message_id == 808
        assert received[0].text == "UDP I/Q dans les deux sens"
    finally:
        transmitter_transport.close()
        receiver_transport.close()


def test_impairments_are_reproducible_for_equal_seeds() -> None:
    samples = np.ones(32, dtype=np.complex64)
    config = SimulationConfig(noise_snr_db=8, phase_offset_deg=20, timing_offset_samples=3)
    first = apply_impairments(samples, config, np.random.default_rng(42))
    second = apply_impairments(samples, config, np.random.default_rng(42))
    np.testing.assert_array_equal(first, second)
