"""
Symbol-Mapping zwischen einem kanonischen Format ('BTC/USDT') und dem
jeweils quellenspezifischen Symbol-Format.

BEWUSST KEIN vollstaendiger universeller Symbol-Parser -- jede Boerse hat
Eigenheiten (Kraken: XBT statt BTC, Bitfinex: teils UST statt USDT bei
USDT-Paaren, CoinGecko: Coin-IDs statt Trading-Pairs). Diese Zuordnungen sind
kuratiert fuer gaengige Coins/Quotes, NICHT gegen jede einzelne Kombination
live verifiziert -- bei ungewoehnlichen Paaren im Zweifel `to_source_symbol()`
testen oder das Symbol direkt (ohne Mapping) angeben.
"""

from __future__ import annotations

# Kraken nutzt fuer manche Coins eigene Kuerzel statt des ueblichen Tickers.
_KRAKEN_BASE_OVERRIDES = {"BTC": "XBT", "DOGE": "XDG"}

# Bitfinex nannte USDT-Paare historisch teils "UST" statt "USDT" im Symbol.
_BITFINEX_QUOTE_OVERRIDES = {"USDT": "UST"}

# CoinGecko braucht eine Coin-ID statt eines Trading-Pairs -- nur fuer die
# gaengigsten Coins kuratiert, alles andere muss der Aufrufer selbst als
# CoinGecko-ID angeben (siehe /coins/list auf der CoinGecko-Seite).
_COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
    "ADA": "cardano", "DOGE": "dogecoin", "BNB": "binancecoin",
    "LTC": "litecoin", "DOT": "polkadot", "AVAX": "avalanche-2",
    "LINK": "chainlink", "MATIC": "polygon-ecosystem-token", "TRX": "tron",
}

# Bekannte Quote-Waehrungen, um zusammengeschriebene Symbole (BTCUSDT) wieder
# in Base/Quote zu trennen -- laengste zuerst pruefen (USDT vor USD, USDC vor USD).
_KNOWN_QUOTES = ["USDT", "USDC", "BUSD", "USD", "EUR", "GBP", "BTC", "ETH"]


def to_source_symbol(canonical: str, source: str) -> str:
    """canonical z.B. 'BTC/USDT' -> Symbol im Format der jeweiligen Quelle."""
    if "/" not in canonical:
        raise ValueError(f"canonical muss im Format 'BASE/QUOTE' sein, z.B. 'BTC/USDT' (erhalten: '{canonical}')")
    base, _, quote = canonical.partition("/")
    base, quote = base.upper(), quote.upper()

    if source == "crypto":
        return f"{base}_{quote}"
    if source in ("binance", "bybit"):
        return f"{base}{quote}"
    if source == "kucoin":
        return f"{base}-{quote}"
    if source == "kraken":
        k_base = _KRAKEN_BASE_OVERRIDES.get(base, base)
        return f"{k_base}{quote}"
    if source == "bitfinex":
        bf_quote = _BITFINEX_QUOTE_OVERRIDES.get(quote, quote)
        return f"t{base}{bf_quote}"
    if source == "coingecko":
        coin_id = _COINGECKO_IDS.get(base)
        if not coin_id:
            raise ValueError(
                f"Keine CoinGecko-ID fuer '{base}' kuratiert -- bitte die Coin-ID "
                f"direkt angeben (siehe coingecko.com -> Coin-Seite -> 'API ID')."
            )
        return coin_id
    if source == "yahoo":
        # Yahoo hat keine USDT-Paare -- naechstbeste Naeherung ist USD.
        yahoo_quote = "USD" if quote == "USDT" else quote
        return f"{base}-{yahoo_quote}"
    if source == "mt5":
        # Broker-abhaengig -- grobe Annahme ohne Trennzeichen, oft aber abweichend
        # (z.B. Suffixe wie 'EURUSD.a'). Im Zweifel MT5-Symbolliste pruefen.
        return f"{base}{quote}"

    raise ValueError(f"Unbekannte Quelle '{source}' fuer Symbol-Mapping.")


def normalize_symbol(symbol: str, source: str) -> str:
    """Kehrt to_source_symbol() um: quellenspezifisches Symbol -> 'BASE/QUOTE'.
    Best-effort -- bei ungewoehnlichen Symbolen kann das Splitten in Base/Quote
    fehlschlagen (wirft ValueError, statt falsch zu raten).
    """
    symbol = symbol.strip()

    if source == "crypto":
        if "_" not in symbol:
            raise ValueError(f"Erwarte 'BASE_QUOTE' fuer crypto, erhalten: '{symbol}'")
        base, quote = symbol.split("_", 1)
        return f"{base.upper()}/{quote.upper()}"

    if source == "kucoin":
        if "-" not in symbol:
            raise ValueError(f"Erwarte 'BASE-QUOTE' fuer kucoin, erhalten: '{symbol}'")
        base, quote = symbol.split("-", 1)
        return f"{base.upper()}/{quote.upper()}"

    if source == "yahoo":
        if "-" in symbol:
            base, quote = symbol.split("-", 1)
            return f"{base.upper()}/{quote.upper()}"
        raise ValueError(f"Kann '{symbol}' (yahoo) nicht in Base/Quote trennen.")

    if source == "bitfinex":
        sym = symbol[1:] if symbol.startswith(("t", "f")) else symbol
        for q in _KNOWN_QUOTES:
            bf_q = _BITFINEX_QUOTE_OVERRIDES.get(q, q)
            if sym.endswith(bf_q) and len(sym) > len(bf_q):
                return f"{sym[:-len(bf_q)].upper()}/{q.upper()}"
        raise ValueError(f"Konnte Quote-Waehrung in '{symbol}' (bitfinex) nicht erkennen.")

    if source == "kraken":
        reverse_base = {v: k for k, v in _KRAKEN_BASE_OVERRIDES.items()}
        for q in _KNOWN_QUOTES:
            if symbol.upper().endswith(q) and len(symbol) > len(q):
                base_part = symbol.upper()[: -len(q)]
                base_part = reverse_base.get(base_part, base_part)
                return f"{base_part}/{q}"
        raise ValueError(f"Konnte Quote-Waehrung in '{symbol}' (kraken) nicht erkennen.")

    if source in ("binance", "bybit", "mt5"):
        for q in _KNOWN_QUOTES:
            if symbol.upper().endswith(q) and len(symbol) > len(q):
                return f"{symbol.upper()[:-len(q)]}/{q}"
        raise ValueError(f"Konnte Quote-Waehrung in '{symbol}' ({source}) nicht erkennen.")

    if source == "coingecko":
        reverse_ids = {v: k for k, v in _COINGECKO_IDS.items()}
        base = reverse_ids.get(symbol.lower())
        if not base:
            raise ValueError(f"Keine bekannte Base-Waehrung fuer CoinGecko-ID '{symbol}'.")
        return f"{base}/USD"  # CoinGecko-Preise sind meist gegen USD/eine vs_currency, keine feste Quote im Symbol

    raise ValueError(f"Unbekannte Quelle '{source}' fuer Symbol-Normalisierung.")


def map_to_sources(canonical: str, sources: list[str]) -> list[dict]:
    """Baut eine fallback_sources-kompatible Liste [{'source':..,'symbol':..}].
    Quellen, fuer die kein Mapping moeglich ist (z.B. fehlende CoinGecko-ID),
    werden ausgelassen statt die ganze Liste scheitern zu lassen."""
    result = []
    for source in sources:
        try:
            result.append({"source": source, "symbol": to_source_symbol(canonical, source)})
        except ValueError:
            continue
    return result
