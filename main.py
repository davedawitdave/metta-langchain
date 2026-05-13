"""
main.py — Crypto ACO entry point.

Usage:
  python main.py              # interactive chat REPL (default)
  python main.py --demo       # run 7 preset scenarios
  python main.py --query "buy 5% BTC"
  python main.py --check      # connectivity check only
  python main.py --no-fetch   # skip live data fetch on boot
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add python/ to import path
sys.path.insert(0, str(Path(__file__).parent / "python"))

from metta_bridge       import MeTTaBridge
from langchain_pipeline import LangChainACOPipeline
from market_feeder      import MarketFeeder

# --- Configuration -------------------------------------------
GROQ_KEY  = os.getenv("GROQ_API_KEY", "")
METTA_DIR = Path(__file__).parent / "metta"
# Use the local petta wrapper script if present, otherwise fall back to PATH
_local_petta = Path(__file__).parent / "petta"
PETTA_CMD = os.getenv("PETTA_CMD", str(_local_petta) if _local_petta.exists() else "petta")


# ============================================================
# CryptoACO coordinator
# ============================================================

class CryptoACO:

    def __init__(self):
        self.bridge    = MeTTaBridge(metta_dir=str(METTA_DIR), petta_cmd=PETTA_CMD)
        self.feeder    = MarketFeeder(bridge=self.bridge, groq_api_key=GROQ_KEY)
        self.pipeline  = LangChainACOPipeline(bridge=self.bridge, groq_api_key=GROQ_KEY)
        self._audit: list[dict] = []

    def boot(self, fetch_live: bool = True) -> None:
        print("\nCRYPTO ACO — Algorithmic Compliance Officer")
        print("MeTTa (PeTTa) + LangChain + Groq llama-3.3-70b")
        print("-" * 50)

        ok, msg = self.bridge.ping()
        status  = "OK" if ok else "not found"
        print(f"PeTTa    : {status}  ({msg})")

        key_status = f"set ({GROQ_KEY[:8]}...)" if GROQ_KEY else "NOT SET"
        print(f"Groq key   : {key_status}")

        if not GROQ_KEY:
            print("WARNING: GROQ_API_KEY not set — LLM steps will fail.")
            print("         Set it with:  export GROQ_API_KEY='gsk_...'")

        if fetch_live:
            print("\nFetching live market data from CoinPaprika...")
            self.feeder.poll(symbols=["BTC", "ETH", "SOL", "LINK", "DOGE", "USDC"], once=True)

        print("\nReady. Type 'help' for commands.\n")

    def process(self, user_message: str) -> str:
        response = self.pipeline.process(user_message)
        self._audit.append({
            "timestamp": datetime.utcnow().isoformat(),
            "query":     user_message,
            "response":  response,
        })
        return response

    def portfolio_snapshot(self) -> str:
        risks = self.bridge.portfolio_risk()
        mkt   = self.bridge.market_summary()
        lines = [
            "",
            "PORTFOLIO RISK SNAPSHOT",
            "-" * 40,
            f"  Global state  : {mkt.get('state','?')}",
            f"  Balance       : ${mkt.get('balance','?')}",
            f"  Daily PnL     : {mkt.get('daily_pnl','?')}%",
            f"  Trades/hour   : {mkt.get('trades_this_hour','?')}",
            "",
            "  Holdings:",
        ]
        risk_label = {
            "Critical": "CRITICAL",
            "High":     "HIGH    ",
            "Medium":   "MEDIUM  ",
            "Low":      "LOW     ",
            "Safe":     "SAFE    ",
        }
        for r in risks:
            asset = r.get("asset", "?")
            cls   = r.get("class", "?")
            lvl   = r.get("risk_level", "?")
            label = risk_label.get(lvl, lvl)
            lines.append(f"    {asset:<6}  {cls:<12}  risk: {label}")
        lines.append("-" * 40)
        return "\n".join(lines)

    def export_audit(self, path: str = "audit_log.json") -> None:
        with open(path, "w") as f:
            json.dump(self._audit, f, indent=2)
        print(f"Audit log saved -> {path}")


# ============================================================
# Demo scenarios
# ============================================================

DEMO_QUERIES = [
    ("buy 5% BTC",
     "ALLOW  — BTC is Layer1 (Low risk), size within 20% cap"),
    ("FOMO into PEPE with 10%",
     "DENY   — PEPE is Meme (Critical), Buy permanently blocked"),
    ("all in on ETH, put 50% in now",
     "DENY   — ETH max single position is 20%"),
    ("buy 3% Ethereum",
     "ALLOW or WARN — depends on live sentiment"),
    ("sell 10% of my Bitcoin",
     "ALLOW  — Sell always permitted"),
    ("get me into dogecoin, just 2%",
     "DENY   — DOGE is Meme (Critical)"),
    ("buy 10% LINK",
     "DENY   — would exceed total DeFi class exposure limit (15%)"),
]


def demo_mode(aco: CryptoACO) -> None:
    print("\n" + "=" * 60)
    print("  DEMO MODE — 7 scenarios")
    print("=" * 60)
    for i, (query, comment) in enumerate(DEMO_QUERIES, 1):
        print(f"\nScenario {i}/7: {comment}")
        aco.process(query)
        input("  [Enter for next]")
    print(aco.portfolio_snapshot())
    aco.export_audit()


# ============================================================
# Interactive REPL
# ============================================================

HELP_TEXT = """
Commands:
  <your message>   run through the full ACO pipeline
  portfolio        show portfolio risk snapshot from MeTTa
  audit            export audit_log.json
  history          print this session's step log
  help             show this message
  quit             exit

Example requests:
  buy 5% BTC
  sell half my ETH
  can I put 10% into Solana?
  swap 20% to USDC
  get me into PEPE
  is it safe to buy ETH right now?
  what's my portfolio risk?
"""


def repl_mode(aco: CryptoACO) -> None:
    print(HELP_TEXT)
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("quit", "exit", "q"):
            print("Goodbye.")
            break
        elif cmd == "portfolio":
            print(aco.portfolio_snapshot())
        elif cmd == "audit":
            aco.export_audit()
        elif cmd == "history":
            for entry in aco.pipeline.get_chat_history():
                role    = entry.get("role", "?").upper()
                content = entry.get("content") or entry.get("result", "")
                print(f"  [{role}] {str(content)[:100]}")
        elif cmd == "help":
            print(HELP_TEXT)
        else:
            aco.process(user_input)


# ============================================================
# Connectivity check
# ============================================================

def check_mode() -> None:
    bridge = MeTTaBridge(metta_dir=str(METTA_DIR), petta_cmd=PETTA_CMD)
    print("\n[CHECK] PeTTa")
    ok, msg = bridge.ping()
    print(f"  {'OK' if ok else 'FAIL'}  {msg}")

    print("\n[CHECK] GROQ_API_KEY")
    if GROQ_KEY:
        print(f"  OK  starts with {GROQ_KEY[:8]}...")
    else:
        print("  MISSING — export GROQ_API_KEY='gsk_...'")

    print("\n[CHECK] MeTTa files")
    for fname in ["knowledge_base.metta", "market_state.metta",
                  "risk_hierarchy.metta", "main_logic.metta"]:
        path   = METTA_DIR / fname
        status = "OK" if path.exists() else "MISSING"
        print(f"  {status}  metta/{fname}")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crypto ACO")
    parser.add_argument("--demo",     action="store_true")
    parser.add_argument("--repl",     action="store_true")
    parser.add_argument("--query",    type=str)
    parser.add_argument("--check",    action="store_true")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()

    if args.check:
        check_mode()
        sys.exit(0)

    aco = CryptoACO()
    aco.boot(fetch_live=not args.no_fetch)

    if args.demo:
        demo_mode(aco)
    elif args.query:
        aco.process(args.query)
    else:
        repl_mode(aco)