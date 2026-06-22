#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Regression tests for calibrate.py, pinning the fixes from the 2026-06-19
# external review:
#   - propose_bands ignored its percentile inputs and returned fixed bands
#     -> split into canonical_bands() (fixed) + observed_bands(p) (data-driven)
#   - quantiles(n=100) default 'exclusive' extrapolated past the observed range
#     on small samples -> 'inclusive' + clamp + n==1 handling
# Stdlib only, Python 3.9+.

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CAL = os.path.join(_HERE, "..", "calibration", "calibrate.py")
_spec = importlib.util.spec_from_file_location("calibrate", _CAL)
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)


class Percentiles(unittest.TestCase):
    def test_clamped_to_observed_range(self):
        vals = [10, 20, 30, 40, 50]
        p = c.percentiles(vals)
        # the old 'exclusive' method would push p95 above the observed max (50)
        for n, val in p.items():
            self.assertGreaterEqual(val, min(vals), f"p{n} below observed min")
            self.assertLessEqual(val, max(vals), f"p{n} above observed max")

    def test_single_value(self):
        self.assertTrue(all(v == 42 for v in c.percentiles([42]).values()))

    def test_empty(self):
        self.assertTrue(all(v == 0 for v in c.percentiles([]).values()))


class Bands(unittest.TestCase):
    def test_observed_bands_actually_use_percentiles(self):
        low = {25: 1000, 50: 2000, 75: 3000, 90: 4000, 95: 5000}
        high = {25: 10000, 50: 20000, 75: 30000, 90: 40000, 95: 50000}
        self.assertNotEqual(c.observed_bands(low), c.observed_bands(high))
        self.assertIn("1K", dict(c.observed_bands(low))["XS"])

    def test_canonical_bands_are_fixed(self):
        b = c.canonical_bands()
        self.assertEqual(b, c.canonical_bands())
        self.assertEqual(set(b), {"context-band", "token-band"})
        self.assertEqual(len(b["token-band"]), 5)


if __name__ == "__main__":
    unittest.main()
