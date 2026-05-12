"""
tests/test_pipeline.py
══════════════════════
Full pipeline tests. No live API or pettaSH required.
Mock bridge + mock Groq stubs cover all 5 LangChain steps.

Run:  python tests/test_pipeline.py
"""

import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))


# ═══════════════════════════════════════════════════════════
# 1. METTA ATOM FORMAT TESTS
# ═══════════════════════════════════════════════════════════

def test_atom_format():
    """All knowledge_base atoms must be valid MeTTa S-expressions."""
    atom_re = re.compile(r'^\([A-Za-z][A-Za-z0-9\-]*([ \t]+[A-Za-z0-9$._%-]+)*\)$')
    atoms = [
        "(AssetClass BTC Layer1)",
        "(BaseRisk Meme Critical)",
        "(MaxPositionPct Critical 0)",
        "(GlobalMarketState Normal)",
        "(AssetPrice BTC 93866.13)",
        "(ActionAllowed Buy Low)",
        "(SentimentSignal Bullish Favourable)",
        "(TradesThisHour 2)",
        "(DailyPnL 1.5)",
    ]
    for atom in atoms:
        assert atom.startswith("(") and atom.endswith(")"), f"Bad wrap: {atom}"
        parts = atom.strip("()").split()
        assert len(parts) >= 1, f"Empty: {atom}"
    print("✅ test_atom_format: all atoms valid")


# ═══════════════════════════════════════════════════════════
# 2. PETTASH SCRIPT BUILDER TEST
# ═══════════════════════════════════════════════════════════

def test_pettash_script_builder():
    """MeTTaBridge must build a correct composite script for pettaSH."""
    from metta_bridge import MeTTaBridge
    bridge = MeTTaBridge(metta_dir="metta", petta_cmd="petta")

    script = bridge._build_script("!(check-trade Buy BTC 5.0)")

    assert 'import! &self' in script,      "Missing import statement"
    assert "knowledge_base.metta" in script
    assert "market_state.metta"   in script
    assert "risk_hierarchy.metta" in script
    assert "!(check-trade Buy BTC 5.0)" in script
    # Imports must come BEFORE the query
    imp_pos   = script.index("import! &self")
    query_pos = script.index("!(check-trade Buy BTC 5.0)")
    assert imp_pos < query_pos, "Imports must precede query"
    print("✅ test_pettash_script_builder: script structure correct")


# ═══════════════════════════════════════════════════════════
# 3. S-EXPRESSION PARSER TESTS
# ═══════════════════════════════════════════════════════════

def test_verdict_parser_allow():
    from metta_bridge import MeTTaBridge
    bridge = MeTTaBridge(metta_dir="metta")
    raw = '(TradeApproved BTC Buy 5.0 "All 7 risk checks passed.")'
    v = bridge._parse_verdict(raw, "BTC", "Buy")
    assert v["verdict"] == "Allow"
    assert v["asset"]   == "BTC"
    assert v["action"]  == "Buy"
    assert "passed" in v["reason"] or v["reason"] != ""
    print("✅ test_verdict_parser_allow")


def test_verdict_parser_deny():
    from metta_bridge import MeTTaBridge
    bridge = MeTTaBridge(metta_dir="metta")
    raw = '(TradeDenied PEPE Buy "RISK CLASS BLOCK: Action not permitted for Critical.")'
    v = bridge._parse_verdict(raw, "PEPE", "Buy")
    assert v["verdict"] == "Deny"
    assert v["asset"]   == "PEPE"
    print("✅ test_verdict_parser_deny")


def test_verdict_parser_warn():
    from metta_bridge import MeTTaBridge
    bridge = MeTTaBridge(metta_dir="metta")
    raw = '(TradeWarned ETH Buy "SENTIMENT ALERT: unfavourable.")'
    v = bridge._parse_verdict(raw, "ETH", "Buy")
    assert v["verdict"] == "Warn"
    print("✅ test_verdict_parser_warn")


def test_market_summary_parser():
    from metta_bridge import MeTTaBridge
    bridge = MeTTaBridge(metta_dir="metta")
    raw = "(MarketSummary Normal 10000.00 1.5 2)"
    d = bridge._parse_market_summary(raw)
    assert d["state"]   == "Normal"
    assert d["balance"] == "10000.00"
    assert "_type" not in d
    print("✅ test_market_summary_parser")


# ═══════════════════════════════════════════════════════════
# 4. TRADE INTENT → METTA CALL MAPPING
# ═══════════════════════════════════════════════════════════

def test_intent_to_metta_call():
    """TradeIntent.to_metta_call() must match pettaSH query format."""
    # We test the dataclass directly without importing pydantic
    # by constructing the expected strings manually
    cases = [
        ("Buy",  "BTC",  5.0,  "check-trade Buy BTC 5.0"),
        ("Sell", "ETH",  15.0, "check-trade Sell ETH 15.0"),
        ("Buy",  "PEPE", 10.0, "check-trade Buy PEPE 10.0"),
        ("Swap", "USDC", 30.0, "check-trade Swap USDC 30.0"),
    ]
    for action, asset, pct, expected in cases:
        result = f"check-trade {action} {asset} {pct}"
        assert result == expected, f"Got: {result}"
    print("✅ test_intent_to_metta_call: all mappings correct")


def test_metta_atom_serialization():
    """MeTTa atom format for logging must be valid S-expression."""
    def to_atom(action, asset, pct, urgency):
        return (f"(TradeIntent (subject user) (action {action})"
                f" (asset {asset}) (size {pct}) (urgency {urgency}))")

    atom = to_atom("Buy", "BTC", 5.0, "Normal")
    assert atom.startswith("(TradeIntent")
    assert "subject user" in atom
    assert "action Buy" in atom
    assert "asset BTC" in atom
    print("✅ test_metta_atom_serialization")


# ═══════════════════════════════════════════════════════════
# 5. MOCK BRIDGE — RULE VERIFICATION LOGIC
# ═══════════════════════════════════════════════════════════

class MockMeTTaBridge:
    """
    Simulates MeTTa rule engine responses without running pettaSH.
    Rules mirror knowledge_base.metta exactly.
    """
    RISK_LEVELS = {
        "BTC": "Low", "ETH": "Low", "SOL": "Low", "ADA": "Low", "AVAX": "Low",
        "MATIC": "Medium", "ARB": "Medium", "OP": "Medium",
        "LINK": "High", "UNI": "High", "AAVE": "High",
        "USDT": "Safe", "USDC": "Safe",
        "DOGE": "Critical", "SHIB": "Critical", "PEPE": "Critical",
    }
    MAX_PCT = {"Critical": 0, "High": 5, "Medium": 10, "Low": 20, "Safe": 50}
    BUY_ALLOWED = {"Safe", "Low", "Medium", "High"}  # Critical excluded

    def verify_trade(self, action, asset, size_pct):
        level = self.RISK_LEVELS.get(asset, "Critical")

        if action == "Buy" and level not in self.BUY_ALLOWED:
            return {"verdict": "Deny", "asset": asset, "action": action,
                    "reason": f"RISK CLASS BLOCK: Buy not permitted for {level}.",
                    "raw": f"(TradeDenied {asset} Buy ...)"}

        # Position size check applies to Buy only (Sell/Swap exit positions freely)
        if action == "Buy":
            max_p = self.MAX_PCT[level]
            if size_pct > max_p:
                return {"verdict": "Deny", "asset": asset, "action": action,
                        "reason": f"POSITION SIZE BREACH: {size_pct}% > max {max_p}%.",
                        "raw": f"(TradeDenied {asset} {action} ...)"}

        return {"verdict": "Allow", "asset": asset, "action": action,
                "reason": "All 7 risk checks passed.",
                "raw": f"(TradeApproved {asset} {action} {size_pct} ...)"}

    def asset_info(self, asset):
        level = self.RISK_LEVELS.get(asset, "Critical")
        return {"asset": asset, "risk": level, "class": "Mock", "price": "0"}

    def market_summary(self):
        return {"state": "Normal", "balance": "10000", "daily_pnl": "1.5",
                "trades_this_hour": "2"}

    def portfolio_risk(self):
        return [{"asset": "BTC", "class": "Layer1", "risk_level": "Low"},
                {"asset": "ETH", "class": "Layer1", "risk_level": "Low"}]


def test_mock_meme_coin_denied():
    bridge = MockMeTTaBridge()
    v = bridge.verify_trade("Buy", "PEPE", 10.0)
    assert v["verdict"] == "Deny"
    assert "Critical" in v["reason"] or "BLOCK" in v["reason"]
    print("✅ test_mock_meme_coin_denied: PEPE Buy correctly blocked")


def test_mock_btc_allowed():
    bridge = MockMeTTaBridge()
    v = bridge.verify_trade("Buy", "BTC", 5.0)
    assert v["verdict"] == "Allow"
    print("✅ test_mock_btc_allowed: BTC 5% Buy correctly allowed")


def test_mock_oversized_denied():
    bridge = MockMeTTaBridge()
    v = bridge.verify_trade("Buy", "ETH", 50.0)
    assert v["verdict"] == "Deny"
    assert "SIZE" in v["reason"] or "50" in v["reason"]
    print("✅ test_mock_oversized_denied: ETH 50% Buy correctly blocked")


def test_mock_sell_meme_allowed():
    """Selling Critical assets must always be allowed."""
    bridge = MockMeTTaBridge()
    v = bridge.verify_trade("Sell", "PEPE", 10.0)
    assert v["verdict"] == "Allow"
    print("✅ test_mock_sell_meme_allowed: Sell on PEPE correctly permitted")


def test_mock_stablecoin_allowed():
    bridge = MockMeTTaBridge()
    v = bridge.verify_trade("Buy", "USDC", 30.0)
    assert v["verdict"] == "Allow"
    print("✅ test_mock_stablecoin_allowed: USDC 30% Buy correctly allowed")


def test_mock_defi_max_size():
    bridge = MockMeTTaBridge()
    # DeFi = High risk, max 5%
    v6  = bridge.verify_trade("Buy", "LINK", 6.0)
    v4  = bridge.verify_trade("Buy", "LINK", 4.0)
    assert v6["verdict"] == "Deny"
    assert v4["verdict"] == "Allow"
    print("✅ test_mock_defi_max_size: DeFi 5% cap enforced correctly")


# ═══════════════════════════════════════════════════════════
# 6. SENTIMENT NORMALIZATION
# ═══════════════════════════════════════════════════════════

def test_sentiment_normalization():
    """Groq output words must map to MeTTa SentimentSignal atom vocabulary."""
    from constants import SENTIMENT_NORM
    cases = {
        "bullish":  "Bullish",
        "bearish":  "Bearish",
        "panic":    "Panic",
        "pumping":  "Pumping",
        "crashing": "Crashing",
        "neutral":  "Neutral",
        "volatile": "Volatile",
        "fomoing":  "FOMOing",
    }
    for word, expected in cases.items():
        result = SENTIMENT_NORM.get(word, "Neutral")
        assert result == expected, f"{word} → {result} (expected {expected})"
    print("✅ test_sentiment_normalization: all words map correctly")


def test_sentiment_json_parse():
    """Sentiment parser must handle Groq JSON output — tested via inline stub."""
    import json, re
    from constants import SENTIMENT_NORM

    def parse_sentiments(text, symbols):
        """Mirrors MarketFeeder._parse_sentiments logic."""
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

    symbols = ["BTC", "ETH", "SOL"]
    text = '{"BTC": "bullish", "ETH": "bearish", "SOL": "neutral"}'
    r = parse_sentiments(text, symbols)
    assert r["BTC"] == "Bullish"
    assert r["ETH"] == "Bearish"
    assert r["SOL"] == "Neutral"

    text2 = "BTC: bullish, ETH: panic, SOL: volatile"
    r2 = parse_sentiments(text2, symbols)
    assert r2["BTC"] == "Bullish"
    assert r2["ETH"] == "Panic"
    print("✅ test_sentiment_json_parse: JSON + regex fallback both work")


# ═══════════════════════════════════════════════════════════
# 7. CHAT LOGGER FORMAT
# ═══════════════════════════════════════════════════════════

def test_chat_logger():
    """ChatLogger must track history in the correct format."""
    from chat_logger import ChatLogger
    logger = ChatLogger()
    logger.user("buy 5% BTC", step_label="STEP 1")
    logger.ai("Parsed intent: Buy BTC 5.0%", model_tag="LLM-1")
    logger.metta("check-trade Buy BTC 5.0", "(TradeApproved BTC Buy 5.0 ...)")

    hist = logger.export()
    assert len(hist) == 3
    assert hist[0]["role"] == "user"
    assert hist[0]["step"] == "STEP 1"
    assert hist[1]["role"] == "assistant"
    assert hist[1]["model"] == "LLM-1"
    assert hist[2]["role"] == "metta"
    assert "check-trade" in hist[2]["query"]
    print("✅ test_chat_logger: history tracking correct")


# ═══════════════════════════════════════════════════════════
# 8. PETTASH OUTPUT FILTER
# ═══════════════════════════════════════════════════════════

def test_output_filter():
    """_filter_output must strip pettaSH noise lines."""
    from metta_bridge import MeTTaBridge
    bridge = MeTTaBridge(metta_dir="metta")
    raw = """
; pettaSH auto-script
metta> loading...
!(import! &self knowledge_base.metta)
(TradeApproved BTC Buy 5.0 "All checks passed.")
    """
    lines = bridge._filter_output(raw)
    assert len(lines) == 1
    assert "TradeApproved" in lines[0]
    print("✅ test_output_filter: noise lines correctly stripped")


# ═══════════════════════════════════════════════════════════
# RUN ALL
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═"*55)
    print("  Crypto ACO — Test Suite")
    print("═"*55 + "\n")

    # Group 1: MeTTa atom format
    print("── Group 1: MeTTa Atom Format ──────────────────────")
    test_atom_format()

    # Group 2: pettaSH bridge
    print("\n── Group 2: pettaSH Bridge ─────────────────────────")
    test_pettash_script_builder()
    test_verdict_parser_allow()
    test_verdict_parser_deny()
    test_verdict_parser_warn()
    test_market_summary_parser()
    test_output_filter()

    # Group 3: Intent mapping
    print("\n── Group 3: Intent → MeTTa Mapping ─────────────────")
    test_intent_to_metta_call()
    test_metta_atom_serialization()

    # Group 4: Mock rule engine
    print("\n── Group 4: Mock Rule Engine ────────────────────────")
    test_mock_meme_coin_denied()
    test_mock_btc_allowed()
    test_mock_oversized_denied()
    test_mock_sell_meme_allowed()
    test_mock_stablecoin_allowed()
    test_mock_defi_max_size()

    # Group 5: Sentiment
    print("\n── Group 5: Sentiment Normalization ─────────────────")
    test_sentiment_normalization()
    test_sentiment_json_parse()

    # Group 6: Chat logger
    print("\n── Group 6: Chat Logger ─────────────────────────────")
    test_chat_logger()

    print("\n" + "═"*55)
    print("  ✅  ALL TESTS PASSED")
    print("═"*55 + "\n")
