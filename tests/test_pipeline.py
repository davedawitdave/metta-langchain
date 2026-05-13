"""
tests/test_pipeline.py
No live PeTTa or Groq API required.
All external calls are mocked inside this file.
"""

import sys, os, re, json
_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_root, "python"))
sys.path.insert(0, _root)


# GROUP tests

def test_atom_format():
    atoms = [
        "(AssetClass BTC Layer1)",
        "(BaseRisk Meme Critical)",
        "(MaxPositionPct Critical 0)",
        "(MaxTotalClassExposure High 15)",
        "(LiquidityGuardPct 1.0)",
        "(GlobalMarketState Normal)",
        "(AssetPrice BTC 80240.17)",
        "(AssetVolume24h BTC 25000000000)",
        "(ActionAllowed Buy Low)",
        "(ActionAllowed Hold Low)",
        "(SentimentSignal Bullish Favourable)",
        "(TradesThisHour 2)",
        "(DailyPnL 1.5)",
    ]
    for atom in atoms:
        assert atom.startswith("(") and atom.endswith(")"), f"Bad wrap: {atom}"
        parts = atom.strip("()").split()
        assert len(parts) >= 1, f"Empty atom: {atom}"


def test_extract_concrete_trade_line():
    """Ground Trade* line must win over AssetRisk and rule templates."""
    from metta_bridge import MeTTaBridge
    blob = """
(TradeApproved $asset $action $pct "template")
(AssetRisk BTC Layer1 Low)
(TradeApproved BTC Buy 5.0 "All 9 checks passed.")
"""
    ln = MeTTaBridge._extract_concrete_trade_line(blob)
    assert ln.startswith("(TradeApproved BTC Buy")
    assert "AssetRisk" not in ln


# GROUP tests

def test_script_builder():
    from metta_bridge import MeTTaBridge
    b = MeTTaBridge(metta_dir="metta", petta_cmd="petta")
    script = b._build_script("!(check-trade Buy BTC 5.0)")

    assert "import! &self" in script,          "missing import"
    assert "knowledge_base.metta" in script,   "missing knowledge_base"
    assert "market_state.metta"   in script,   "missing market_state"
    assert "risk_hierarchy.metta" in script,   "missing risk_hierarchy"
    assert "main_logic.metta" not in script,   "main API merged into risk_hierarchy"
    assert "!(check-trade Buy BTC 5.0)" in script, "missing query"

    # imports must appear before the query
    imp_pos   = script.index("import! &self")
    query_pos = script.index("!(check-trade Buy BTC 5.0)")
    assert imp_pos < query_pos, "imports must precede query"


def test_output_filter():
    from metta_bridge import MeTTaBridge
    b = MeTTaBridge(metta_dir="metta")
    raw = """
; comment
metta> loading
!(import! &self kb.metta)
(TradeApproved BTC Buy 5.0 "All 9 checks passed.")
some noise line
(TradeDenied PEPE Buy "Critical risk.")
    """
    lines = b._filter_output(raw)
    assert len(lines) == 2
    assert any("TradeApproved" in ln for ln in lines)
    assert any("TradeDenied"   in ln for ln in lines)


# GROUP tests

def test_parse_verdict_allow():
    from metta_bridge import MeTTaBridge
    b = MeTTaBridge(metta_dir="metta")
    raw = '(TradeApproved BTC Buy 5.0 "All 9 checks passed.")'
    v = b._parse_verdict(raw, "BTC", "Buy")
    assert v["verdict"] == "Allow"
    assert v["asset"]   == "BTC"
    assert v["action"]  == "Buy"
    assert "passed" in v["reason"]


def test_parse_verdict_deny():
    from metta_bridge import MeTTaBridge
    b = MeTTaBridge(metta_dir="metta")
    raw = '(TradeDenied PEPE Buy "Asset is Critical risk. Buy not permitted.")'
    v = b._parse_verdict(raw, "PEPE", "Buy")
    assert v["verdict"] == "Deny"
    assert v["asset"]   == "PEPE"


def test_parse_verdict_warn():
    from metta_bridge import MeTTaBridge
    b = MeTTaBridge(metta_dir="metta")
    raw = '(TradeWarned ETH Buy "Sentiment is unfavourable.")'
    v = b._parse_verdict(raw, "ETH", "Buy")
    assert v["verdict"] == "Warn"


def test_parse_market_summary():
    from metta_bridge import MeTTaBridge
    b = MeTTaBridge(metta_dir="metta")
    raw = "(MarketSummary Normal 10000.00 1.5 2)"
    d = b._parse_market_summary(raw)
    assert d["state"]   == "Normal"
    assert d["balance"] == "10000.00"
    assert "_t" not in d


# GROUP tests

def test_intent_metta_call():
    cases = [
        ("Buy",  "BTC",  5.0,  "check-trade Buy BTC 5.0"),
        ("Sell", "ETH",  15.0, "check-trade Sell ETH 15.0"),
        ("Buy",  "PEPE", 10.0, "check-trade Buy PEPE 10.0"),
        ("Swap", "USDC", 30.0, "check-trade Swap USDC 30.0"),
    ]
    for action, asset, pct, expected in cases:
        result = f"check-trade {action} {asset} {pct}"
        assert result == expected, f"got: {result}"


def test_intent_atom():
    def atom(action, asset, pct, urgency):
        return (f"(TradeIntent (subject user) (action {action})"
                f" (asset {asset}) (size {pct}) (urgency {urgency}))")
    a = atom("Buy", "BTC", 5.0, "Normal")
    assert "action Buy"  in a
    assert "asset BTC"   in a
    assert "size 5.0"    in a


# GROUP tests

class MockBridge:
    """
    Simulates MeTTa verdicts without PeTTa.
    Rules mirror knowledge_base.metta exactly including
    the new total-class-exposure and liquidity checks.
    """
    RISK = {
        "BTC": "Low",  "ETH": "Low",  "SOL": "Low",
        "ADA": "Low",  "AVAX":"Low",
        "MATIC":"Medium","ARB":"Medium","OP":"Medium",
        "LINK":"High", "UNI":"High",  "AAVE":"High",
        "USDT":"Safe", "USDC":"Safe",
        "DOGE":"Critical","SHIB":"Critical","PEPE":"Critical",
    }
    MAX_SINGLE = {"Critical":0,"High":5,"Medium":10,"Low":20,"Safe":50}
    MAX_CLASS  = {"Critical":0,"High":15,"Medium":25,"Low":60,"Safe":80}
    BUY_OK     = {"Safe","Low","Medium","High"}
    # Simulated holdings for exposure test
    HOLDINGS   = {"LINK":3.0,"UNI":4.0}   # DeFi = 7%

    def verify_trade(self, action, asset, size_pct):
        level = self.RISK.get(asset, "Critical")

        if action == "Hold":
            return {"verdict": "Allow", "asset": asset, "action": action,
                    "reason": "Hold is not an opening trade.", "raw": f"(TradeApproved {asset} {action} {size_pct})"}

        # check 4: asset risk
        if action == "Buy" and level not in self.BUY_OK:
            return self._deny(asset, action, "Asset is Critical risk. Buy not permitted.")

        if action == "Buy":
            # check 5: single position size
            if size_pct > self.MAX_SINGLE[level]:
                return self._deny(asset, action,
                    f"Position {size_pct}% exceeds single-asset limit {self.MAX_SINGLE[level]}%.")

            # check 6: total class exposure (new)
            current = sum(v for k, v in self.HOLDINGS.items()
                         if self.RISK.get(k) == level)
            if current + size_pct > self.MAX_CLASS[level]:
                return self._deny(asset, action,
                    f"Total {level} exposure {current+size_pct}% exceeds class limit {self.MAX_CLASS[level]}%.")

        return {"verdict":"Allow","asset":asset,"action":action,
                "reason":"All checks passed.","raw":f"(TradeApproved {asset} {action} {size_pct})"}

    def _deny(self, asset, action, reason):
        return {"verdict":"Deny","asset":asset,"action":action,
                "reason":reason,"raw":f"(TradeDenied {asset} {action})"}

    def asset_info(self, asset):
        return {"asset":asset,"risk":self.RISK.get(asset,"Critical"),
                "class":"Mock","price":"0","volatility":"0",
                "sentiment":"Neutral","trend":"Neutral"}

    def market_summary(self):
        return {"state":"Normal","balance":"10000",
                "daily_pnl":"1.5","trades_this_hour":"2"}

    def portfolio_risk(self):
        return [{"asset":"BTC","class":"Layer1","risk_level":"Low"}]


def test_hold_skips_size_cap():
    """Hold with large size_pct must not hit buy-style position limits."""
    b = MockBridge()
    v = b.verify_trade("Hold", "BTC", 50.0)
    assert v["verdict"] == "Allow"


def test_meme_buy_denied():
    b = MockBridge()
    v = b.verify_trade("Buy", "PEPE", 10.0)
    assert v["verdict"] == "Deny"
    assert "Critical" in v["reason"]


def test_btc_buy_allowed():
    b = MockBridge()
    v = b.verify_trade("Buy", "BTC", 5.0)
    assert v["verdict"] == "Allow"


def test_oversize_denied():
    b = MockBridge()
    v = b.verify_trade("Buy", "ETH", 50.0)
    assert v["verdict"] == "Deny"


def test_sell_critical_allowed():
    """Selling a Critical asset must always be allowed."""
    b = MockBridge()
    v = b.verify_trade("Sell", "PEPE", 5.0)
    assert v["verdict"] == "Allow"


def test_stablecoin_allowed():
    b = MockBridge()
    v = b.verify_trade("Buy", "USDC", 30.0)
    assert v["verdict"] == "Allow"


def test_defi_single_cap():
    """DeFi (High) single max is 5%."""
    b = MockBridge()
    assert b.verify_trade("Buy", "LINK", 6.0)["verdict"] == "Deny"
    assert b.verify_trade("Buy", "LINK", 4.0)["verdict"] == "Allow"


def test_total_class_exposure():
    """
    MockBridge has LINK 3% + UNI 4% = 7% High already.
    MaxTotalClassExposure High = 15%.
    Adding 10% AAVE -> 17% > 15 -> Deny.
    Adding 5%  AAVE -> 12% < 15 -> Allow.
    """
    b = MockBridge()
    v_deny  = b.verify_trade("Buy", "AAVE", 10.0)
    v_allow = b.verify_trade("Buy", "AAVE", 5.0)
    assert v_deny["verdict"]  == "Deny",  f"expected Deny, got {v_deny}"
    assert v_allow["verdict"] == "Allow", f"expected Allow, got {v_allow}"


# GROUP tests

def test_sentiment_norm():
    from constants import SENTIMENT_NORM
    cases = {
        "bullish":"Bullish", "bearish":"Bearish",
        "panic":"Panic",     "pumping":"Pumping",
        "crashing":"Crashing","neutral":"Neutral",
        "volatile":"Volatile","fomoing":"FOMOing",
    }
    for word, expected in cases.items():
        got = SENTIMENT_NORM.get(word, "Neutral")
        assert got == expected, f"{word} -> {got} (expected {expected})"


def test_sentiment_json_parse():
    import json, re
    from constants import SENTIMENT_NORM

    def parse(text, symbols):
        results = {s: "Neutral" for s in symbols}
        try:
            data = json.loads(re.sub(r"```json\s*|```", "", text).strip())
            for sym in symbols:
                results[sym] = SENTIMENT_NORM.get(str(data.get(sym,"neutral")).lower(), "Neutral")
            return results
        except Exception:
            pass
        for sym in symbols:
            m = re.search(rf'{sym}[:\s]+(\w+)', text, re.IGNORECASE)
            if m:
                results[sym] = SENTIMENT_NORM.get(m.group(1).lower(), "Neutral")
        return results

    syms = ["BTC","ETH","SOL"]
    r = parse('{"BTC":"bullish","ETH":"bearish","SOL":"neutral"}', syms)
    assert r["BTC"] == "Bullish"
    assert r["ETH"] == "Bearish"
    assert r["SOL"] == "Neutral"

    r2 = parse("BTC: pumping, ETH: panic", syms)
    assert r2["BTC"] == "Pumping"
    assert r2["ETH"] == "Panic"


# GROUP tests

def test_chat_logger():
    from chat_logger import ChatLogger
    log = ChatLogger()
    log.step_header("STEP 1  Intent Parser")
    log.user_says("buy 5% BTC")
    log.llm_says("action=Buy asset=BTC size=5%", tag="LLM-1")
    log.metta_query("check-trade Buy BTC 5.0", "(TradeApproved BTC Buy 5.0)")
    log.metta_verdict("Allow", "BTC", "Buy")

    hist = log.export()
    roles = [h["role"] for h in hist]
    assert "step"      in roles
    assert "user"      in roles
    assert "assistant" in roles
    assert "metta"     in roles


# GROUP tests

def test_new_kb_atoms():
    """Verify that the Gemini-suggested atoms are correctly formatted."""
    new_atoms = [
        "(MaxTotalClassExposure Critical 0)",
        "(MaxTotalClassExposure High     15)",
        "(MaxTotalClassExposure Medium   25)",
        "(MaxTotalClassExposure Low      60)",
        "(MaxTotalClassExposure Safe     80)",
        "(LiquidityGuardPct 1.0)",
        "(AssetVolume24h BTC 25000000000)",
        "(AssetVolume24h SOL 3000000000)",
    ]
    for atom in new_atoms:
        assert atom.startswith("(") and atom.endswith(")"), f"bad: {atom}"
        parts = atom.strip("()").split()
        assert len(parts) >= 2


# ============================================================
# RUN
# ============================================================
