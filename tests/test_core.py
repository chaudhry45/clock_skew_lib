import math
import unittest

from clock_skew_lib import Sample, SkewEstimator


class SampleTest(unittest.TestCase):
    def test_round_trip_and_turnaround(self) -> None:
        s = Sample(client_send=0.0, server_recv=1.0, server_send=1.5, client_recv=2.0)
        self.assertAlmostEqual(s.round_trip, 2.0)
        self.assertAlmostEqual(s.server_turnaround, 0.5)

    def test_offset_symmetric_delay(self) -> None:
        # Client clock 0, server clock 10. One-way delay 1s.
        # server_recv = 0 + 1 + 10 = 11, server_send = 11 + 0.5 = 11.5,
        # client_recv = 11.5 + 1 - 10 = 2.5.
        s = Sample(client_send=0.0, server_recv=11.0, server_send=11.5, client_recv=2.5)
        self.assertAlmostEqual(s.offset, 10.0)

    def test_is_valid_rejects_negative_round_trip(self) -> None:
        s = Sample(client_send=5.0, server_recv=6.0, server_send=6.0, client_recv=4.0)
        self.assertFalse(s.is_valid())

    def test_is_valid_rejects_negative_turnaround(self) -> None:
        s = Sample(client_send=0.0, server_recv=2.0, server_send=1.0, client_recv=3.0)
        self.assertFalse(s.is_valid())

    def test_is_valid_accepts_zero_durations(self) -> None:
        s = Sample(client_send=1.0, server_recv=1.0, server_send=1.0, client_recv=1.0)
        self.assertTrue(s.is_valid())


class SkewEstimatorTest(unittest.TestCase):
    def test_empty_estimate_is_none(self) -> None:
        est = SkewEstimator()
        self.assertIsNone(est.estimate())
        self.assertEqual(est.count, 0)

    def test_add_rejects_invalid(self) -> None:
        est = SkewEstimator()
        bad = Sample(client_send=0.0, server_recv=1.0, server_send=0.5, client_recv=2.0)
        self.assertFalse(est.add(bad))
        self.assertEqual(est.count, 0)

    def test_add_accepts_valid(self) -> None:
        est = SkewEstimator()
        good = Sample(client_send=0.0, server_recv=11.0, server_send=11.5, client_recv=2.5)
        self.assertTrue(est.add(good))
        self.assertEqual(est.count, 1)
        self.assertAlmostEqual(est.estimate(), 10.0)

    def test_median_odd_count(self) -> None:
        est = SkewEstimator()
        # Offsets: 1, 5, 2 -> median 2.
        for offset in (1.0, 5.0, 2.0):
            est.add(self._sample_with_offset(offset))
        self.assertAlmostEqual(est.estimate(), 2.0)

    def test_median_even_count(self) -> None:
        est = SkewEstimator()
        # Offsets: 1, 2, 3, 4 -> median 2.5.
        for offset in (1.0, 2.0, 3.0, 4.0):
            est.add(self._sample_with_offset(offset))
        self.assertAlmostEqual(est.estimate(), 2.5)

    def test_add_many_returns_accepted_count(self) -> None:
        est = SkewEstimator()
        samples = [
            self._sample_with_offset(3.0),
            Sample(client_send=0.0, server_recv=1.0, server_send=0.5, client_recv=2.0),
            self._sample_with_offset(7.0),
        ]
        self.assertEqual(est.add_many(samples), 2)
        self.assertEqual(est.count, 2)

    def test_reset_clears_state(self) -> None:
        est = SkewEstimator()
        est.add(self._sample_with_offset(4.0))
        est.reset()
        self.assertEqual(est.count, 0)
        self.assertIsNone(est.estimate())

    def test_median_is_robust_to_outlier(self) -> None:
        est = SkewEstimator()
        for offset in (2.0, 2.1, 2.2, 2.3, 1000.0):
            est.add(self._sample_with_offset(offset))
        self.assertAlmostEqual(est.estimate(), 2.2)

    @staticmethod
    def _sample_with_offset(offset: float) -> Sample:
        """Build a sample whose computed offset equals ``offset``.

        We fix client_send=0, server_recv=offset, server_send=offset,
        client_recv=0. Then round_trip=0, turnaround=0, and
        offset = ((offset - 0) - (0 - offset)) / 2 = offset.
        """
        return Sample(
            client_send=0.0,
            server_recv=offset,
            server_send=offset,
            client_recv=0.0,
        )


if __name__ == "__main__":
    unittest.main()
