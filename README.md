# clock_skew_lib

Estimates the constant offset between a client clock and a remote server clock from timestamped request/response pairs.

```python
from clock_skew_lib import Sample, SkewEstimator

est = SkewEstimator()

# client_send, server_recv, server_send, client_recv (seconds, each in its own clock)
est.add(Sample(client_send=0.0, server_recv=11.0, server_send=11.5, client_recv=2.5))
est.add(Sample(client_send=0.0, server_recv=12.0, server_send=12.5, client_recv=2.5))

print(est.count)        # 2
print(est.estimate())   # 10.0
```

## Why this exists

The problem is measuring clock skew without a trusted time source. A single round trip gives an offset estimate only if you assume the network delay is the same in both directions; when that assumption is wrong, the estimate is wrong by half the asymmetry. This library makes one deliberate trade-off: it assumes symmetric one-way delay and reports the median of per-sample offsets rather than the mean. The median costs a sort on every call to `estimate()` but is robust to the retransmits and scheduler hiccups that plague real networks, where a single outlier can move a mean arbitrarily far.

## The edge you will hit

`estimate()` returns `None` when no valid samples have been added. That is not an error condition — it is the honest answer to "what is the skew?" with no data. A caller that expects a float must handle the `None` branch. Samples with a negative round trip or negative server turnaround are rejected by `add()`, which returns `False`; this happens whenever a clock steps during the measurement, and silently clamping those samples would bias the result.

## Public API

- `Sample(client_send, server_recv, server_send, client_recv)` — one round trip. Exposes `.round_trip`, `.server_turnaround`, `.offset`, and `.is_valid()`.
- `SkewEstimator()` — `.add(sample) -> bool`, `.add_many(samples) -> int`, `.count`, `.estimate() -> float | None`, `.reset()`.
