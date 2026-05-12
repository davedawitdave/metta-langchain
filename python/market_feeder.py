"""
market_feeder.py — Live market data → MeTTa atoms (pettaSH compatible).
═════════════════════════════════════════════════════════════════════════
Data sources:
  - CoinPaprika REST API: price, volume, 24h change (free, no key)
  - Groq API (llama-3.1-8b-instant): live news sentiment extraction

Writes market_state.metta via MeTTaBridge.update_market_state().
pettaSH re-reads the file from disk on each query — always live.
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
from constants import SENTIMENT_NORM, COIN_IDS

# ── Config ────────────────────────────────────────────────────
COINPAPRIKA_BASE = "https://api.coinpaprika.com/v1"



class MarketFeeder:
    """
    Fetches live price + news sentiment and writes MeTTa atoms.
    Uses Groq (via LangChain) for sentiment — same model as the ACO.
    """

    def __init__(self, bridge, groq_api_key: Optional[str] = None):
        self.bridge   = bridge
        self._key     = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "CryptoACO/2.0"})
        self._llm = None  # lazy init

    def poll(self, symbols: list[str] = None, once: bool = True) -> None:
        """Fetch data and update market_state.metta. Loop if once=False."""
        targets = symbols or list(COIN_IDS.keys())
        while True:
            try:
                self._update(targets)
            except Exception as e:
                print(f"[MarketFeeder] Error: {e}")
            if once:
                break
            time.sleep(60)

    # ── Internal update ───────────────────────────────────────

    def _update(self, symbols: list[str]) -> None:
        prices     = self._fetch_prices(symbols)
        sentiments = self._fetch_sentiments(symbols)
        global_st  = self._compute_global_state(prices)

        # Build list of MeTTa atoms
        atoms = [f"; Generated {datetime.now(timezone.utc).isoformat()}", ""]
        atoms.append(f"(GlobalMarketState {global_st})")
        atoms.append("")

        for sym in symbols:
            p = prices.get(sym)
            if not p:
                continue
            vol   = abs(p.get("pct_24h", 0.0))
            trend = "Bullish" if p.get("pct_24h", 0) > 0 else "Bearish"
            sent  = sentiments.get(sym, "Neutral")
            atoms.append(f"(AssetPrice {sym} {p['price']:.2f})")
            atoms.append(f"(AssetVolatility {sym} {vol:.2f})")
            atoms.append(f"(AssetSentiment {sym} {sent})")
            atoms.append(f"(AssetTrend {sym} {trend})")
            atoms.append("")

        # Keep portfolio state unchanged (user-defined)
        atoms += [
            "; Portfolio state — edit manually or via portfolio commands",
            "(PortfolioBalance 10000.00)",
            "(HoldingPct BTC  20.0)",
            "(HoldingPct ETH  15.0)",
            "(HoldingPct USDC 30.0)",
            "(DailyPnL 1.5)",
            "(TradesThisHour 2)",
        ]

        self.bridge.update_market_state(atoms)
        print(f"[MarketFeeder] AtomSpace updated — GlobalMarketState: {global_st}")

    # ── CoinPaprika prices ────────────────────────────────────

    def _fetch_prices(self, symbols: list[str]) -> dict:
        results = {}
        for sym in symbols:
            cid = COIN_IDS.get(sym)
            if not cid:
                continue
            try:
                r = self._session.get(
                    f"{COINPAPRIKA_BASE}/tickers/{cid}", timeout=8)
                r.raise_for_status()
                usd = r.json().get("quotes", {}).get("USD", {})
                results[sym] = {
                    "price":  float(usd.get("price", 0)),
                    "pct_24h": float(usd.get("percent_change_24h", 0)),
                }
            except Exception as e:
                print(f"[CoinPaprika] {sym}: {e}")
        return results

    # ── Groq news sentiment (LangChain chain) ────────────────

    def _fetch_sentiments(self, symbols: list[str]) -> dict[str, str]:
        if not self._key:
            return {s: "Neutral" for s in symbols}

        if self._llm is None:
            self._llm = ChatGroq(
                model="llama-3.1-8b-instant",
                api_key=self._key,
                temperature=0.1,
            )

        coin_list = ", ".join(symbols)
        prompt = ChatPromptTemplate.from_messages([
            ("system", SENTIMENT_SYSTEM),
            ("human",  SENTIMENT_HUMAN),
        ])
        chain = prompt | self._llm | StrOutputParser()

        try:
            text = chain.invoke({"coins": coin_list})
            return self._parse_sentiments(text, symbols)
        except Exception as e:
            print(f"[Groq Sentiment] {e}")
            return {s: "Neutral" for s in symbols}

    def _parse_sentiments(self, text: str, symbols: list[str]) -> dict:
        results = {s: "Neutral" for s in symbols}
        # Try JSON parse first
        try:
            clean = re.sub(r"```json\s*|```", "", text).strip()
            data  = json.loads(clean)
            for sym in symbols:
                raw = str(data.get(sym, "neutral")).lower()
                results[sym] = SENTIMENT_NORM.get(raw, "Neutral")
            return results
        except Exception:
            pass
        # Regex fallback
        for sym in symbols:
            m = re.search(rf'{sym}[:\s]+(\w+)', text, re.IGNORECASE)
            if m:
                results[sym] = SENTIMENT_NORM.get(m.group(1).lower(), "Neutral")
        return results

    # ── Global state ──────────────────────────────────────────

    def _compute_global_state(self, prices: dict) -> str:
        if not prices:
            return "Normal"
        avg_abs = sum(abs(p.get("pct_24h", 0)) for p in prices.values()) / len(prices)
        if avg_abs >= 20:  return "Panic"
        if avg_abs >= 10:  return "Cautious"
        return "Normal"


# ── Sentiment prompts ─────────────────────────────────────────
# Designed so Groq output maps directly to MeTTa SentimentSignal atoms.

SENTIMENT_SYSTEM = """You are a crypto market sentiment analyst with access to current news.
Classify market sentiment for each cryptocurrency based on recent news and price action."""

SENTIMENT_HUMAN = """Analyze the current market sentiment for: {coins}

Return ONLY a JSON object — no markdown, no explanation:
{{
  "BTC": "Bullish|Bearish|Neutral|Panic|Crashing|Pumping|Dumping|FOMOing|Volatile",
  "ETH": "Bullish|Bearish|Neutral|Panic|Crashing|Pumping|Dumping|FOMOing|Volatile"
}}

Use ONLY those exact sentiment words. Every coin gets exactly one word."""
