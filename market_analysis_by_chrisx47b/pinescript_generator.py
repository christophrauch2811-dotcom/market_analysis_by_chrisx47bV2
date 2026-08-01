"""
Pine-Script-v6-Code-Generator.

WICHTIGER VORBEHALT: Der generierte Code wurde NICHT compiliert -- es gibt
keinen Pine-Script-Compiler in dieser Umgebung. Die Syntax folgt den
verifizierten v6-Konventionen (//@version=6, verpflichtende ta.*/request.*-
Namespaces, input.int()/input.float() statt generischem input(), if-Bloecke
statt des in v6 entfernten when=-Parameters in strategy.entry()). Vor
produktivem Einsatz IMMER im TradingView Pine-Editor pruefen/compilieren.

Zwei Einstiegspunkte:
  - generate_pine_indicator(): reine Anzeige-Indikatoren (kein Trading)
  - generate_pine_strategy(): mit strategy.entry()/strategy.exit(),
    lauffaehig in TradingViews eigenem Strategy Tester -- dieser Connector
    backtestet bewusst nicht selbst (siehe fruehere Entscheidung), delegiert
    das hier stattdessen an TradingViews eigene Infrastruktur.
"""

from __future__ import annotations

SUPPORTED_INDICATOR_COMPONENTS = (
    "sma", "ema", "rsi", "macd", "bollinger", "atr", "supertrend",
    "vwap", "adx", "stochastic",
)
SUPPORTED_ENTRY_METHODS = ("ema_cross", "rsi_reversion", "supertrend_flip", "breakout_donchian")
SUPPORTED_EXIT_METHODS = ("percent", "atr")

# Komponenten, die typischerweise AUF dem Preischart liegen (force_overlay=true),
# im Gegensatz zu Oszillatoren, die in einem eigenen Panel unten laufen.
_OVERLAY_COMPONENTS = {"sma", "ema", "bollinger", "supertrend", "vwap"}


def _indicator_block(component: str, idx: int) -> tuple[list[str], list[str]]:
    """Gibt (Berechnungszeilen, Plot-Zeilen) fuer eine Komponente zurueck."""
    calc, plots = [], []
    force_ov = "force_overlay=true" if component in _OVERLAY_COMPONENTS else ""

    if component == "sma":
        calc.append(f'smaLen{idx} = input.int(20, title="SMA Length {idx}")')
        calc.append(f'smaVal{idx} = ta.sma(close, smaLen{idx})')
        plots.append(f'plot(smaVal{idx}, title="SMA {idx}", color=color.blue{", " + force_ov if force_ov else ""})')
    elif component == "ema":
        calc.append(f'emaLen{idx} = input.int(20, title="EMA Length {idx}")')
        calc.append(f'emaVal{idx} = ta.ema(close, emaLen{idx})')
        plots.append(f'plot(emaVal{idx}, title="EMA {idx}", color=color.orange{", " + force_ov if force_ov else ""})')
    elif component == "rsi":
        calc.append(f'rsiLen{idx} = input.int(14, title="RSI Length {idx}")')
        calc.append(f'rsiVal{idx} = ta.rsi(close, rsiLen{idx})')
        plots.append(f'plot(rsiVal{idx}, title="RSI {idx}", color=color.purple)')
        plots.append(f'hline(70, title="RSI Overbought {idx}", color=color.red)')
        plots.append(f'hline(30, title="RSI Oversold {idx}", color=color.green)')
    elif component == "macd":
        calc.append(f'[macdLine{idx}, macdSignal{idx}, macdHist{idx}] = ta.macd(close, 12, 26, 9)')
        plots.append(f'plot(macdLine{idx}, title="MACD {idx}", color=color.blue)')
        plots.append(f'plot(macdSignal{idx}, title="MACD Signal {idx}", color=color.orange)')
        plots.append(f'plot(macdHist{idx}, title="MACD Hist {idx}", color=color.gray, style=plot.style_columns)')
    elif component == "bollinger":
        calc.append(f'bbLen{idx} = input.int(20, title="Bollinger Length {idx}")')
        calc.append(f'bbMult{idx} = input.float(2.0, title="Bollinger Mult {idx}")')
        calc.append(f'bbBasis{idx} = ta.sma(close, bbLen{idx})')
        calc.append(f'bbDev{idx} = bbMult{idx} * ta.stdev(close, bbLen{idx})')
        calc.append(f'bbUpper{idx} = bbBasis{idx} + bbDev{idx}')
        calc.append(f'bbLower{idx} = bbBasis{idx} - bbDev{idx}')
        plots.append(f'plot(bbBasis{idx}, title="BB Basis {idx}", color=color.gray{", " + force_ov if force_ov else ""})')
        plots.append(f'plot(bbUpper{idx}, title="BB Upper {idx}", color=color.teal{", " + force_ov if force_ov else ""})')
        plots.append(f'plot(bbLower{idx}, title="BB Lower {idx}", color=color.teal{", " + force_ov if force_ov else ""})')
    elif component == "atr":
        calc.append(f'atrLen{idx} = input.int(14, title="ATR Length {idx}")')
        calc.append(f'atrVal{idx} = ta.atr(atrLen{idx})')
        plots.append(f'plot(atrVal{idx}, title="ATR {idx}", color=color.red)')
    elif component == "supertrend":
        calc.append(f'stFactor{idx} = input.float(3.0, title="Supertrend Factor {idx}")')
        calc.append(f'stAtrLen{idx} = input.int(10, title="Supertrend ATR Length {idx}")')
        calc.append(f'[stVal{idx}, stDir{idx}] = ta.supertrend(stFactor{idx}, stAtrLen{idx})')
        plots.append(f'plot(stVal{idx}, title="Supertrend {idx}", '
                      f'color = stDir{idx} < 0 ? color.green : color.red{", " + force_ov if force_ov else ""})')
    elif component == "vwap":
        calc.append(f'vwapVal{idx} = ta.vwap(close)')
        plots.append(f'plot(vwapVal{idx}, title="VWAP {idx}", color=color.yellow{", " + force_ov if force_ov else ""})')
    elif component == "adx":
        calc.append(f'adxLen{idx} = input.int(14, title="ADX Length {idx}")')
        calc.append(f'adxSmooth{idx} = input.int(14, title="ADX Smoothing {idx}")')
        calc.append(f'[diPlus{idx}, diMinus{idx}, adxVal{idx}] = ta.dmi(adxLen{idx}, adxSmooth{idx})')
        plots.append(f'plot(adxVal{idx}, title="ADX {idx}", color=color.black)')
        plots.append(f'plot(diPlus{idx}, title="DI+ {idx}", color=color.green)')
        plots.append(f'plot(diMinus{idx}, title="DI- {idx}", color=color.red)')
    elif component == "stochastic":
        calc.append(f'stochLen{idx} = input.int(14, title="Stochastic Length {idx}")')
        calc.append(f'stochK{idx} = ta.sma(ta.stoch(close, high, low, stochLen{idx}), 3)')
        calc.append(f'stochD{idx} = ta.sma(stochK{idx}, 3)')
        plots.append(f'plot(stochK{idx}, title="Stoch %K {idx}", color=color.blue)')
        plots.append(f'plot(stochD{idx}, title="Stoch %D {idx}", color=color.orange)')
    else:
        raise ValueError(f"Unbekannte Komponente '{component}'. Erlaubt: {SUPPORTED_INDICATOR_COMPONENTS}")

    return calc, plots


def generate_pine_indicator(name: str, components: list[str], overlay: bool = False) -> str:
    """
    Baut ein Pine-Script-v6-Indikator-Skript, das die gewuenschten Komponenten
    kombiniert (jede Komponente bekommt eigene, durchnummerierte Inputs, damit
    mehrere gleichzeitig -- z.B. zwei EMAs -- nicht kollidieren).

    components: Liste aus SUPPORTED_INDICATOR_COMPONENTS, z.B. ['ema','ema','rsi'].
    overlay: True = Standard-Platzierung ist auf dem Preischart (fuer reine
        MA/Bollinger/Supertrend/VWAP-Kombinationen sinnvoll). False (Default)
        = eigenes Panel, mit force_overlay=true fuer die Preischart-Komponenten.
    """
    if not components:
        raise ValueError("Mindestens eine Komponente angeben.")

    lines = [f'//@version=6', f'indicator("{name}", overlay={"true" if overlay else "false"})', ""]
    all_calc, all_plots = [], []
    for i, comp in enumerate(components, start=1):
        calc, plots = _indicator_block(comp.lower(), i)
        all_calc.extend(calc)
        all_plots.extend(plots)

    lines.extend(all_calc)
    lines.append("")
    lines.extend(all_plots)
    return "\n".join(lines)


def _entry_block(method: str) -> tuple[list[str], str, str]:
    """Gibt (Berechnungszeilen, longCondition-Ausdruck, shortCondition-Ausdruck) zurueck."""
    if method == "ema_cross":
        calc = [
            'fastLen = input.int(9, title="Fast EMA Length")',
            'slowLen = input.int(21, title="Slow EMA Length")',
            'fastEma = ta.ema(close, fastLen)',
            'slowEma = ta.ema(close, slowLen)',
        ]
        return calc, "ta.crossover(fastEma, slowEma)", "ta.crossunder(fastEma, slowEma)"

    if method == "rsi_reversion":
        calc = [
            'rsiLen = input.int(14, title="RSI Length")',
            'rsiOversold = input.int(30, title="RSI Oversold Level")',
            'rsiOverbought = input.int(70, title="RSI Overbought Level")',
            'rsiVal = ta.rsi(close, rsiLen)',
        ]
        return calc, "ta.crossover(rsiVal, rsiOversold)", "ta.crossunder(rsiVal, rsiOverbought)"

    if method == "supertrend_flip":
        calc = [
            'stFactor = input.float(3.0, title="Supertrend Factor")',
            'stAtrLen = input.int(10, title="Supertrend ATR Length")',
            '[stVal, stDir] = ta.supertrend(stFactor, stAtrLen)',
            '// Konvention (TradingView-Standard-Supertrend): direction < 0 = Aufwaertstrend, > 0 = Abwaertstrend',
            '// Bitte im Editor visuell verifizieren, falls sich die Konvention je Version unterscheidet.',
        ]
        return calc, "ta.change(stDir) < 0", "ta.change(stDir) > 0"

    if method == "breakout_donchian":
        calc = [
            'donchianLen = input.int(20, title="Donchian Length")',
            'donchianHigh = ta.highest(high, donchianLen)[1]',
            'donchianLow = ta.lowest(low, donchianLen)[1]',
        ]
        return calc, "ta.crossover(close, donchianHigh)", "ta.crossunder(close, donchianLow)"

    raise ValueError(f"Unbekannte Entry-Methode '{method}'. Erlaubt: {SUPPORTED_ENTRY_METHODS}")


def generate_pine_strategy(name: str, entry_method: str = "ema_cross",
                            direction: str = "both", exit_method: str = "percent",
                            stop_loss_pct: float = 2.0, take_profit_pct: float = 4.0,
                            atr_stop_mult: float = 2.0, atr_take_profit_mult: float = 4.0,
                            atr_length: int = 14) -> str:
    """
    Baut ein Pine-Script-v6-Strategie-Skript mit Entry-Logik + Stop-Loss/
    Take-Profit, lauffaehig in TradingViews Strategy Tester. Nutzt bewusst
    if-Bloecke statt des in v6 entfernten when=-Parameters.

    entry_method: 'ema_cross', 'rsi_reversion', 'supertrend_flip', 'breakout_donchian'
    direction: 'long_only', 'short_only', 'both'
    exit_method: 'percent' (stop_loss_pct/take_profit_pct vom Entry-Preis)
                 oder 'atr' (atr_stop_mult/atr_take_profit_mult * ATR)
    """
    if direction not in ("long_only", "short_only", "both"):
        raise ValueError("direction muss 'long_only', 'short_only' oder 'both' sein.")
    if exit_method not in SUPPORTED_EXIT_METHODS:
        raise ValueError(f"exit_method muss einer von {SUPPORTED_EXIT_METHODS} sein.")

    entry_calc, long_cond, short_cond = _entry_block(entry_method)

    lines = [
        "//@version=6",
        f'strategy("{name}", overlay=true, margin_long=100, margin_short=100, '
        f'default_qty_type=strategy.percent_of_equity, default_qty_value=100)',
        "",
    ]
    lines.extend(entry_calc)
    lines.append("")

    if exit_method == "atr":
        lines.append(f'atrVal = ta.atr({atr_length})')
        lines.append("")

    do_long = direction in ("long_only", "both")
    do_short = direction in ("short_only", "both")

    if do_long:
        lines.append(f'longCondition = {long_cond}')
        lines.append("if longCondition")
        lines.append('    strategy.entry("Long", strategy.long)')
        lines.append("")

    if do_short:
        lines.append(f'shortCondition = {short_cond}')
        lines.append("if shortCondition")
        lines.append('    strategy.entry("Short", strategy.short)')
        lines.append("")

    if exit_method == "percent":
        if do_long:
            lines.append(f'longStop = strategy.position_avg_price * (1 - {stop_loss_pct} / 100)')
            lines.append(f'longTarget = strategy.position_avg_price * (1 + {take_profit_pct} / 100)')
            lines.append('if strategy.position_size > 0')
            lines.append('    strategy.exit("Exit Long", from_entry="Long", stop=longStop, limit=longTarget)')
            lines.append("")
        if do_short:
            lines.append(f'shortStop = strategy.position_avg_price * (1 + {stop_loss_pct} / 100)')
            lines.append(f'shortTarget = strategy.position_avg_price * (1 - {take_profit_pct} / 100)')
            lines.append('if strategy.position_size < 0')
            lines.append('    strategy.exit("Exit Short", from_entry="Short", stop=shortStop, limit=shortTarget)')
    else:  # atr
        if do_long:
            lines.append(f'longStop = strategy.position_avg_price - atrVal * {atr_stop_mult}')
            lines.append(f'longTarget = strategy.position_avg_price + atrVal * {atr_take_profit_mult}')
            lines.append('if strategy.position_size > 0')
            lines.append('    strategy.exit("Exit Long", from_entry="Long", stop=longStop, limit=longTarget)')
            lines.append("")
        if do_short:
            lines.append(f'shortStop = strategy.position_avg_price + atrVal * {atr_stop_mult}')
            lines.append(f'shortTarget = strategy.position_avg_price - atrVal * {atr_take_profit_mult}')
            lines.append('if strategy.position_size < 0')
            lines.append('    strategy.exit("Exit Short", from_entry="Short", stop=shortStop, limit=shortTarget)')

    return "\n".join(lines)
