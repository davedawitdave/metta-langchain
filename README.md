# Crypto ACO — Algorithmic Compliance Officer
**MeTTa + LangChain + Groq — Neuro-Symbolic Trading Guardrail**

Separates **trading requests** (full 4-step pipeline with symbolic verification) from **unrelated questions** (direct LLM answer).


### Prerequisites
- Python 3.10+
- Symbolic interpreter (PeTTa) + GROQ_API_KEY

### Setup (5 Steps)

**1. Install symbolic interpreter**
```bash
git clone https://github.com/trueagi-io/PeTTa
cd metta-wam && make install
petta --version   # verify
```

**2. Clone and install Python deps**
```bash
cd /path/to/metta-langchain
pip install -r requirements.txt
```

**3. Configure API**
```bash
export GROQ_API_KEY="gsk_..."        # Get free key at console.groq.com
export PETTA_CMD="petta"              # Optional if not in PATH
```

**4. Verify setup**
```bash
python main.py --check
```

**5. Run**
```bash
python main.py              # Interactive chat
python main.py --demo       # 7 demo scenarios
python main.py --query "buy 5% BTC"
```

---

## How It Works

### The 4-Step Pipeline

**Phase I: Intent Parsing (LLM)**
- User input → llama-3.3-70b → TradeIntent struct (action, asset, size)

**Phase II: Symbolic Verification (NO LLM)**
- MeTTa engine checks 9 rules → Verdict (Allow/Deny/Warn)
- Checks: circuit-breaker, daily-loss, trade-rate, asset-risk, position-size, total-exposure, liquidity, divergence, sentiment

**Phase III: Explanation (LLM)**
- Risk Analyst explains why verdict was reached

**Phase IV: Final Summary (LLM)**
- Condenses to 1-3 sentence user response

---

## The 9 Checks (risk_hierarchy.metta)

| # | Check | Denies when |
|---|-------|-------------|
| 1 | circuit-breaker | Market in Panic/Shutdown |
| 2 | daily-loss | Portfolio down > DailyLossLimit% |
| 3 | trade-rate | Trades/hour >= MaxTradesPerHour |
| 4 | asset-risk | Asset not in ActionAllowed table |
| 5 | position-size | Requested% > tier max |
| 6 | total-exposure | Tier holdings + request > tier limit |
| 7 | liquidity | Order value > 25% of 24h volume |
| 8 | divergence | Sentiment=Pumping AND trend=Bearish |
| 9 | sentiment | Unfavourable mood → WARN (not deny) |

First `(Denied ...)` short-circuits. All pass = `Allow`.


## Example Prompts

**Should ALLOW**
```
buy 5% BTC
buy 4% LINK
sell half my Bitcoin
swap 30% to USDC
```

**Should DENY**
```
FOMO into PEPE 10%        (Critical asset, blocked)
buy DOGE 2%               (Critical, blocked)
all in on ETH 50%         (exceeds 20% cap)
buy 15% LINK              (DeFi tier max is 15%)
```

**Unrelated (Direct LLM, no symbolic check)**
```
How does blockchain work?
What's the difference between BTC and ETH?
Explain DeFi
```

---

## REPL Commands

```
<message>        Full ACO pipeline
portfolio        Risk snapshot from MeTTa
audit            Export audit_log.json
history          This session's log
help             Show commands
quit             Exit
```

---

## Symbolic Direct Testing (No Python)

```bash
petta sh metta/main_logic.metta

!(import! &self "metta/knowledge_base.metta")
!(import! &self "metta/market_state.metta")
!(import! &self "metta/risk_hierarchy.metta")

!(check-trade Buy BTC 5.0)      ; → TradeApproved
!(check-trade Buy PEPE 10.0)    ; → TradeDenied
!(asset-info SOL)
!(market-summary)
```


## Project Structure

```
metta-langchain/
├── metta/
│   ├── knowledge_base.metta    Static rules, thresholds, asset classes
│   ├── market_state.metta      Dynamic state (prices, sentiment)
│   ├── risk_hierarchy.metta    9-check verification engine
│   └── main_logic.metta        Public API
├── python/
│   ├── metta_bridge.py         Subprocess runner + parser
│   ├── langchain_pipeline.py   LLM orchestration
│   └── market_feeder.py        Live data → MeTTa atoms
├── tests/
│   └── test_pipeline.py        No live API needed
├── main.py                     REPL entry point
└── requirements.txt
```

---

## Extending

**Add a new asset**
```metta
(AssetClass NEWCOIN Layer2)     ; Inherits Medium risk
```

**Add a custom check**
```metta
(= (check-custom-rule $asset)
   (if (expensive-rule $asset) (Denied custom-rule $asset) Allowed))
```

**Simulate market conditions**
```metta
(GlobalMarketState Panic)       ; All buys blocked
```

**Adjust limits**
```metta
(MaxPositionPct Low 15)         ; Reduce BTC max to 15%
```


## Why Symbolic + LLM (not either alone)

| Aspect | LLM only | Symbolic only | This system |
|--------|----------|---------------|------------|
| **Natural language** | ✅ | ❌ | ✅ |
| **Hard rules** | ❌ hallucinate | ✅ | ✅ |
| **Audit trail** | ❌ opaque | ✅ | ✅ |
| **Fast** | ❌ LLM per step | ✅ | ✅ symbolic gates LLM |
| **Extend easily** | Redeploy | Add atom | Add atom |
| **Live data** | Manual | Manual | Auto |

---

## Troubleshooting

**Symbolic not found**
```bash
export PETTA_CMD="/full/path/to/petta"
python main.py --check
```

**GROQ_API_KEY missing**
```bash
export GROQ_API_KEY="gsk_..."
python main.py --check
```

**MeTTa files not found**
- Verify `metta/*.metta` files exist
- Run: `python main.py --check`


## References

- **Symbolic (MeTTa)**: https://github.com/trueagi-io/metta-wam
- **LangChain**: https://langchain.com
- **Groq**: https://console.groq.com
- **PeTTa repo**: https://github.com/trueagi-io/PeTTa

