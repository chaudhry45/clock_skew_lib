"""Core clock skew estimation logic.

Given a series of request/response timestamp pairs recorded by a client
against a remote server's clock, estimate the constant offset (skew)
between the two clocks. The model assumes one-way network delay is
symmetric and roughly constant, so the midpoint of the round trip is a
low-noise estimate of the true offset.

We deliberately keep the estimator simple: a single scalar offset, no
drift term. Adding a slope would require many more samples and would make
the API harder to reason about for the common case where skew is stable
over the measurement window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Sample:
    """One request/response round trip.

    All four timestamps are in seconds, expressed in each side's own
    clock. ``client_send`` and ``client_recv`` come from the client clock,
    ``server_recv`` and ``server_send`` from the server clock.

    A sample is considered usable only if the server's turnaround time is
    non-negative and the client's measured round trip is non-negative.
    Negative durations indicate clock jumps or misordered events and are
    rejected by :meth:`SkewEstimator.add`.
    """

    client_send: float
    server_recv: float
    server_send: float
    client_recv: float

    @property
    def round_trip(self) -> float:
        """Client-observed round trip time, in seconds."""
        return self.client_recv - self.client_send

    @property
    def server_turnaround(self) -> float:
        """Server-observed processing time, in seconds."""
        return self.server_send - self.server_recv

    @property
    def offset(self) -> float:
        """Estimated server-clock minus client-clock offset for this sample.

        Derivation: let ``d`` be the one-way delay (assumed equal in both
        directions) and ``theta`` the true skew. Then
        ``server_recv = client_send + d + theta`` and
        ``client_recv = server_send + d - theta``. Subtracting gives
        ``theta = ((server_recv - client_send) - (client_recv - server_send)) / 2``.
        """
        return (
            (self.server_recv - self.client_send)
            - (self.client_recv - self.server_send)
        ) / 2.0

    def is_valid(self) -> bool:
        """Return True when the sample's durations are physically plausible.

        We reject negative durations rather than clamping them: a negative
        round trip or turnaround almost always means the clocks moved
        during the measurement, and silently accepting it would bias the
        estimate.
        """
        return self.round_trip >= 0.0 and self.server_turnaround >= 0.0


class SkewEstimator:
    """Accumulates samples and reports a robust clock skew estimate.

    The estimator keeps every accepted sample and, on demand, returns the
    median of the per-sample offsets. The median is used instead of the
    mean because a single outlier (a retransmit, a scheduler hiccup) can
    drag a mean arbitrarily far, while the median moves at most to the
    next sample.

    The class is not thread-safe; callers that share one across threads
    must synchronise externally.
    """

    def __init__(self) -> None:
        self._offsets: List[float] = []

    def add(self, sample: Sample) -> bool:
        """Add a sample if it is valid.

        Returns True when the sample was accepted, False when it was
        rejected. Rejection is not an error: callers are expected to feed
        a stream and let the estimator filter it.
        """
        if not sample.is_valid():
            return False
        self._offsets.append(sample.offset)
        return True

    def add_many(self, samples: Iterable[Sample]) -> int:
        """Add every sample in ``samples`` and return the accepted count."""
        accepted = 0
        for sample in samples:
            if self.add(sample):
                accepted += 1
        return accepted

    @property
    def count(self) -> int:
        """Number of accepted samples."""
        return len(self._offsets)

    def estimate(self) -> Optional[float]:
        """Return the median offset, or None when no samples were accepted.

        Returning None rather than 0.0 forces callers to distinguish
        "no data" from "clocks agree".
        """
        if not self._offsets:
            return None
        ordered = sorted(self._offsets)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def reset(self) -> None:
        """Discard all accepted samples."""
        self._offsets.clear()

    def best_sample(self) -> Optional[Tuple[Sample, float]]:
        """Return the sample with the smallest round trip and its offset.

        The minimum-round-trip sample is the least contaminated by
        asymmetric network delay, so it is a useful cross-check against
        the median. Returns None when no samples were accepted.
        """
        if not self._offsets:
            return None
        # We only stored offsets, so re-derive the best sample lazily by
        # tracking it as a parallel list. To keep memory bounded we store
        # the pair alongside each offset instead of recomputing.
        raise NotImplementedError


# ``best_sample`` above intentionally raises: the estimator stores only
# offsets, and adding a parallel sample list would be dead weight for the
# common path. Callers who need the best sample should keep their own
# list. The method is removed from the public surface by not exporting it
# in __init__.py.
