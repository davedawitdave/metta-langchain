"""
market_feeder.py
Fetches live market data and writes market_state.metta.

Sources:
  CoinPaprika REST API  : price, 24h change, 24h volume  (free, no key)
  Groq llama-3.1-8b     : news sentiment classification

Output: calls bridge.update_market_state(atoms) which overwrites
market_state.metta.  PeTTa re-reads from disk on every query.
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from constants import SENTIMENT_NORM, COIN_IDS, ASSET_RISK_LEVELS, ASSET_CLASS

COINPAPRIKA_BASE = "https://api.coinpaprika.com/v1"


class MarketFeeder:

    def __init__(self, bridge, groq_api_key: Optional[str] = None):
        self.bridge   = bridge
        self._key     = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "CryptoACO/3.0"})
        self._llm     = None   # lazy init

    def poll(self, symbols: list[str] = None, once: bool = True) -> None:
        """Fetch and write atoms. Set once=False for a continuous loop."""
        targets = symbols or list(COIN_IDS.keys())
        while True:
            try:
                self._update(targets)
            except Exception as e:
                print(f"[MarketFeeder] error: {e}")
            if once:
                break
            time.sleep(60)

    # --- exposure atoms (mirrors knowledge_base + holdings) ----

    @staticmethod
    def _current_exposure_atoms(holdings: dict[str, float]) -> list[str]:
        """Emit (CurrentExposure <BaseRisk tier> <sum pct>) for each tier."""
        totals = {t: 0.0 for t in ("Critical", "High", "Medium", "Low", "Safe")}
        for sym, pct in holdings.items():
            tier = ASSET_RISK_LEVELS.get(sym, "Critical")
            totals[tier] += float(pct)
        lines = [f"(CurrentExposure {tier} {totals[tier]:.4f})" for tier in totals]
        return lines + [""]

    @staticmethod
    def _asset_risk_atoms(holdings: dict[str, float]) -> list[str]:
        """Emit (AssetRisk <sym> <class> <tier>) for get-risk-profile / portfolio."""
        lines = ["; Per-holding risk rows (get-risk-profile)", ""]
        for sym, pct in holdings.items():
            if pct <= 0:
                continue
            cls = ASSET_CLASS.get(sym, "Unverified")
            tier = ASSET_RISK_LEVELS.get(sym, "Critical")
            lines.append(f"(AssetRisk {sym} {cls} {tier})")
        lines.append("")
        return lines

    # --- internal update -------------------------------------

    def _update(self, symbols: list[str]) -> None:
        prices     = self._fetch_prices(symbols)
        sentiments = self._fetch_sentiments(symbols)
        state      = self._global_state(prices)

        atoms = [
            f"; AUTO-GENERATED {datetime.now(timezone.utc).isoformat()}", "",
            f"(GlobalMarketState {state})", "",
        ]

        for sym in symbols:
            p = prices.get(sym)
            if not p:
                continue
            vol   = abs(p.get("pct_24h", 0.0))
            trend = "Bullish" if p.get("pct_24h", 0) > 0 else "Bearish"
            sent  = sentiments.get(sym, "Neutral")
            vol24 = int(p.get("volume_24h", 0))
            atoms += [
                f"(AssetPrice      {sym}  {p['price']:.4f})",
                f"(AssetVolatility {sym}  {vol:.2f})",
                f"(AssetSentiment  {sym}  {sent})",
                f"(AssetTrend      {sym}  {trend})",
                f"(AssetVolume24h  {sym}  {vol24})",
                "",
            ]

        holdings = {
            "BTC": 20.0, "ETH": 15.0, "LINK": 3.0, "USDC": 30.0,
        }
        atoms += [
            "; Portfolio state — edit manually",
            "(PortfolioBalance 10000.00)",
            "(HoldingPct BTC   20.0)",
            "(HoldingPct ETH   15.0)",
            "(HoldingPct LINK   3.0)",
            "(HoldingPct USDC  30.0)",
            "",
            "; Tier exposure sums (must match risk_hierarchy sum-exposure-by-level)",
        ]
        atoms += self._current_exposure_atoms(holdings)
        atoms += self._asset_risk_atoms(holdings)
        atoms += [
            "(DailyPnL 1.5)",
            "(TradesThisHour 2)",
        ]

        self.bridge.update_market_state(atoms)
        print(f"[MarketFeeder] updated — GlobalMarketState: {state}")

    # --- CoinPaprika -----------------------------------------

    def _fetch_prices(self, symbols: list[str]) -> dict:
        results = {}
        for sym in symbols:
            cid = COIN_IDS.get(sym)
            if not cid:
                continue
            try:
                r   = self._session.get(f"{COINPAPRIKA_BASE}/tickers/{cid}", timeout=8)
                r.raise_for_status()
                usd = r.json().get("quotes", {}).get("USD", {})
                results[sym] = {
                    "price":     float(usd.get("price", 0)),
                    "pct_24h":   float(usd.get("percent_change_24h", 0)),
                    "volume_24h":float(usd.get("volume_24h", 0)),
                }
            except Exception as e:
                print(f"[CoinPaprika] {sym}: {e}")
        return results

    # --- Groq sentiment (LangChain) --------------------------

    def _fetch_sentiments(self, symbols: list[str]) -> dict[str, str]:
        if not self._key:
            return {s: "Neutral" for s in symbols}
        if self._llm is None:
            self._llm = ChatGroq(model="llama-3.1-8b-instant",
                                 api_key=self._key, temperature=0.1)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SENTIMENT_SYSTEM),
            ("human",  SENTIMENT_HUMAN),
        ])
        chain = prompt | self._llm | StrOutputParser()
        try:
            text = chain.invoke({"coins": ", ".join(symbols)})
            return self._parse_sentiments(text, symbols)
        except Exception as e:
            print(f"[Groq Sentiment] {e}")
            return {s: "Neutral" for s in symbols}

    def _parse_sentiments(self, text: str, symbols: list[str]) -> dict:
        results = {s: "Neutral" for s in symbols}
        try:
            clean = re.sub(r"```json\s*|```", "", text).strip()
            data  = json.loads(clean)
            for sym in symbols:
                raw = str(data.get(sym, "neutral")).lower()
                results[sym] = SENTIMENT_NORM.get(raw, "Neutral")
            return results
        except Exception:
            pass
        for sym in symbols:
            m = re.search(rf'{sym}[:\s]+(\w+)', text, re.IGNORECASE)
            if m:
                results[sym] = SENTIMENT_NORM.get(m.group(1).lower(), "Neutral")
        return results

    # --- global state computation ----------------------------

    def _global_state(self, prices: dict) -> str:
        if not prices:
            return "Normal"
        avg = sum(abs(p.get("pct_24h", 0)) for p in prices.values()) / len(prices)
        if avg >= 20:
            return "Panic"
        if avg >= 10:
            return "Cautious"
        return "Normal"


# --- Groq prompts --------------------------------------------
# Words in the JSON response must match SENTIMENT_NORM keys.

SENTIMENT_SYSTEM = """\
You are a crypto market sentiment analyst.
Classify current sentiment for each coin based on recent news and price action.\
"""

SENTIMENT_HUMAN = """\
Coins: {coins}

Return ONLY a JSON object, no markdown, no explanation:
{{"BTC": "Bullish|Bearish|Neutral|Panic|Crashing|Pumping|Dumping|FOMOing|Volatile"}}

One word per coin. Use only the words listed.\
"""