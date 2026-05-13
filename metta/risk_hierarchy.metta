; ============================================================
; CRYPTO ACO — RISK HIERARCHY ENGINE  (risk_hierarchy.metta)
; The Brain: recursive verification logic.
; Returns structured proof atoms, never bare True/False.
;
; Check order (first Denied short-circuits):
;   1  circuit-breaker      global market halt
;   2  daily-loss           portfolio down-day limit
;   3  trade-rate           hourly throttle
;   4  asset-risk           action allowed for this tier?
;   5  position-size        single trade cap
;   6  total-class-exposure correlation / concentration cap  [NEW]
;   7  liquidity            order vs 24h volume guard        [NEW]
;   8  divergence           LLM hype vs API trend conflict   [NEW]
;   9  sentiment            warn when buying into bad vibes
; ============================================================


; --- HELPER: resolve-risk-level --------------------------
; (resolve-risk-level BTC) → Low
; Unknown asset falls back to Critical for safety.

; Single definition — a duplicate second rule caused pettaSH to
; non-terminate (infinite / unbounded search), tripping the 30s bridge timeout.
(= (resolve-risk-level $asset)
   (let $classes (collapse (match &self (AssetClass $asset $c) $c))
     (if (== $classes ())
       Critical
       (let* (($class (once (match &self (AssetClass $asset $c) $c)))
              ($level (once (match &self (BaseRisk $class $l) $l))))
         $level))))


; --- HELPER: get-max-position ----------------------------
(= (get-max-position $level)
   (once (match &self (MaxPositionPct $level $pct) $pct)))


; --- HELPER: action-permitted? ---------------------------
(= (action-permitted? $action $level)
   (let $found (collapse (match &self (ActionAllowed $action $level) True))
     (if (== $found ()) False True)))


; --- HELPER: sum-exposure-by-level -----------------------
; Adds up all current holdings that share the same risk level.
; Used by the total-class-exposure check.
; e.g. (sum-exposure-by-level High) → 3.0 + 4.0 = 7.0
; collapse returns a list; we need numeric sum via fold pattern.

; Portfolio tier totals live in market_state.metta as (CurrentExposure <tier> <pct>).
; Computing sums inside MeTTa with collapse + foldl-atom was pathologically slow in PeTTa.
(= (sum-exposure-by-level $level)
   (once (match &self (CurrentExposure $level $sum) $sum)))


; --- CHECK 1: Global Circuit Breaker ---------------------
; Denies ALL trades (buy and sell) if market is in Panic or Shutdown.

(= (check-circuit-breaker)
   (let $state (once (match &self (GlobalMarketState $s) $s))
     (if (or (== $state Panic) (== $state Shutdown))
       (Denied circuit-breaker $state)
       Allowed)))


; --- CHECK 2: Daily Loss Limit ---------------------------
; Halts Buy orders when portfolio PnL falls below -DailyLossLimit%.

(= (check-daily-loss $action)
   (let* (($pnl   (once (match &self (DailyPnL $p) $p)))
          ($limit (once (match &self (CircuitBreakerThreshold DailyLossLimit $l) $l))))
     (if (and (== $action Buy) (< $pnl (* -1.0 $limit)))
       (Denied daily-loss-limit $pnl)
       Allowed)))


; --- CHECK 3: Trade Rate Throttle ------------------------
; Caps trades per hour to prevent overtrading.

(= (check-trade-rate)
   (let* (($count (once (match &self (TradesThisHour $n) $n)))
          ($limit (once (match &self (CircuitBreakerThreshold MaxTradesPerHour $l) $l))))
     (if (>= $count $limit)
       (Denied trade-rate-throttle $count)
       Allowed)))


; --- CHECK 4: Asset Risk Class Gate ----------------------
; Looks up ActionAllowed table. Critical assets block Buy entirely.
; Unknown assets default to Critical via resolve-risk-level fallback.

(= (check-asset-risk $action $asset)
   (let* (($level     (resolve-risk-level $asset))
          ($permitted (action-permitted? $action $level)))
     (if (== $level Critical)
       (Denied unknown-or-critical $asset)
       (if $permitted
         Allowed
         (Denied action-blocked $action $level)))))


; --- CHECK 5: Single-Asset Position Size Limit -----------
; Enforces MaxPositionPct per risk level for opening risk (Buy/Swap).
; Hold/Sell are not new long exposure — skip (otherwise LLM "all in" + Hold
; hits the Low-tier cap and looks like "denied for low risk").

(= (check-position-size $action $asset $req-pct)
   (if (or (== $action Hold) (== $action Sell))
     Allowed
     (let* (($level   (resolve-risk-level $asset))
            ($max-pct (get-max-position $level)))
       (if (> $req-pct $max-pct)
         (Denied position-too-large $req-pct $max-pct)
         Allowed))))


; --- CHECK 6: Total Class Exposure [GEMINI] --------------
; Ensures the user is not over-concentrated in one risk tier.
; Checks: (current holdings in tier) + req-pct <= MaxTotalClassExposure.
;
; Example denied case:
;   Holdings: LINK 3%, UNI 4% → DeFi total = 7%
;   MaxTotalClassExposure High = 15%
;   Request: Buy AAVE 10% → 7 + 10 = 17 > 15 → Denied

(= (check-total-exposure $action $asset $req-pct)
   (if (or (== $action Hold) (== $action Sell))
     Allowed
     (let* (($level        (resolve-risk-level $asset))
            ($current      (sum-exposure-by-level $level))
            ($limit        (once (match &self (MaxTotalClassExposure $level $l) $l)))
            ($after        (+ $current $req-pct)))
       (if (> $after $limit)
         (Denied total-class-exposure $level $after $limit)
         Allowed))))


; --- CHECK 7: Liquidity Guard [GEMINI] ------------------
; Rejects Buy orders whose USD value exceeds LiquidityGuardPct
; of the asset's 24h trading volume (prevents slippage).
;
; Order value = (req-pct / 100) * PortfolioBalance * AssetPrice
; But since we don't have a live price in MeTTa easily at query time,
; we use the stored AssetVolume24h directly.
; Condition: (req-pct / 100) * PortfolioBalance > LiquidityGuardPct/100 * Volume24h

(= (check-liquidity $action $asset $req-pct)
   (if (not (== $action Buy))
     Allowed
     (let* (($balance   (once (match &self (PortfolioBalance $b) $b)))
            ($vol24h    (once (match &self (AssetVolume24h $asset $v) $v)))
            ($guard-pct (once (match &self (LiquidityGuardPct $g) $g)))
            ($order-val (* (/ $req-pct 100.0) $balance))
            ($max-order (* (/ $guard-pct 100.0) $vol24h)))
       (if (> $order-val $max-order)
         (Denied low-liquidity $asset $order-val $max-order)
         Allowed))))


; --- CHECK 8: Divergence Sentinel [GEMINI] ---------------
; Detects when LLM-sourced sentiment (the "vibe") conflicts with
; the technical trend from CoinPaprika price data (the "math").
;
; Denied case: Sentiment = Pumping BUT Trend = Bearish
; This is the neuro-symbolic edge: symbols catch what LLMs miss.

(= (check-divergence $asset $action)
   (let* (($sentiment (once (match &self (AssetSentiment $asset $s) $s)))
          ($trend     (once (match &self (AssetTrend $asset $t) $t))))
     (if (and (== $action Buy)
              (and (== $sentiment Pumping) (== $trend Bearish)))
       (Denied sentiment-divergence $asset $sentiment $trend)
       Allowed)))


; --- CHECK 9: Sentiment Alignment ------------------------
; Softer check: warns (does not deny) when buying into
; Unfavourable market sentiment.

(= (check-sentiment $asset $action)
   (let* (($raw-s (once (match &self (AssetSentiment $asset $s) $s)))
          ($state (once (match &self (SentimentSignal $raw-s $st) $st))))
     (if (and (== $action Buy) (== $state Unfavourable))
       (Warned sentiment-unfavourable $raw-s)
       Allowed)))


; --- MASTER VERIFIER (step-chain) ------------------------
; Split into one function per step to avoid deep nesting,
; which some pettaSH versions struggle to evaluate.
; Each step calls the next only if the current check passes.

(= (verify-trade $action $asset $size-pct)
   (verify-step1 $action $asset $size-pct))

(= (verify-step1 $action $asset $size-pct)
   (let $r (check-circuit-breaker)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step2 $action $asset $size-pct))))

(= (verify-step2 $action $asset $size-pct)
   (let $r (check-daily-loss $action)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step3 $action $asset $size-pct))))

(= (verify-step3 $action $asset $size-pct)
   (let $r (check-trade-rate)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step4 $action $asset $size-pct))))

(= (verify-step4 $action $asset $size-pct)
   (let $r (check-asset-risk $action $asset)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step5 $action $asset $size-pct))))

(= (verify-step5 $action $asset $size-pct)
   (let $r (check-position-size $action $asset $size-pct)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step6 $action $asset $size-pct))))

(= (verify-step6 $action $asset $size-pct)
   (let $r (check-total-exposure $action $asset $size-pct)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step7 $action $asset $size-pct))))

(= (verify-step7 $action $asset $size-pct)
   (let $r (check-liquidity $action $asset $size-pct)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step8 $action $asset $size-pct))))

(= (verify-step8 $action $asset $size-pct)
   (let $r (check-divergence $asset $action)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r)
       (verify-step9 $action $asset $size-pct))))

(= (verify-step9 $action $asset $size-pct)
   (let $r (check-sentiment $asset $action)
     (if (not (== $r Allowed))
       (Verdict Warn $asset $action $r)
       (Verdict Allow $asset $action (size $size-pct)))))


; --- EXPLAIN-VERDICT -------------------------------------
; Translates a structured Verdict atom into a plain-English
; explanation string consumed by the LangChain adviser.

(= (explain-verdict (Verdict Allow $asset $action (size $pct)))
   (TradeApproved $asset $action $pct "All 9 checks passed."))

(= (explain-verdict (Verdict Deny $asset $action (Denied circuit-breaker $state)))
   (TradeDenied $asset $action "Global market is in Panic or Shutdown. No trades permitted until conditions stabilise."))

(= (explain-verdict (Verdict Deny $asset $action (Denied daily-loss-limit $pnl)))
   (TradeDenied $asset $action "Daily loss limit reached. Buy orders suspended to protect remaining capital."))

(= (explain-verdict (Verdict Deny $asset $action (Denied trade-rate-throttle $count)))
   (TradeDenied $asset $action "Hourly trade limit reached. Wait before placing another order."))

(= (explain-verdict (Verdict Deny $asset $action (Denied unknown-or-critical $asset)))
   (TradeDenied $asset $action "Asset is either unknown or classified as Critical risk. Buy orders are not permitted."))

(= (explain-verdict (Verdict Deny $asset $action (Denied action-blocked $act $level)))
   (TradeDenied $asset $action "This action is not permitted for the asset risk tier."))

(= (explain-verdict (Verdict Deny $asset $action (Denied position-too-large $req $max)))
   (TradeDenied $asset $action "Requested position exceeds the single-asset size limit for this risk tier."))

(= (explain-verdict (Verdict Deny $asset $action (Denied total-class-exposure $level $after $limit)))
   (TradeDenied $asset $action "Adding this trade would push total exposure in this risk tier above the portfolio concentration limit."))

(= (explain-verdict (Verdict Deny $asset $action (Denied low-liquidity $asset $order $max)))
   (TradeDenied $asset $action "Order value exceeds the liquidity guard threshold. This trade risks significant slippage."))

(= (explain-verdict (Verdict Deny $asset $action (Denied sentiment-divergence $asset $sentiment $trend)))
   (TradeDenied $asset $action "Sentiment signal says Pumping but price trend is Bearish. Hype-vs-math divergence detected."))

(= (explain-verdict (Verdict Warn $asset $action (Warned sentiment-unfavourable $sent)))
   (TradeWarned $asset $action "Market sentiment is unfavourable. Trade is permitted but proceed with caution."))


; --- PORTFOLIO RISK PROFILE ------------------------------
; Reads pre-computed (AssetRisk ...) facts from market_state.metta
; (written by market_feeder). The old collapse + nested match over
; every HoldingPct made the 4th file import effectively non-terminating.

(= (get-risk-profile)
   (collapse
     (match &self (AssetRisk $sym $class $level) (AssetRisk $sym $class $level))))


; ============================================================
; PUBLIC API (was main_logic.metta — merged to avoid a 4th
; import! pass that never completed under PeTTa on this project)
; ============================================================

(= (check-trade $action $asset $pct)
   (let $verdict (verify-trade $action $asset $pct)
     (explain-verdict $verdict)))

(= (asset-info $asset)
   (let* (($class (once (match &self (AssetClass $asset $c) $c)))
          ($level (once (match &self (BaseRisk $class $l) $l)))
          ($max   (once (match &self (MaxPositionPct $level $m) $m)))
          ($price (once (match &self (AssetPrice $asset $p) $p)))
          ($vol   (once (match &self (AssetVolatility $asset $v) $v)))
          ($sent  (once (match &self (AssetSentiment $asset $s) $s)))
          ($trend (once (match &self (AssetTrend $asset $t) $t))))
     (AssetInfo $asset $class $level $max $price $vol $sent $trend)))

(= (market-summary)
   (let* (($state   (once (match &self (GlobalMarketState $s) $s)))
          ($balance (once (match &self (PortfolioBalance $b) $b)))
          ($pnl     (once (match &self (DailyPnL $p) $p)))
          ($trades  (once (match &self (TradesThisHour $t) $t))))
     (MarketSummary $state $balance $pnl $trades)))

(= (portfolio-risk)
   (get-risk-profile))