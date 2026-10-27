"""Transport boundary shared by simulated and physical I/Q links."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray


class TransportError(RuntimeError):
    """Base class for transport failures."""


class TransportTimeout(TransportError):
    """No complete I/Q burst arrived before a deadline."""


class IQTransport(ABC):
    """Exchange complete complex baseband bursts."""

    @abstractmethod
    def send_samples(self, samples: NDArray[np.complexfloating]) -> None:
        """Send one finite I/Q burst."""

    @abstractmethod
    def receive_samples(self, timeout: float | None = None) -> NDArray[np.complex64]:
        """Receive one finite I/Q burst or raise ``TransportTimeout``."""

    @abstractmethod
    def flush_input(self) -> None:
        """Discard complete or partial stale receive data."""

    @abstractmethod
    def close(self) -> None:
        """Release transport resources."""

    def __enter__(self) -> IQTransport:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
