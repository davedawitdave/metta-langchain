"""
langchain_pipeline.py — The 4-Step LangChain Pipeline (Groq / Llama).
══════════════════════════════════════════════════════════════════════
Implements the 4 steps from the assignment using FORMAL LangChain:

  STEP 1 ─ LLM-1: Intent Decomposer
            ChatGroq → identifies Subject, Action, Object from natural language
            → structured TradeIntent (Pydantic via with_structured_output)

  STEP 2 ─ MeTTa Verification (NOT an LLM — this is the guardrail)
            pettaSH subprocess → returns (TradeApproved|TradeDenied|TradeWarned)

  STEP 3 ─ LLM-2: Risk Analyst
            ChatGroq → reads the MeTTa verdict + asset context
            → writes a risk analysis paragraph before final decision

  STEP 4a ─ LLM-3: Compliance Reviewer (DENY path)
            ChatGroq → reviews denied trades and suggests legal alternatives

  STEP 4b ─ LLM-4: Trade Strategist (ALLOW/WARN path)
            ChatGroq → explains approval, caveats, execution tips

  STEP 5 ─ LLM-5: Final Summarizer
            ChatGroq → condenses all reasoning into the You/ACO chat answer

All LLM responses are logged step-by-step in chat style.
"""

import json
import re
from datetime import datetime
from typing import Literal, Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# PYDANTIC SCHEMA — maps 1:1 to MeTTa atom vocabulary
# ═══════════════════════════════════════════════════════════

class TradeIntent(BaseModel):
    """
    Structured extraction of a user's trading request.
    Fields map directly to MeTTa query: check-trade <action> <asset> <size_pct>
    """
    subject:    str = Field(description="Who is making the request. Usually 'user'.")
    action:     Literal["Buy", "Sell", "Swap", "Hold"] = Field(
                    description="Trading action. Buy/Sell/Swap/Hold.")
    asset:      str = Field(description="Crypto ticker symbol in UPPERCASE. E.g. BTC, ETH, SOL.")
    size_pct:   float = Field(
                    default=5.0, ge=0.0, le=100.0,
                    description="Portfolio percentage to trade. Default 5.0.")
    urgency:    Literal["High", "Normal", "Low"] = Field(
                    default="Normal",
                    description="Urgency level. High=FOMO/now, Normal=standard, Low=limit order.")
    raw_query:  str = Field(description="Original user message verbatim.")

    def to_metta_call(self) -> str:
        return f"check-trade {self.action} {self.asset} {self.size_pct}"

    def to_metta_atom(self) -> str:
        return (f"(TradeIntent (subject {self.subject}) (action {self.action})"
                f" (asset {self.asset}) (size {self.size_pct}) (urgency {self.urgency}))")

    def normalize(self):
        self.asset = self.asset.upper().strip()
        return self


from chat_logger import ChatLogger


# ═══════════════════════════════════════════════════════════
# THE PIPELINE
# ═══════════════════════════════════════════════════════════

class LangChainACOPipeline:
    """
    4-Step neuro-symbolic pipeline with 5 distinct LLM calls.

    Steps:
      LLM-1  Intent Decomposer  (Groq llama-3.3-70b-versatile)
      METTA  Symbolic Verifier  (pettaSH subprocess — NOT an LLM)
      LLM-2  Risk Analyst       (Groq llama-3.3-70b-versatile)
      LLM-3  Compliance Reviewer OR LLM-4 Trade Strategist (branch)
      LLM-5  Final Summarizer   (Groq llama-3.1-8b-instant — fast)
    """

    # Groq model names
    SMART_MODEL = "llama-3.3-70b-versatile"   # deep reasoning steps
    FAST_MODEL  = "llama-3.1-8b-instant"       # quick summary step

    def __init__(self, bridge, groq_api_key: str, temperature: float = 0.1):
        self.bridge = bridge
        self.log    = ChatLogger()
        self._key   = groq_api_key

        # LLM-1: Intent decomposer — needs structured output
        self._llm_smart = ChatGroq(
            model=self.SMART_MODEL,
            api_key=groq_api_key,
            temperature=temperature,
            max_retries=2,
        )

        # LLM-5: Fast summarizer
        self._llm_fast = ChatGroq(
            model=self.FAST_MODEL,
            api_key=groq_api_key,
            temperature=0.3,
            max_retries=2,
        )

        # Conversation memory for the session
        self._session_history: list = []

    # ─────────────────────────────────────────────────────────
    # MAIN ENTRY — process one user turn
    # ─────────────────────────────────────────────────────────

    def process(self, user_message: str) -> str:
        """
        Run the full 4-step pipeline for one user message.
        Returns the final ACO response string.
        Prints every step as a chat log.
        """
        ts = datetime.utcnow().strftime("%H:%M:%S")
        print(f"\n{'═'*60}")
        print(f"  🤖  CRYPTO ACO SESSION  ─  {ts} UTC")
        print(f"{'═'*60}")

        # ── STEP 1: Intent Decomposer (LLM-1) ────────────────
        intent = self._step1_intent(user_message)

        # ── STEP 2: MeTTa Symbolic Verification ──────────────
        verdict = self._step2_metta(intent)

        # ── STEP 3: Risk Analyst (LLM-2) ─────────────────────
        risk_analysis = self._step3_risk_analyst(intent, verdict)

        # ── STEP 4: Branch on verdict (LLM-3 or LLM-4) ───────
        branch_response = self._step4_branch(intent, verdict, risk_analysis)

        # ── STEP 5: Final Summarizer (LLM-5) → chat answer ───
        final = self._step5_summarize(user_message, intent, verdict,
                                       risk_analysis, branch_response)

        # Update session memory
        self._session_history.append(HumanMessage(content=user_message))
        self._session_history.append(AIMessage(content=final))

        # Final pretty chat output
        print(f"\n{'─'*60}")
        print(f"  You: {user_message}")
        print(f"  ACO: {final}")
        print(f"{'─'*60}\n")

        return final

    # ─────────────────────────────────────────────────────────
    # STEP 1: LLM-1 — Intent Decomposer
    # ─────────────────────────────────────────────────────────

    def _step1_intent(self, user_message: str) -> TradeIntent:
        """
        STEP 1 — LangChain Structured Output.
        Extracts Subject/Action/Object using with_structured_output + Pydantic.
        This is the formal LangChain way per the assignment.
        """
        self.log.user(
            user_message,
            step_label="STEP 1 — Intent Decomposer [LLM-1: llama-3.3-70b]"
        )

        # LangChain structured output: LLM fills the Pydantic schema
        structured_llm = self._llm_smart.with_structured_output(TradeIntent)

        system = SystemMessage(content=INTENT_SYSTEM_PROMPT)
        human  = HumanMessage(content=f'User message: "{user_message}"')
        intent: TradeIntent = structured_llm.invoke([system, human])
        intent.normalize()

        self.log.ai(
            f"Parsed intent:\n"
            f"  Subject: {intent.subject}\n"
            f"  Action:  {intent.action}\n"
            f"  Asset:   {intent.asset}\n"
            f"  Size:    {intent.size_pct}%\n"
            f"  Urgency: {intent.urgency}\n"
            f"  MeTTa:   {intent.to_metta_atom()}",
            model_tag="LLM-1 Intent"
        )
        return intent

    # ─────────────────────────────────────────────────────────
    # STEP 2: MeTTa Symbolic Verification (NOT an LLM)
    # ─────────────────────────────────────────────────────────

    def _step2_metta(self, intent: TradeIntent) -> dict:
        """
        STEP 2 — The Guardrail (pettaSH).
        Runs the recursive 7-check verify-trade function.
        This is the symbolic brain — no LLM involvement.
        """
        label = "STEP 2 — MeTTa Symbolic Verifier [pettaSH]"
        print(f"\n┌─ [{label}] ┐")

        metta_call = intent.to_metta_call()
        self.log.system(f"Sending to pettaSH: !({metta_call})")

        verdict = self.bridge.verify_trade(intent.action, intent.asset, intent.size_pct)

        self.log.metta(metta_call, verdict.get("raw", str(verdict)))
        self.log.verdict_banner(verdict["verdict"], intent.asset, intent.action)

        if verdict["reason"]:
            self.log.system(f"Reason: {verdict['reason']}")

        print(f"└{'─'*59}┘")
        return verdict

    # ─────────────────────────────────────────────────────────
    # STEP 3: LLM-2 — Risk Analyst
    # ─────────────────────────────────────────────────────────

    def _step3_risk_analyst(self, intent: TradeIntent, verdict: dict) -> str:
        """
        STEP 3 — Risk Analyst LLM.
        Reads the MeTTa verdict + market context.
        Writes a structured risk analysis (1 paragraph).
        This is a separate LangChain chain: prompt | llm | parser.
        """
        self.log.user(
            f"Analyze risk for: {intent.action} {intent.asset} "
            f"({intent.size_pct}%) | MeTTa: {verdict['verdict']} | "
            f"Reason: {verdict.get('reason','none')}",
            step_label="STEP 3 — Risk Analyst [LLM-2: llama-3.3-70b]"
        )

        # Build market context from bridge
        asset_data = self.bridge.asset_info(intent.asset)
        mkt        = self.bridge.market_summary()

        prompt = ChatPromptTemplate.from_messages([
            ("system", RISK_ANALYST_SYSTEM),
            ("human",  RISK_ANALYST_HUMAN),
        ])
        chain = prompt | self._llm_smart | StrOutputParser()

        analysis = chain.invoke({
            "action":       intent.action,
            "asset":        intent.asset,
            "size_pct":     intent.size_pct,
            "verdict":      verdict["verdict"],
            "metta_reason": verdict.get("reason", "N/A"),
            "asset_class":  asset_data.get("class", "Unknown"),
            "risk_level":   asset_data.get("risk", "Unknown"),
            "price":        asset_data.get("price", "N/A"),
            "volatility":   asset_data.get("volatility", "N/A"),
            "sentiment":    asset_data.get("sentiment", "N/A"),
            "market_state": mkt.get("state", "N/A"),
            "daily_pnl":    mkt.get("daily_pnl", "N/A"),
        })

        self.log.ai(analysis, model_tag="LLM-2 Risk")
        return analysis

    # ─────────────────────────────────────────────────────────
    # STEP 4: LLM-3 or LLM-4 — Compliance Reviewer / Strategist
    # ─────────────────────────────────────────────────────────

    def _step4_branch(
        self, intent: TradeIntent, verdict: dict, risk_analysis: str
    ) -> str:
        """
        STEP 4 — Branching based on MeTTa verdict.

        DENY/ERROR path → LLM-3: Compliance Reviewer
          Explains WHY it was blocked and suggests alternatives.

        ALLOW/WARN path → LLM-4: Trade Strategist
          Confirms the trade and provides execution guidance.

        Both are full LangChain chains with session memory context.
        """
        v = verdict["verdict"]

        if v in ("Deny", "Error"):
            return self._step4a_compliance_reviewer(intent, verdict, risk_analysis)
        else:
            return self._step4b_trade_strategist(intent, verdict, risk_analysis)

    def _step4a_compliance_reviewer(
        self, intent: TradeIntent, verdict: dict, risk_analysis: str
    ) -> str:
        """LLM-3: Compliance Reviewer (DENY path)."""
        self.log.user(
            f"DENIED: {intent.action} {intent.asset}. Reason: {verdict.get('reason','')}",
            step_label="STEP 4a — Compliance Reviewer [LLM-3: llama-3.3-70b]"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", COMPLIANCE_REVIEWER_SYSTEM),
            MessagesPlaceholder("history"),
            ("human",  COMPLIANCE_REVIEWER_HUMAN),
        ])
        chain = prompt | self._llm_smart | StrOutputParser()

        response = chain.invoke({
            "action":       intent.action,
            "asset":        intent.asset,
            "size_pct":     intent.size_pct,
            "metta_reason": verdict.get("reason", "Compliance rule violation."),
            "raw_verdict":  verdict.get("raw", ""),
            "risk_analysis": risk_analysis,
            "history":      self._session_history[-4:],  # last 2 turns context
        })

        self.log.ai(response, model_tag="LLM-3 Compliance")
        return response

    def _step4b_trade_strategist(
        self, intent: TradeIntent, verdict: dict, risk_analysis: str
    ) -> str:
        """LLM-4: Trade Strategist (ALLOW/WARN path)."""
        label = ("STEP 4b — Trade Strategist [LLM-4: llama-3.3-70b]"
                 + (" ⚠️  WITH WARNING" if verdict["verdict"] == "Warn" else ""))
        self.log.user(
            f"{verdict['verdict']}: {intent.action} {intent.asset} "
            f"({intent.size_pct}%). Providing strategy.",
            step_label=label
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", TRADE_STRATEGIST_SYSTEM),
            MessagesPlaceholder("history"),
            ("human",  TRADE_STRATEGIST_HUMAN),
        ])
        chain = prompt | self._llm_smart | StrOutputParser()

        response = chain.invoke({
            "action":       intent.action,
            "asset":        intent.asset,
            "size_pct":     intent.size_pct,
            "verdict":      verdict["verdict"],
            "metta_reason": verdict.get("reason", ""),
            "risk_analysis": risk_analysis,
            "urgency":      intent.urgency,
            "history":      self._session_history[-4:],
        })

        self.log.ai(response, model_tag="LLM-4 Strategy")
        return response

    # ─────────────────────────────────────────────────────────
    # STEP 5: LLM-5 — Final Summarizer
    # ─────────────────────────────────────────────────────────

    def _step5_summarize(
        self,
        user_message: str,
        intent: TradeIntent,
        verdict: dict,
        risk_analysis: str,
        branch_response: str,
    ) -> str:
        """
        STEP 5 — Final Summarizer.
        Condenses all reasoning into a single crisp You/ACO response.
        Uses the fast llama-3.1-8b-instant model.
        """
        self.log.user(
            "Synthesize final response for user.",
            step_label="STEP 5 — Final Summarizer [LLM-5: llama-3.1-8b]"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", SUMMARIZER_SYSTEM),
            ("human",  SUMMARIZER_HUMAN),
        ])
        chain = prompt | self._llm_fast | StrOutputParser()

        summary = chain.invoke({
            "user_message":    user_message,
            "verdict":         verdict["verdict"],
            "asset":           intent.asset,
            "action":          intent.action,
            "size_pct":        intent.size_pct,
            "metta_reason":    verdict.get("reason", ""),
            "risk_analysis":   risk_analysis[:500],   # truncate for token budget
            "branch_response": branch_response[:800],
        })

        self.log.ai(summary, model_tag="LLM-5 Final")
        return summary

    # ─────────────────────────────────────────────────────────
    # AUDIT + HISTORY
    # ─────────────────────────────────────────────────────────

    def get_chat_history(self) -> list[dict]:
        return self.log.export()

    def get_session_memory(self) -> list:
        return list(self._session_history)


# ═══════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# Keep these OUTSIDE the class to stay readable and editable.
# ═══════════════════════════════════════════════════════════

# ── LLM-1: Intent Decomposer ─────────────────────────────────
INTENT_SYSTEM_PROMPT = """You are a trade intent parser for a crypto trading compliance system.
Extract the Subject (who), Action (Buy/Sell/Swap/Hold), and Object (asset ticker) from the user's message.

Known asset tickers: BTC, ETH, SOL, ADA, AVAX, MATIC, ARB, OP, LINK, UNI, AAVE, USDT, USDC, DOGE, SHIB, PEPE

Mapping rules:
- action: buying/long/get in/acquire → Buy | selling/exit/dump → Sell | converting/swap → Swap | holding/HODL → Hold
- asset: "Bitcoin" → BTC, "Ethereum" → ETH, "Solana" → SOL, "Dogecoin" → DOGE. Unknown coin → UNKNOWN.
- size_pct: "all in" → 50.0 | "half" → 25.0 | "small" → 2.0 | "10%" → 10.0 | unspecified → 5.0
- urgency: FOMO/now/asap/immediately → High | default → Normal
- subject: always "user" unless specified otherwise

Return the structured TradeIntent object."""


# ── LLM-2: Risk Analyst ──────────────────────────────────────
RISK_ANALYST_SYSTEM = """You are a senior crypto risk analyst. Analyze the proposed trade and the MeTTa 
compliance engine's verdict. Be concise, factual, and objective. 2-3 sentences maximum."""

RISK_ANALYST_HUMAN = """Trade request: {action} {asset} ({size_pct}% of portfolio)
MeTTa verdict: {verdict} | Reason: {metta_reason}
Asset class: {asset_class} | Risk tier: {risk_level}
Current price: ${price} | Volatility: {volatility}% | Sentiment: {sentiment}
Market state: {market_state} | Daily PnL: {daily_pnl}%

Write a 2-3 sentence risk assessment of this trade, explaining the key risk factors."""

# ── LLM-3: Compliance Reviewer (DENY path) ───────────────────
COMPLIANCE_REVIEWER_SYSTEM = """You are the ACO (Algorithmic Compliance Officer). 
A trade has been DENIED by the MeTTa symbolic risk engine. Your job is to:
1. Explain clearly WHY the trade was blocked (reference the specific rule).
2. Suggest 1-2 concrete LEGAL alternatives the user could do instead.
3. Be firm but helpful. Never override the denial. 3-4 sentences."""

COMPLIANCE_REVIEWER_HUMAN = """DENIED trade: {action} {asset} ({size_pct}%)
MeTTa denial reason: {metta_reason}
Raw MeTTa atom: {raw_verdict}
Risk analysis: {risk_analysis}

Explain the denial and suggest alternatives. Remember: the denial is FINAL."""

# ── LLM-4: Trade Strategist (ALLOW/WARN path) ────────────────
TRADE_STRATEGIST_SYSTEM = """You are a crypto trade strategist. A trade has been APPROVED 
(or approved with a WARNING) by the MeTTa compliance engine. Your job is to:
1. Confirm the approval and state any warnings clearly.
2. Give 1-2 practical execution tips (timing, order type, etc.).
3. Keep it professional. 3-4 sentences."""

TRADE_STRATEGIST_HUMAN = """APPROVED trade ({verdict}): {action} {asset} ({size_pct}%)
MeTTa note: {metta_reason}
Risk analysis: {risk_analysis}
Urgency level: {urgency}

Confirm the trade approval and provide execution guidance."""

# ── LLM-5: Final Summarizer ──────────────────────────────────
SUMMARIZER_SYSTEM = """You are the final voice of the Crypto ACO system. Synthesize all analysis 
into ONE clear response the user will see. Format: 2-4 sentences. Start with the verdict icon:
✅ (approved) | 🚫 (denied) | ⚠️ (approved with warning). Be direct and informative."""

SUMMARIZER_HUMAN = """User asked: "{user_message}"

MeTTa verdict: {verdict} on {action} {asset} ({size_pct}%)
MeTTa reason: {metta_reason}
Risk analysis summary: {risk_analysis}
Detailed guidance: {branch_response}

Write the final 2-4 sentence ACO response. Start with the verdict icon."""
