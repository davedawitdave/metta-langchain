; ============================================================
; CRYPTO ACO — KNOWLEDGE BASE (knowledge_base.metta)
; "The Law": Static facts, asset taxonomy, and hard rules.
; Loaded by pettaSH via: !(import! &self "path/knowledge_base.metta")
; ============================================================


; ─── SECTION 1: ASSET TAXONOMY ───────────────────────────────
(AssetClass BTC  Layer1)
(AssetClass ETH  Layer1)
(AssetClass SOL  Layer1)
(AssetClass ADA  Layer1)
(AssetClass AVAX Layer1)
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


; ─── SECTION 2: RISK HIERARCHY ───────────────────────────────
; Meme > DeFi > Layer2 > Layer1 > Stablecoin
(BaseRisk Meme       Critical)
(BaseRisk Unverified Critical)
(BaseRisk DeFi       High)
(BaseRisk Layer2     Medium)
(BaseRisk Layer1     Low)
(BaseRisk Stablecoin Safe)


; ─── SECTION 3: VERIFICATION REQUIREMENTS ────────────────────
(VerifyLevel Critical 5)
(VerifyLevel High     3)
(VerifyLevel Medium   2)
(VerifyLevel Low      1)
(VerifyLevel Safe     0)


; ─── SECTION 4: POSITION LIMITS ─────────────────────────────
(MaxPositionPct Critical 0)
(MaxPositionPct High     5)
(MaxPositionPct Medium   10)
(MaxPositionPct Low      20)
(MaxPositionPct Safe     50)


; ─── SECTION 5: CIRCUIT BREAKER THRESHOLDS ───────────────────
(CircuitBreakerThreshold MarketCapDrop24h    15.0)
(CircuitBreakerThreshold VolatilityIndex      5.0)
(CircuitBreakerThreshold DailyLossLimit      10.0)
(CircuitBreakerThreshold MaxTradesPerHour     6)


; ─── SECTION 6: ALLOWED ACTIONS ─────────────────────────────
; Buy on Critical is intentionally ABSENT → always Denied.
(ActionAllowed Buy    Safe)
(ActionAllowed Buy    Low)
(ActionAllowed Buy    Medium)
(ActionAllowed Buy    High)
(ActionAllowed Sell   Safe)
(ActionAllowed Sell   Low)
(ActionAllowed Sell   Medium)
(ActionAllowed Sell   High)
(ActionAllowed Sell   Critical)
(ActionAllowed Swap   Safe)
(ActionAllowed Swap   Low)
(ActionAllowed Swap   Medium)


; ─── SECTION 7: SENTIMENT-TO-STATE MAPPING ───────────────────
(SentimentSignal Bullish   Favourable)
(SentimentSignal Bearish   Unfavourable)
(SentimentSignal Neutral   Uncertain)
(SentimentSignal Panic     Unfavourable)
(SentimentSignal FOMOing   Unfavourable)
(SentimentSignal Crashing  Unfavourable)
(SentimentSignal Pumping   Favourable)
(SentimentSignal Dumping   Unfavourable)
(SentimentSignal Volatile  Uncertain)
