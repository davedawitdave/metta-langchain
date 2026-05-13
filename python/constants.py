"""
constants.py
Shared lookup tables with no external dependencies.
Imported by market_feeder.py and the test suite.
"""

# Maps LLM sentiment words -> MeTTa SentimentSignal atom vocabulary.
# Keys are lowercase; values are the exact atoms in knowledge_base.metta.
SENTIMENT_NORM: dict[str, str] = {
    "bull":       "Bullish",  "bullish":    "Bullish",
    "bear":       "Bearish",  "bearish":    "Bearish",
    "neutral":    "Neutral",  "uncertain":  "Neutral",  "mixed":    "Neutral",
    "panic":      "Panic",    "fear":       "Panic",
    "crash":      "Crashing", "crashing":   "Crashing",
    "pump":       "Pumping",  "pumping":    "Pumping",  "rallying": "Pumping",
    "dump":       "Dumping",  "dumping":    "Dumping",
    "fomo":       "FOMOing",  "fomoing":    "FOMOing",
    "volatile":   "Volatile", "volatility": "Volatile",
}

# CoinPaprika REST API coin IDs.
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

# Mirror of knowledge_base.metta (AssetClass column).
ASSET_CLASS: dict[str, str] = {
    "BTC": "Layer1", "ETH": "Layer1", "SOL": "Layer1",
    "ADA": "Layer1", "AVAX": "Layer1",
    "MATIC": "Layer2", "ARB": "Layer2", "OP": "Layer2",
    "LINK": "DeFi", "UNI": "DeFi", "AAVE": "DeFi",
    "USDT": "Stablecoin", "USDC": "Stablecoin",
    "DOGE": "Meme", "SHIB": "Meme", "PEPE": "Meme",
}

# Mirror of knowledge_base.metta risk levels — for mock bridge in tests.
ASSET_RISK_LEVELS: dict[str, str] = {
    "BTC":  "Low",  "ETH":  "Low",  "SOL":  "Low",
    "ADA":  "Low",  "AVAX": "Low",
    "MATIC":"Medium","ARB":  "Medium","OP":   "Medium",
    "LINK": "High", "UNI":  "High", "AAVE": "High",
    "USDT": "Safe", "USDC": "Safe",
    "DOGE": "Critical","SHIB":"Critical","PEPE":"Critical",
}