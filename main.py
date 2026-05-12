"""
main.py — Crypto ACO Chat Orchestrator.
════════════════════════════════════════
Entry point. Wires MeTTaBridge (pettaSH) + LangChainACOPipeline (Groq/Llama).
Runs a You/ACO chat REPL with full step-by-step logging.

Usage:
  python main.py             → interactive chat REPL
  python main.py --demo      → run 7 demo scenarios
  python main.py --query "buy 5% BTC"  → single query
  python main.py --check     → ping pettaSH + Groq connectivity
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add python/ to path
sys.path.insert(0, str(Path(__file__).parent / "python"))

from metta_bridge       import MeTTaBridge
from langchain_pipeline import LangChainACOPipeline
from market_feeder      import MarketFeeder


# ── Configuration ─────────────────────────────────────────────
GROQ_KEY  = os.getenv("GROQ_API_KEY", "")
METTA_DIR = Path(__file__).parent / "metta"
# Use local petta wrapper by default
PETTA_CMD = os.getenv("PETTA_CMD", str(Path(__file__).parent / "petta"))


# ═══════════════════════════════════════════════════════════════
# CryptoACO — the coordinator
# ═══════════════════════════════════════════════════════════════

class CryptoACO:

    def __init__(self):
        self.bridge   = MeTTaBridge(metta_dir=str(METTA_DIR), petta_cmd=PETTA_CMD)
        self.feeder   = MarketFeeder(bridge=self.bridge, groq_api_key=GROQ_KEY)
        self.pipeline = LangChainACOPipeline(
            bridge=self.bridge,
            groq_api_key=GROQ_KEY,
        )
        self._audit_log: list[dict] = []

    # ── Boot ─────────────────────────────────────────────────

    def boot(self, fetch_live: bool = True) -> None:
        print("\n" + "═"*60)
        print("  CRYPTO ACO — Algorithmic Compliance Officer")
        print("  Powered by: pettaSH (MeTTa) + Groq llama-3.3-70b")
        print("═"*60)

        print("\n[ACO] Checking pettaSH connectivity...")
        ok, msg = self.bridge.ping()
        if ok:
            print(f"[ACO] ✅ pettaSH ready: {msg}")
        else:
            print(f"[ACO] ⚠️  pettaSH check: {msg}")
            print("[ACO] Continuing — bridge will attempt queries anyway.")

        if not GROQ_KEY:
            print("[ACO] ⚠️  GROQ_API_KEY not set. LLM steps will fail.")
            print("      Set it with: export GROQ_API_KEY='gsk_...'")
        else:
            print(f"[ACO] ✅ Groq API key found.")

        if fetch_live:
            print("[ACO] Fetching live market data via CoinPaprika...")
            self.feeder.poll(symbols=["BTC","ETH","SOL","DOGE","USDC"], once=True)

        print("[ACO] Ready. Type 'help' for commands.\n")

    # ── Single request ────────────────────────────────────────

    def process(self, user_message: str) -> str:
        response = self.pipeline.process(user_message)
        self._audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "query":     user_message,
            "response":  response,
            "history":   self.pipeline.get_chat_history()[-6:],
        })
        return response

    # ── Portfolio snapshot ────────────────────────────────────

    def portfolio_snapshot(self) -> str:
        risks = self.bridge.portfolio_risk()
        mkt   = self.bridge.market_summary()
        lines = [
            "═"*45,
            "  PORTFOLIO RISK SNAPSHOT",
            "═"*45,
            f"  Global Market State : {mkt.get('state','?')}",
            f"  Portfolio Balance   : ${mkt.get('balance','?')}",
            f"  Daily PnL           : {mkt.get('daily_pnl','?')}%",
            f"  Trades This Hour    : {mkt.get('trades_this_hour','?')}",
            "",
            "  Holdings:",
        ]
        for r in risks:
            asset = r.get("asset","?")
            cls   = r.get("class","?")
            lvl   = r.get("risk_level","?")
            icon  = {"Critical":"🔴","High":"🟠","Medium":"🟡","Low":"🟢","Safe":"🔵"}.get(lvl,"⚪")
            lines.append(f"  {icon} {asset:<6} {cls:<12} Risk: {lvl}")
        lines.append("═"*45)
        return "\n".join(lines)

    # ── Audit export ─────────────────────────────────────────

    def export_audit(self, path: str = "audit_log.json") -> None:
        with open(path, "w") as f:
            json.dump(self._audit_log, f, indent=2)
        print(f"[ACO] Audit log saved → {path}")


# ═══════════════════════════════════════════════════════════════
# DEMO SCENARIOS
# ═══════════════════════════════════════════════════════════════

DEMO_QUERIES = [
    # verdict: Allow
    ("buy 5% BTC",
     "Should ALLOW — BTC is Layer1 (Low risk), size within 20% max"),
    # verdict: Deny — Critical risk (Meme)
    ("FOMO into PEPE with 10%, it's about to moon!",
     "Should DENY — PEPE is Meme (Critical), Buy not in ActionAllowed"),
    # verdict: Deny — position too large
    ("all in on ETH, put 50% of my portfolio in now",
     "Should DENY — ETH max is 20%, 50% exceeds limit"),
    # verdict: Allow or Warn — sentiment check
    ("buy 3% Ethereum",
     "Should ALLOW/WARN — ETH sentiment check"),
    # verdict: Allow — selling always ok
    ("sell 10% of my Bitcoin holdings",
     "Should ALLOW — Sell always permitted"),
    # verdict: Deny — Meme
    ("get me into dogecoin, just 2%",
     "Should DENY — DOGE is Meme (Critical)"),
    # verdict: Allow — Stablecoin (Safe)
    ("convert 30% to USDC to de-risk my portfolio",
     "Should ALLOW — USDC is Stablecoin (Safe)"),
]


def demo_mode(aco: CryptoACO) -> None:
    print("\n" + "█"*60)
    print("  DEMO MODE — 7 test scenarios")
    print("█"*60)

    for i, (query, comment) in enumerate(DEMO_QUERIES, 1):
        print(f"\n{'─'*60}")
        print(f"  Scenario {i}/7: {comment}")
        aco.process(query)
        input("  [Press Enter for next scenario...]")

    print("\n" + "█"*60)
    print(aco.portfolio_snapshot())
    aco.export_audit()


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE CHAT REPL
# ═══════════════════════════════════════════════════════════════

HELP_TEXT = """
Commands:
  <your trade request>  →  Process through the full 4-step ACO pipeline
  portfolio             →  Show current portfolio risk snapshot
  audit                 →  Export audit log to audit_log.json
  history               →  Show this session's chat history
  clear                 →  Clear screen
  help                  →  Show this message
  quit / exit           →  Exit

Example trade requests:
  "buy 5% BTC"
  "I want to sell half my ETH"
  "can I put 10% into Solana?"
  "swap 20% to USDC to hedge"
  "FOMO into PEPE with 5%"
  "what about buying some Dogecoin?"
  "exit all my DeFi positions"
  "is it safe to buy ETH right now?"
"""


def repl_mode(aco: CryptoACO) -> None:
    print(HELP_TEXT)
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[ACO] Session ended.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("quit", "exit", "q"):
            print("[ACO] Goodbye.")
            break
        elif cmd == "portfolio":
            print(aco.portfolio_snapshot())
        elif cmd == "audit":
            aco.export_audit()
        elif cmd == "history":
            for entry in aco.pipeline.get_chat_history():
                role = entry.get("role","?").upper()
                content = entry.get("content") or entry.get("result","")
                print(f"  [{role}] {content[:120]}")
        elif cmd in ("clear", "cls"):
            os.system("clear")
        elif cmd == "help":
            print(HELP_TEXT)
        else:
            aco.process(user_input)


# ═══════════════════════════════════════════════════════════════
# CONNECTIVITY CHECK
# ═══════════════════════════════════════════════════════════════

def check_mode(bridge: MeTTaBridge) -> None:
    print("\n[CHECK] pettaSH:")
    ok, msg = bridge.ping()
    print(f"  {'✅' if ok else '❌'} {msg}")

    print("\n[CHECK] GROQ_API_KEY:")
    if GROQ_KEY:
        print(f"  ✅ Set (starts with: {GROQ_KEY[:8]}...)")
    else:
        print("  ❌ Not set. Export: GROQ_API_KEY='gsk_...'")

    print("\n[CHECK] MeTTa files:")
    for fname in ["knowledge_base.metta","market_state.metta",
                  "risk_hierarchy.metta","main_logic.metta"]:
        path = METTA_DIR / fname
        status = "✅" if path.exists() else "❌"
        print(f"  {status} metta/{fname}")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crypto ACO — Algorithmic Compliance Officer",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--demo",  action="store_true", help="Run 7 demo scenarios")
    parser.add_argument("--repl",  action="store_true", help="Interactive chat REPL (default)")
    parser.add_argument("--query", type=str,            help="Process a single query")
    parser.add_argument("--check", action="store_true", help="Check connectivity only")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip live market data fetch on boot")
    args = parser.parse_args()

    if args.check:
        bridge = MeTTaBridge(metta_dir=str(METTA_DIR), petta_cmd=PETTA_CMD)
        check_mode(bridge)
        sys.exit(0)

    aco = CryptoACO()
    aco.boot(fetch_live=not args.no_fetch)

    if args.demo:
        demo_mode(aco)
    elif args.query:
        print(aco.process(args.query))
    else:
        # Default: interactive REPL
        repl_mode(aco)
