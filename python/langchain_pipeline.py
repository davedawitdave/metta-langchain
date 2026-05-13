"""
langchain_pipeline.py — 3-LLM ACO Pipeline (Groq / Llama).

Step 1  LLM-1: Intent Parser
        ChatGroq with_structured_output(TradeIntent)
        Extracts Subject / Action / Object from natural language.
        -> TradeIntent (Pydantic)

Step 2  MeTTa Symbolic Verifier  [NOT an LLM]
        PeTTa subprocess runs the 9-check verify-trade chain.
        -> verdict dict  (Allow | Deny | Warn)

Step 3  LLM-2: Adviser
        Single LLM that does both risk analysis AND guidance.
        DENY  -> explains the block + suggests alternatives.
        ALLOW -> confirms + gives execution tips.
        WARN  -> confirms with caution note.
        Uses MessagesPlaceholder for session memory.
        -> adviser_response string

Step 4  LLM-3: Final Answer
        Condenses Step 3 into one clean You/ACO sentence.
        -> final string shown to user

Total LLM calls per turn: 3.
"""

from datetime import datetime
from typing import Literal

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from chat_logger import ChatLogger


# ============================================================
# PYDANTIC SCHEMA — maps 1:1 to MeTTa atom vocabulary
# ============================================================

class TradeIntent(BaseModel):
    """
    Structured output from LLM-1.
    Fields feed directly into the MeTTa query:
        check-trade <action> <asset> <size_pct>
    """
    subject:   str = Field(description="Who is requesting. Usually 'user'.")
    action:    Literal["Buy", "Sell", "Swap", "Hold"] = Field(
                   description="Buy | Sell | Swap | Hold")
    asset:     str = Field(description="Ticker in UPPERCASE. E.g. BTC, ETH.")
    size_pct:  float = Field(
                   default=5.0, ge=0.0, le=100.0,
                   description="Portfolio percent to trade. Default 5.0.")
    urgency:   Literal["High", "Normal", "Low"] = Field(
                   default="Normal",
                   description="High=FOMO/now. Normal=standard. Low=limit.")
    raw_query: str = Field(description="Original user message, verbatim.")

    def to_metta_call(self) -> str:
        return f"check-trade {self.action} {self.asset} {self.size_pct}"

    def to_atom(self) -> str:
        return (f"(TradeIntent (subject {self.subject})"
                f" (action {self.action}) (asset {self.asset})"
                f" (size {self.size_pct}) (urgency {self.urgency}))")

    def normalize(self) -> "TradeIntent":
        self.asset = self.asset.upper().strip()
        return self


# ============================================================
# PIPELINE
# ============================================================

class LangChainACOPipeline:

    MODEL     = "llama-3.3-70b-versatile"   # Steps 1, 2
    MODEL_FAST = "llama-3.1-8b-instant"     # Step 3 (final sentence)

    def __init__(self, bridge, groq_api_key: str, temperature: float = 0.1):
        self.bridge  = bridge
        self.log     = ChatLogger()
        self._llm    = ChatGroq(model=self.MODEL,      api_key=groq_api_key,
                                temperature=temperature, max_retries=2)
        self._llm_f  = ChatGroq(model=self.MODEL_FAST, api_key=groq_api_key,
                                temperature=0.3,         max_retries=2)
        self._memory: list = []   # LangChain message history for session context

    # --------------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------------

    def process(self, user_message: str) -> str:
        # Check if query is related to trading (buy/sell/hold/swap)
        trading_keywords = ["buy", "sell", "hold", "swap"]
        is_trading_query = any(kw in user_message.lower() for kw in trading_keywords)
        
        if not is_trading_query:
            # For unrelated questions, return raw LLM output with "You:" prefix
            response = self._llm.invoke([
                SystemMessage(content="You are a helpful crypto assistant. Answer directly and concisely."),
                HumanMessage(content=user_message),
            ])
            raw_answer = response.content if hasattr(response, 'content') else str(response)
            final = f"You: {raw_answer}"
            self._memory.append(HumanMessage(content=user_message))
            self._memory.append(AIMessage(content=final))
            return final
        
        # For trading queries, run full ACO pipeline
        ts = datetime.utcnow().strftime("%H:%M:%S UTC")
        print(f"\n{'=' * 60}\n  CRYPTO ACO  {ts}\n{'=' * 60}")

        intent   = self._step1_parse_intent(user_message)
        verdict  = self._step2_metta_verify(intent)
        advice   = self._step3_adviser(intent, verdict)
        final    = self._step4_final_answer(user_message, intent, verdict, advice)

        self._memory.append(HumanMessage(content=user_message))
        self._memory.append(AIMessage(content=final))
        self.log.final_answer(user_message, final, verdict["verdict"])
        return final

    # --------------------------------------------------------
    # STEP 1:
    # --------------------------------------------------------
    # STEP 1: LLM-1 — Intent Parser
    # --------------------------------------------------------

    def _step1_parse_intent(self, user_message: str) -> TradeIntent:
        self.log.step_header("STEP 1  Intent Parser  [LLM-1: llama-3.3-70b]")
        self.log.user_says(user_message)

        structured = self._llm.with_structured_output(TradeIntent)
        intent: TradeIntent = structured.invoke([
            SystemMessage(content=PROMPT_INTENT),
            HumanMessage(content=f'Parse: "{user_message}"'),
        ])
        intent.normalize()

        self.log.llm_says(
            f"subject={intent.subject}  action={intent.action}  "
            f"asset={intent.asset}  size={intent.size_pct}%  urgency={intent.urgency}\n"
            f"metta atom: {intent.to_atom()}",
            tag="LLM-1"
        )
        return intent

    # --------------------------------------------------------
    # STEP 2: MeTTa Symbolic Verifier  [NOT an LLM]
    # --------------------------------------------------------

    def _step2_metta_verify(self, intent: TradeIntent) -> dict:
        self.log.step_header("STEP 2  MeTTa Symbolic Verifier  [PeTTa]")

        call    = intent.to_metta_call()
        verdict = self.bridge.verify_trade(intent.action, intent.asset, intent.size_pct)

        self.log.metta_query(call, verdict.get("raw", str(verdict)))
        self.log.metta_verdict(verdict["verdict"], intent.asset, intent.action)
        if verdict.get("reason"):
            self.log.system_note(f"reason: {verdict['reason']}")

        return verdict

    # --------------------------------------------------------
    # STEP 3: LLM-2 — Adviser (risk analysis + guidance combined)
    # --------------------------------------------------------

    def _step3_adviser(self, intent: TradeIntent, verdict: dict) -> str:
        """
        Single LLM that handles both paths:
        - DENY  : explain block + suggest alternatives
        - ALLOW : confirm + execution tips
        - WARN  : confirm with caution
        Uses session memory via MessagesPlaceholder.
        """
        self.log.step_header("STEP 3  Adviser  [LLM-2: llama-3.3-70b]")

        asset_data = self.bridge.asset_info(intent.asset)
        mkt        = self.bridge.market_summary()

        prompt = ChatPromptTemplate.from_messages([
            ("system", PROMPT_ADVISER_SYSTEM),
            MessagesPlaceholder("history"),
            ("human", PROMPT_ADVISER_HUMAN),
        ])
        chain  = prompt | self._llm | StrOutputParser()

        response = chain.invoke({
            "action":       intent.action,
            "asset":        intent.asset,
            "size_pct":     intent.size_pct,
            "urgency":      intent.urgency,
            "verdict":      verdict["verdict"],
            "metta_reason": verdict.get("reason", "N/A"),
            "asset_class":  asset_data.get("class", "Unknown"),
            "risk_level":   asset_data.get("risk",  "Unknown"),
            "price":        asset_data.get("price", "N/A"),
            "volatility":   asset_data.get("volatility", "N/A"),
            "sentiment":    asset_data.get("sentiment",  "N/A"),
            "trend":        asset_data.get("trend",      "N/A"),
            "market_state": mkt.get("state",     "N/A"),
            "daily_pnl":    mkt.get("daily_pnl", "N/A"),
            "history":      self._memory[-4:],   # last 2 turns for context
        })

        self.log.llm_says(response, tag="LLM-2")
        return response

    # --------------------------------------------------------
    # STEP 4: LLM-3 — Final Answer (1-2 sentences for the user)
    # --------------------------------------------------------

    def _step4_final_answer(
        self,
        user_message: str,
        intent: TradeIntent,
        verdict: dict,
        advice: str,
    ) -> str:
        self.log.step_header("STEP 4  Final Answer  [LLM-3: llama-3.1-8b]")

        prompt = ChatPromptTemplate.from_messages([
            ("system", PROMPT_FINAL_SYSTEM),
            ("human",  PROMPT_FINAL_HUMAN),
        ])
        chain  = prompt | self._llm_f | StrOutputParser()

        final = chain.invoke({
            "user_message": user_message,
            "verdict":      verdict["verdict"],
            "asset":        intent.asset,
            "action":       intent.action,
            "metta_reason": verdict.get("reason", ""),
            "advice":       advice[:600],
        })

        self.log.llm_says(final, tag="LLM-3")
        return final

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    def get_chat_history(self) -> list[dict]:
        return self.log.export()

    def get_session_memory(self) -> list:
        return list(self._memory)


# ============================================================
# PROMPT TEMPLATES
# Kept outside the class so they are easy to read and edit.
# ============================================================

# LLM-1: Intent Parser
PROMPT_INTENT = """\
You are a trade intent parser for a crypto compliance system.
Extract Subject, Action, and Object from the user's message.

Known tickers: BTC ETH SOL ADA AVAX MATIC ARB OP LINK UNI AAVE USDT USDC DOGE SHIB PEPE

Rules:
- action  : buy/long/acquire -> Buy | sell/exit/dump -> Sell | swap/convert -> Swap | hold/hodl -> Hold
- asset   : "Bitcoin" -> BTC, "Ethereum" -> ETH, "Solana" -> SOL, "Dogecoin" -> DOGE, unknown -> UNKNOWN
- size_pct: "all in" -> 50.0 | "half" -> 25.0 | "small" -> 2.0 | "10%" -> 10.0 | not stated -> 5.0
- urgency : fomo/now/asap -> High | default -> Normal
- subject : always "user" unless stated otherwise

Return the TradeIntent object.\
"""

# LLM-2: Adviser (handles DENY and ALLOW/WARN in one prompt)
PROMPT_ADVISER_SYSTEM = """\
You are the ACO (Algorithmic Compliance Officer) adviser.
The MeTTa symbolic engine has already made the decision. Your job is to explain it.

If verdict is DENY  : explain clearly which rule blocked the trade and suggest 1-2 alternatives.
If verdict is ALLOW : confirm approval and give 1-2 practical execution tips.
If verdict is WARN  : confirm approval but explain the caution clearly.

The MeTTa verdict is exactly one of: Allow | Deny | Warn. The asset risk tier (e.g. Low) describes how risky the asset class is, not whether the trade was denied—never treat "Low" tier as a denial by itself.

Rules:
- Never override the MeTTa decision.
- Be concise: 3-5 sentences.
- No bullet points. Plain prose.
- Do not repeat the verdict icon — the final formatter will add it.\
"""

PROMPT_ADVISER_HUMAN = """\
Trade : {action} {asset} ({size_pct}% of portfolio)  urgency={urgency}
MeTTa verdict : {verdict}
MeTTa reason  : {metta_reason}
Asset class   : {asset_class}  risk tier : {risk_level}
Price $: {price}  volatility: {volatility}%  sentiment: {sentiment}  trend: {trend}
Market state  : {market_state}  daily PnL: {daily_pnl}%

Write your adviser response.\
"""

# LLM-3: Final Answer
PROMPT_FINAL_SYSTEM = """\
You are the final voice of the ACO system.
Condense the adviser's response into 1-3 clear sentences the user will read directly.

Verdict icons to START with (use only one):
  ALLOW -> [APPROVED]
  DENY  -> [DENIED]
  WARN  -> [WARNING]

No additional formatting. Plain sentences only.\
"""

PROMPT_FINAL_HUMAN = """\
User asked : "{user_message}"
MeTTa verdict : {verdict} on {action} {asset}
MeTTa reason  : {metta_reason}
Adviser guidance : {advice}

Write the final 1-3 sentence response starting with the verdict icon.\
"""