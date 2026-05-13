; ============================================================
; CRYPTO ACO — KNOWLEDGE BASE  (knowledge_base.metta)
; The Law: all static rules live here. Nothing changes at
; runtime. Python never encodes rules — only reads atoms.
; ============================================================


; --- SECTION 1: ASSET TAXONOMY ---------------------------
; (AssetClass <ticker> <class>)
; class: Layer1 | Layer2 | DeFi | Stablecoin | Meme

(AssetClass BTC   Layer1)
(AssetClass ETH   Layer1)
(AssetClass SOL   Layer1)
(AssetClass ADA   Layer1)
(AssetClass AVAX  Layer1)
(AssetClass MATIC Layer2)
(AssetClass ARB   Layer2)
(AssetClass OP    Layer2)
(AssetClass LINK  DeFi)
(AssetClass UNI   DeFi)
(AssetClass AAVE  DeFi)
(AssetClass USDT  Stablecoin)
(AssetClass USDC  Stablecoin)
(AssetClass DOGE  Meme)
(AssetClass SHIB  Meme)
(AssetClass PEPE  Meme)


; --- SECTION 2: RISK HIERARCHY ---------------------------
; Meme > DeFi > Layer2 > Layer1 > Stablecoin
; Each class maps to a risk level used throughout checks.

(BaseRisk Meme       Critical)
(BaseRisk Unverified Critical)
(BaseRisk DeFi       High)
(BaseRisk Layer2     Medium)
(BaseRisk Layer1     Low)
(BaseRisk Stablecoin Safe)


; --- SECTION 3: SINGLE-ASSET POSITION LIMITS -------------
; (MaxPositionPct <risk-level> <max-percent-of-portfolio>)
; Hard cap per trade. Buy on Critical = 0 = always denied.

(MaxPositionPct Critical 0)
(MaxPositionPct High     5)
(MaxPositionPct Medium   10)
(MaxPositionPct Low      20)
(MaxPositionPct Safe     50)


; --- SECTION 4: TOTAL CLASS EXPOSURE LIMITS --------------
; (MaxTotalClassExposure <risk-level> <max-total-percent>)
; Gemini suggestion: prevent correlation risk.
; Even if one trade is small, total in that tier may be too high.
;
; Example: user has 8% in LINK + 4% in UNI = 12% DeFi total.
; MaxTotalClassExposure High = 15, so 4% more DeFi is allowed.
; But 8% more would be denied (12 + 8 = 20 > 15).
 
(MaxTotalClassExposure Critical 0)
(MaxTotalClassExposure High     15)
(MaxTotalClassExposure Medium   25)
(MaxTotalClassExposure Low      60)
(MaxTotalClassExposure Safe     80)


; --- SECTION 5: CIRCUIT BREAKER THRESHOLDS --------------
; (CircuitBreakerThreshold <condition> <limit>)

(CircuitBreakerThreshold VolatilityIndex    5.0)   ; % per day -> halt buys
(CircuitBreakerThreshold DailyLossLimit    10.0)   ; % portfolio loss -> halt buys
(CircuitBreakerThreshold MaxTradesPerHour   6)     ; count -> throttle


; --- SECTION 6: LIQUIDITY GUARD THRESHOLD ---------------
; (LiquidityGuardPct <pct>)
; An order may not exceed this % of the asset's 24h volume.
; Prevents slippage and price manipulation.
; e.g. 1.0 = order must be < 1% of 24h volume in USD.

(LiquidityGuardPct 1.0)


; --- SECTION 7: ALLOWED ACTIONS -------------------------
; Buy on Critical is intentionally absent — always Denied.
; Sell is allowed on all tiers (exit positions freely).
; Swap allowed only up to Medium risk.

(ActionAllowed Buy  Safe)
(ActionAllowed Buy  Low)
(ActionAllowed Buy  Medium)
(ActionAllowed Buy  High)
(ActionAllowed Sell Safe)
(ActionAllowed Sell Low)
(ActionAllowed Sell Medium)
(ActionAllowed Sell High)
(ActionAllowed Sell Critical)
(ActionAllowed Swap Safe)
(ActionAllowed Swap Low)
(ActionAllowed Swap Medium)

; Hold = no new trade; must be allowed at every tier (like staying flat).
(ActionAllowed Hold Safe)
(ActionAllowed Hold Low)
(ActionAllowed Hold Medium)
(ActionAllowed Hold High)
(ActionAllowed Hold Critical)


; --- SECTION 8: SENTIMENT-TO-STATE MAPPING ---------------
; Maps raw sentiment words from market_feeder → abstract states
; used by divergence and sentiment checks.

(SentimentSignal Bullish   Favourable)
(SentimentSignal Pumping   Favourable)
(SentimentSignal Neutral   Uncertain)
(SentimentSignal Volatile  Uncertain)
(SentimentSignal Bearish   Unfavourable)
(SentimentSignal Panic     Unfavourable)
(SentimentSignal FOMOing   Unfavourable)
(SentimentSignal Crashing  Unfavourable)
(SentimentSignal Dumping   Unfavourable)