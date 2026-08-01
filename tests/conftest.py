"""Gemeinsame Fixtures fuer alle Tests. Kein Netzwerkzugriff -- alle Tests
laufen mit gemockten Antworten (Formate gegen die echte API-Doku verifiziert,
siehe README/CLAUDE.md), damit CI ohne Internetzugriff funktioniert.
"""
import pytest


class FakeResp:
    """Minimaler Ersatz fuer requests.Response."""
    def __init__(self, data, content=None):
        self._data = data
        self.content = content if content is not None else b""

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


@pytest.fixture
def synthetic_ohlcv():
    """Ein realistisches, aber zufaelliges OHLCV-DataFrame fuer Feature-/
    Regime-/Pattern-Tests, die keine echte Quelle brauchen."""
    import numpy as np
    import pandas as pd

    def _make(n=300, seed=42, drift=0.0, noise=1.0):
        rng = np.random.default_rng(seed)
        price = 2300 + np.cumsum(drift + rng.standard_normal(n) * noise)
        idx = pd.date_range("2024-01-01", periods=n, freq="h")
        open_ = price + rng.standard_normal(n) * 0.3
        close = price
        extra_hi = abs(rng.standard_normal(n) * 1.2)
        extra_lo = abs(rng.standard_normal(n) * 1.2)
        high = np.maximum(open_, close) + extra_hi
        low = np.minimum(open_, close) - extra_lo
        return pd.DataFrame({
            "open": open_, "high": high, "low": low, "close": close,
            "volume": rng.integers(500, 5000, n),
        }, index=idx)

    return _make
