"""Crypto ACO — entry point with demo, REPL, and check modes."""
import os, sys, json, argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent / "python"))
from metta_bridge import MeTTaBridge
from langchain_pipeline import LangChainACOPipeline
from market_feeder import MarketFeeder

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
METTA_DIR = Path(__file__).parent / "metta"
_local_petta = Path(__file__).parent / "petta"
PETTA_CMD = os.getenv("PETTA_CMD", str(_local_petta) if _local_petta.exists() else "petta")

class CryptoACO:
    def __init__(self):
        self.bridge = MeTTaBridge(metta_dir=str(METTA_DIR), petta_cmd=PETTA_CMD)
        self.feeder = MarketFeeder(bridge=self.bridge, groq_api_key=GROQ_KEY)
        self.pipeline = LangChainACOPipeline(bridge=self.bridge, groq_api_key=GROQ_KEY)
        self._audit = []

    def boot(self, fetch_live=True):
        print("\nCRYPTO ACO — Algorithmic Compliance Officer")
        print("MeTTa + LangChain + Groq llama-3.3-70b")
        print("-" * 50)
        ok, msg = self.bridge.ping()
        print(f"Symbolic  : {'OK' if ok else 'not found'}  ({msg})")
        key_status = f"set ({GROQ_KEY[:8]}...)" if GROQ_KEY else "NOT SET"
        print(f"Groq key   : {key_status}")
        if not GROQ_KEY:
            print("WARNING: export GROQ_API_KEY='gsk_...'")
        if fetch_live:
            print("\nFetching live market data...")
            self.feeder.poll(symbols=["BTC", "ETH", "SOL", "LINK", "DOGE", "USDC"], once=True)
        print("\nReady. Type 'help' for commands.\n")

    def process(self, user_message):
        response = self.pipeline.process(user_message)
        self._audit.append({"timestamp": datetime.utcnow().isoformat(), "query": user_message, "response": response})
        return response

    def portfolio_snapshot(self):
        risks = self.bridge.portfolio_risk()
        mkt = self.bridge.market_summary()
        lines = ["", "PORTFOLIO SNAPSHOT", "-" * 40,
                 f"  State     : {mkt.get('state','?')}",
                 f"  Balance   : ${mkt.get('balance','?')}",
                 f"  Daily PnL : {mkt.get('daily_pnl','?')}%",
                 f"  Trades/hr : {mkt.get('trades_this_hour','?')}", "", "  Holdings:"]
        risk_map = {"Critical": "CRITICAL", "High": "HIGH", "Medium": "MEDIUM", "Low": "LOW", "Safe": "SAFE"}
        for r in risks:
            lvl = risk_map.get(r.get("risk_level", "?"), r.get("risk_level", "?"))
            lines.append(f"    {r.get('asset','?'):<6}  {r.get('class','?'):<12}  risk: {lvl}")
        lines.append("-" * 40)
        return "\n".join(lines)

    def export_audit(self, path="audit_log.json"):
        with open(path, "w") as f:
            json.dump(self._audit, f, indent=2)
        print(f"Audit log saved -> {path}")

DEMO_QUERIES = [
    ("buy 5% BTC", "ALLOW — BTC Low risk, within cap"),
    ("FOMO into PEPE 10%", "DENY — PEPE Critical, blocked"),
    ("all in ETH 50%", "DENY — exceeds 20% cap"),
    ("buy 3% Ethereum", "ALLOW/WARN — depends on sentiment"),
    ("sell 10% Bitcoin", "ALLOW — sells always permitted"),
    ("buy dogecoin 2%", "DENY — DOGE Critical"),
    ("buy 10% LINK", "DENY — exceeds DeFi total exposure"),
]

def demo_mode(aco):
    print("\n" + "=" * 60 + "\n  DEMO MODE — 7 scenarios\n" + "=" * 60)
    for i, (query, comment) in enumerate(DEMO_QUERIES, 1):
        print(f"\n[{i}/7] {comment}")
        aco.process(query)
        input("  [Enter for next]")
    print(aco.portfolio_snapshot())
    aco.export_audit()

HELP = """Commands:
  <message>   run ACO pipeline
  portfolio   show portfolio snapshot
  audit       export audit_log.json
  history     print session log
  help        show commands
  quit        exit

Examples: buy 5% BTC, sell half my ETH, is it safe to buy ETH?, swap 20% USDC"""

def repl_mode(aco):
    print(HELP)
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
                print(f"  [{entry.get('role','?').upper()}] {str(entry.get('content') or entry.get('result', ''))[:100]}")
        elif cmd == "help":
            print(HELP)
        else:
            print(aco.process(user_input))

def check_mode():
    bridge = MeTTaBridge(metta_dir=str(METTA_DIR), petta_cmd=PETTA_CMD)
    print("\n[CHECK] Symbolic")
    ok, msg = bridge.ping()
    print(f"  {'OK' if ok else 'FAIL'}  {msg}")
    print("\n[CHECK] GROQ_API_KEY")
    print(f"  {'OK' if GROQ_KEY else 'MISSING'}  {GROQ_KEY[:8]+'...' if GROQ_KEY else 'export GROQ_API_KEY'}")
    print("\n[CHECK] MeTTa files")
    for fname in ["knowledge_base.metta", "market_state.metta", "risk_hierarchy.metta", "main_logic.metta"]:
        path = METTA_DIR / fname
        print(f"  {'OK' if path.exists() else 'MISSING'}  metta/{fname}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crypto ACO")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--query", type=str)
    parser.add_argument("--check", action="store_true")
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
