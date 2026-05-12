"""
constants.py — Shared constants with no external dependencies.
Imported by both market_feeder.py and the test suite.
"""

# Maps Groq/LLM sentiment words → MeTTa SentimentSignal atom vocabulary
# These keys match what the LLM is instructed to return in SENTIMENT_HUMAN prompt.
SENTIMENT_NORM: dict[str, str] = {
    "bull":      "Bullish",  "bullish":  "Bullish",
    "bear":      "Bearish",  "bearish":  "Bearish",
    "neutral":   "Neutral",  "uncertain":"Neutral",  "mixed": "Neutral",
    "panic":     "Panic",    "fear":     "Panic",
    "crash":     "Crashing", "crashing": "Crashing",
    "pump":      "Pumping",  "pumping":  "Pumping",  "rallying": "Pumping",
    "dump":      "Dumping",  "dumping":  "Dumping",
    "fomo":      "FOMOing",  "fomoing":  "FOMOing",
    "volatile":  "Volatile", "volatility":"Volatile",
}

# CoinPaprika coin IDs for the REST API
COIN_IDS: dict[str, str] = {
    "BTC":  "btc-bitcoin",
    "ETH":  "eth-ethereum",
    "SOL":  "sol-solana",
    "ADA":  "ada-cardano",
    "AVAX": "avax-avalanche-2",
    "MATIC":"matic-polygon",
    "DOGE": "doge-dogecoin",
    "LINK": "link-chainlink",
    "USDT": "usdt-tether",
    "USDC": "usdc-usd-coin",
    "ARB":  "arb-arbitrum",
    "PEPE": "pepe-pepe",
    "SHIB": "shib-shiba-inu",
}

# Asset → risk level (mirrors knowledge_base.metta — kept in sync manually)
ASSET_RISK_LEVELS: dict[str, str] = {
    "BTC": "Low",  "ETH": "Low",  "SOL": "Low",  "ADA": "Low",  "AVAX": "Low",
    "MATIC": "Medium", "ARB": "Medium", "OP": "Medium",
    "LINK": "High", "UNI": "High", "AAVE": "High",
    "USDT": "Safe", "USDC": "Safe",
    "DOGE": "Critical", "SHIB": "Critical", "PEPE": "Critical",
}
