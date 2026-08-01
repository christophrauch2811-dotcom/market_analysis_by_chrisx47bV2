"""
Minimale, vektorisierte Backtesting-Engine.

Zweck: Regime-/Breakout-/Indikator-Signale grob plausibilisieren, BEVOR man
RL-Training darauf aufbaut -- kein Ersatz fuer eine echte Order-Simulation
mit Slippage/Fees/Liquiditaet, sondern ein schneller Sanity-Check.

Unterstuetzt einfache regelbasierte Long/Short/Flat-Strategien als Funktion
des DataFrames (z.B. basierend auf regime_label oder Breakout-Flags).
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def backtest_signal(df: pd.DataFrame, signal: pd.Series, fee_pct: float = 0.05,
                     slippage_pct: float = 0.02) -> dict:
    """
    df: OHLCV-DataFrame.
    signal: pd.Series (gleicher Index wie df), Werte in {-1, 0, 1} =
        {short, flat, long} -- der Zustand, der ab der NAECHSTEN Kerze gehalten
        wird (kein Lookahead: Signal zu Zeitpunkt t bestimmt die Position in t+1).
    fee_pct / slippage_pct: pro Positionswechsel, in Prozentpunkten (z.B. 0.05 = 5 Bps).

    Gibt Kennzahlen zurueck: Gesamt-Return, Sharpe (annualisiert auf Basis der
    Kerzenanzahl/Jahr wird NICHT geschaetzt -- bewusst nur Rohwerte je Kerze),
    Max Drawdown, Win Rate, Anzahl Trades, Vergleich zu Buy&Hold.
    """
    assert len(df) == len(signal), "df und signal muessen dieselbe Laenge haben"

    position = signal.shift(1).fillna(0)  # kein Lookahead: heutiges Signal wirkt erst morgen
    market_return = df["close"].pct_change().fillna(0)
    strategy_return = position * market_return

    position_change = position.diff().abs().fillna(0)
    costs = position_change * (fee_pct + slippage_pct) / 100
    strategy_return_net = strategy_return - costs

    equity = (1 + strategy_return_net).cumprod()
    buy_hold_equity = (1 + market_return).cumprod()

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown = float(drawdown.min())

    trades = position.diff().fillna(0) != 0
    n_trades = int(trades.sum())

    # Trade-weise PnL fuer Win-Rate (grobe Naeherung ueber Haltephasen)
    trade_returns = []
    current_start = None
    current_side = 0
    for i, (ts, pos) in enumerate(position.items()):
        if pos != current_side:
            if current_side != 0 and current_start is not None:
                seg = strategy_return_net.loc[current_start:ts]
                trade_returns.append(float((1 + seg).prod() - 1))
            current_start = ts
            current_side = pos
    wins = sum(1 for r in trade_returns if r > 0)
    win_rate = wins / len(trade_returns) if trade_returns else None

    daily_std = strategy_return_net.std()
    sharpe_per_bar = (strategy_return_net.mean() / daily_std) if daily_std else 0.0

    return {
        "total_return_pct": round((equity.iloc[-1] - 1) * 100, 3),
        "buy_hold_return_pct": round((buy_hold_equity.iloc[-1] - 1) * 100, 3),
        "max_drawdown_pct": round(max_drawdown * 100, 3),
        "n_trades": n_trades,
        "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "sharpe_per_bar": round(float(sharpe_per_bar), 4),
        "bars": len(df),
        "warning": ("Vereinfachte Simulation ohne echte Order-Ausfuehrung/Liquiditaet -- "
                    "nur zur groben Plausibilisierung von Signalen, keine Performance-Zusage."),
    }


def backtest_regime_strategy(df: pd.DataFrame, regime_labels: pd.Series) -> dict:
    """
    Einfachste denkbare Regime-Strategie zum Sanity-Check von regime.py:
    long bei 'strong_trend_up'/'weak_trend_up', short bei den down-Varianten,
    sonst flat. regime_labels muss pro Kerze berechnet sein (z.B. rollierend
    mit regime.detect_regime() auf einem wachsenden Fenster -- rechenintensiv,
    daher hier als vom Aufrufer bereits berechnete Serie erwartet).
    """
    signal = regime_labels.map(
        lambda lbl: 1 if lbl in ("strong_trend_up", "weak_trend_up")
        else (-1 if lbl in ("strong_trend_down", "weak_trend_down") else 0)
    ).fillna(0)
    return backtest_signal(df, signal)


def backtest_breakout_strategy(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Klassischer Donchian-Breakout-Sanity-Check: long bei neuem N-Kerzen-Hoch,
    short bei neuem N-Kerzen-Tief, sonst Position halten."""
    hh = df["high"].rolling(lookback).max().shift(1)
    ll = df["low"].rolling(lookback).min().shift(1)
    signal = pd.Series(0, index=df.index)
    signal[df["close"] >= hh] = 1
    signal[df["close"] <= ll] = -1
    signal = signal.replace(0, np.nan).ffill().fillna(0)  # Position halten bis Gegensignal
    return backtest_signal(df, signal)
