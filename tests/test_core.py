import unittest

import numpy as np

from hurst_spike_risk.core import hurst_dfa, spike_flags


class CoreTests(unittest.TestCase):
    def test_hurst_is_finite_for_variable_series(self):
        rng = np.random.default_rng(7)
        value = hurst_dfa(rng.poisson(2.0, size=180))
        self.assertTrue(np.isfinite(value))

    def test_constant_series_is_not_estimated(self):
        self.assertTrue(np.isnan(hurst_dfa(np.ones(180))))

    def test_large_jump_is_flagged(self):
        values = [2, 1, 2, 2, 1, 2, 1, 2, 2, 1, 20]
        flags, _ = spike_flags(values, jump_ratio=3.0, min_spike_count=4)
        self.assertTrue(flags[-1])


if __name__ == "__main__":
    unittest.main()

