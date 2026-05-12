# Crypto ACO — Algorithmic Compliance Officer
### MeTTa (pettaSH) + LangChain + Groq/Llama — Neuro-Symbolic Trading Guardrail

---

## The 4-Step Pipeline (Zigzag Layout)

```
Phase I — Intent Capture (L → R)
────────────────────────────────────────────────────────────────
 User           LLM-1                        TradeIntent
 "FOMO into  →  Intent Decomposer         →  (subject user)
  PEPE 10%"     ChatGroq llama-3.3-70b        (action Buy)
                with_structured_output         (asset PEPE)
                Subject / Action / Object      (size 10.0)
                                               (urgency High)

                              ↓
Phase II — Symbolic Verification (R ← L)
────────────────────────────────────────────────────────────────
 (Verdict Deny   ←  risk_hierarchy.metta  ←  MeTTaBridge
  PEPE Buy           7-check recursive        pettaSH
  action-blocked)    verify-trade             subprocess
                     BRAIN: no LLM here       temp .metta file

                              ↓
Phase III — LLM Reasoning (L → R)
────────────────────────────────────────────────────────────────
 LLM-2              LLM-3 or LLM-4           LLM-5
 Risk Analyst   →   Compliance Reviewer  →   Final Summarizer
 ChatGroq           (DENY path)              ChatGroq
 llama-3.3-70b      or Trade Strategist      llama-3.1-8b
 asset context      (ALLOW/WARN path)        2-4 sentence
 market state       ChatGroq                 You/ACO answer
                    llama-3.3-70b

                              ↓
Final Chat Output
────────────────────────────────────────────────────────────────
 You: FOMO into PEPE with 10%
 ACO: 🚫 Trade blocked. PEPE is classified as a Meme coin...
```

---

## The 5 LangChain LLM Calls

| Step | LLM | Role | LangChain API |
|------|-----|------|---------------|
| 1 | llama-3.3-70b | **Intent Decomposer** — extracts Subject/Action/Object | `with_structured_output(TradeIntent)` |
| — | *pettaSH* | **Symbolic Verifier** — recursive 7-check rule engine | subprocess (NOT an LLM) |
| 2 | llama-3.3-70b | **Risk Analyst** — reads MeTTa verdict + market context | `prompt \| llm \| StrOutputParser()` |
| 3 | llama-3.3-70b | **Compliance Reviewer** (DENY path) — explains block + alternatives | `prompt \| llm \| StrOutputParser()` |
| 4 | llama-3.3-70b | **Trade Strategist** (ALLOW/WARN path) — execution guidance | `prompt \| llm \| StrOutputParser()` |
| 5 | llama-3.1-8b | **Final Summarizer** — condenses into chat answer | `prompt \| llm \| StrOutputParser()` |

---

## Project Structure

```
crypto_aco/
├── metta/                          ← 80% of logic — all in MeTTa
│   ├── knowledge_base.metta        ← Static rules: taxonomy, limits, thresholds
│   ├── market_state.metta          ← Dynamic: live prices, sentiment (auto-written)
│   ├── risk_hierarchy.metta        ← THE BRAIN: recursive 7-check verifier
│   └── main_logic.metta            ← Public API + pettaSH REPL entry point
│
├── python/                         ← 20% adapter code
│   ├── metta_bridge.py             ← pettaSH subprocess runner + S-expr parser
│   ├── langchain_pipeline.py       ← 5 LangChain LLM calls + ChatLogger
│   ├── market_feeder.py            ← CoinPaprika + Groq sentiment → MeTTa atoms
│
├── tests/
│   └── test_pipeline.py            ← All tests (no live API required)
│
├── main.py                         ← Chat REPL orchestrator
└── requirements.txt
```

---

## Setup

### Step 1 — Install pettaSH (MeTTa interpreter)
```bash
# Option A: metta-wam (recommended)
git clone https://github.com/trueagi-io/metta-wam
cd metta-wam && make install
petta --version   # verify

# Option B: if petta is at a custom path
export PETTA_CMD=/path/to/petta
```

### Step 2 — Install Python dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Set API keys
```bash
export GROQ_API_KEY="gsk_..."       # required — get free at console.groq.com
# PETTA_CMD defaults to "petta" — override if needed
export PETTA_CMD="petta"
```

### Step 4 — Verify setup
```bash
python main.py --check
```

### Step 5 — Run
```bash
python main.py              # interactive chat REPL (default)
python main.py --demo       # 7 automated test scenarios
python main.py --query "buy 5% BTC"   # single query
```

---

## What the Chat Looks Like

Every request shows all 5 pipeline steps, then the final You/ACO answer:

```
════════════════════════════════════════════════════════════
  🤖  CRYPTO ACO SESSION  ─  14:32:07 UTC
════════════════════════════════════════════════════════════

┌─ [STEP 1 — Intent Decomposer [LLM-1: llama-3.3-70b]] ────┐
│ You: FOMO into PEPE with 10%, it's about to moon!
│ ACO [LLM-1 Intent]: Parsed intent:
│   Subject: user
│   Action:  Buy
│   Asset:   PEPE
│   Size:    10.0%
│   Urgency: High
│   MeTTa:   (TradeIntent (subject user) (action Buy) ...)
└───────────────────────────────────────────────────────────┘

┌─ [STEP 2 — MeTTa Symbolic Verifier [pettaSH]] ────────────┐
│ [SYS] Sending to pettaSH: !(check-trade Buy PEPE 10.0)
│ [MeTTa] !(  check-trade Buy PEPE 10.0  )
│ [MeTTa] ←   (TradeDenied PEPE Buy "RISK CLASS BLOCK...")
│
│  🚫  METTA VERDICT: DENY  ─  Buy PEPE
│
│ [SYS] Reason: RISK CLASS BLOCK: Action not permitted for Critical.
└───────────────────────────────────────────────────────────┘

┌─ [STEP 3 — Risk Analyst [LLM-2: llama-3.3-70b]] ──────────┐
│ You: Analyze risk for: Buy PEPE (10%) | MeTTa: Deny
│ ACO [LLM-2 Risk]: PEPE is classified as a Critical-tier Meme
│   coin with no fundamental utility. Its price is driven
│   entirely by speculative sentiment, making a 10% allocation
│   extremely high risk.
└───────────────────────────────────────────────────────────┘

┌─ [STEP 4a — Compliance Reviewer [LLM-3: llama-3.3-70b]] ──┐
│ You: DENIED: Buy PEPE. Reason: RISK CLASS BLOCK...
│ ACO [LLM-3 Compliance]: The ACO has blocked this trade
│   because PEPE is a Critical-risk Meme asset. Alternatives:
│   1) Consider SOL or ETH (Low risk, up to 20% size).
│   2) If you want meme exposure, reduce size to 0% — it is
│   not permitted at any size under current rules.
└───────────────────────────────────────────────────────────┘

┌─ [STEP 5 — Final Summarizer [LLM-5: llama-3.1-8b]] ───────┐
│ You: Synthesize final response for user.
│ ACO [LLM-5 Final]: Condensing all analysis...
└───────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────
  You: FOMO into PEPE with 10%, it's about to moon!
  ACO: 🚫 PEPE is a Critical-tier Meme coin — Buy orders are
       permanently blocked regardless of size. The ACO denied
       this trade based on asset risk classification. Consider
       Layer1 assets like SOL or ETH instead.
────────────────────────────────────────────────────────────
```

---

## REPL Commands

```
<your message>   →  Full 4-step pipeline
portfolio        →  Portfolio risk snapshot from MeTTa
audit            →  Export audit_log.json
history          →  Print this session's step-by-step log
help             →  Show this list
quit             →  Exit
```

---

## Example Prompts to Try

### Trade Requests
```
buy 5% BTC
buy 10% Solana
I want to get into Ethereum, about 3%
sell half my Bitcoin
convert 30% to USDC
swap my ETH for USDC
put 20% into AVAX
acquire some Cardano
buy 2% Chainlink
exit my MATIC position
```

### Should Be DENIED (by MeTTa)
```
FOMO into PEPE with 10%
buy some Dogecoin, just 2%
get me into SHIB
all in on ETH — 50% now
buy 6% LINK                    (DeFi max is 5%)
buy 15% ARB                    (Layer2 max is 10%)
```

### Should Be APPROVED
```
buy 5% BTC
buy 4% LINK
buy 9% MATIC
sell any amount of any asset
convert 30% to USDC
buy 50% USDT
```

### Should Be WARNED (sentiment)
```
buy 3% ETH                     (if ETH sentiment = Bearish)
buy some Solana                (if SOL sentiment = Dumping)
```

### Market Analysis Questions
```
what's the current risk level of my portfolio?
is it safe to buy BTC right now?
what's the maximum I can buy of ETH?
explain why PEPE is blocked
what assets can I buy with 10%?
show me the market state
```

### Complex / Multi-step
```
I want to de-risk — what should I do?
should I buy the dip on ETH or wait?
I have FOMO on SOL — help me think through this
what's a safe way to get more crypto exposure?
I need to hedge my BTC position
```

---

## The 7 MeTTa Checks (risk_hierarchy.metta)

| # | Check | Triggers on |
|---|-------|-------------|
| 1 | `check-circuit-breaker` | `GlobalMarketState = Panic\|Shutdown` |
| 2 | `check-daily-loss` | `DailyPnL < -DailyLossLimit%` |
| 3 | `check-trade-rate` | `TradesThisHour >= MaxTradesPerHour` |
| 4 | `check-asset-risk` | `ActionAllowed` table miss |
| 5 | `check-position-size` | `requested% > MaxPositionPct[risk_level]` |
| 6 | `check-volatility` | `AssetVolatility > VolatilityIndex threshold` |
| 7 | `check-sentiment` | `SentimentSignal = Unfavourable` (WARN only) |

First check that returns `(Denied ...)` short-circuits the chain. All 7 must return `Allowed` for approval.

---

## pettaSH Direct Testing

You can test the MeTTa logic without running Python at all:

```bash
# Start pettaSH REPL
petta sh metta/main_logic.metta

# Then at the REPL:
!(import! &self "metta/knowledge_base.metta")
!(import! &self "metta/market_state.metta")
!(import! &self "metta/risk_hierarchy.metta")

# Run queries
!(check-trade Buy BTC 5.0)       ; → TradeApproved
!(check-trade Buy PEPE 10.0)     ; → TradeDenied
!(check-trade Buy ETH 50.0)      ; → TradeDenied (size)
!(check-trade Sell DOGE 5.0)     ; → TradeApproved (sell always ok)
!(asset-info SOL)
!(market-summary)
!(portfolio-risk)
```

---

## Extending the System

### Add a new asset (MeTTa only — no Python)
```metta
; In knowledge_base.metta:
(AssetClass NEW_COIN Layer2)     ; inherits Medium risk automatically
```

### Add a custom rule
```metta
; In risk_hierarchy.metta:
(= (check-news-volume $asset)
   (let $sig (match &self (NewsSentiment $asset Strong $_) Strong)
     (if (== $sig Strong) Allowed (Warned low-news-signal $asset))))
; Then add to verify-trade chain...
```

### Simulate market panic (edit market_state.metta)
```metta
(GlobalMarketState Panic)        ; all Buy orders blocked immediately
```

### Change position limits (knowledge_base.metta)
```metta
(MaxPositionPct Low 15)          ; tighten BTC/ETH max from 20% to 15%
```

---

## Why pettaSH + LangChain (not one or the other)

| Concern | LangChain alone | MeTTa alone | This system |
|---------|----------------|-------------|-------------|
| **Natural language** | ✅ | ❌ | ✅ LLM parses/explains |
| **Hard rules** | ❌ hallucination risk | ✅ | ✅ MeTTa enforces |
| **Auditability** | ❌ opaque | ✅ proof atoms | ✅ structured verdict |
| **Rule extension** | Redeploy code | Add one atom | Add one atom |
| **Speed** | Slow (LLM every step) | Fast (symbolic) | Fast (MeTTa gates LLM) |
| **Live data** | Manual | Manual | Auto via feeder |
