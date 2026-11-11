"""Clock skew estimation from timestamped request/response pairs.

This package exposes :class:`SkewEstimator` and :class:`Sample`.
"""

from .core import Sample, SkewEstimator

__all__ = ["Sample", "SkewEstimator"]
