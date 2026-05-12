; ============================================================
; CRYPTO ACO — RISK HIERARCHY ENGINE (risk_hierarchy.metta)
; THE BRAIN: Recursive 7-check verification logic.
; pettaSH evaluates this via import from the runner script.
; Returns structured proof atoms — not bare True/False.
; ============================================================


; ─── HELPER: resolve-risk-level ──────────────────────────────
(= (resolve-risk-level $asset)
   (let* (($class (once (match &self (AssetClass $asset $c) $c)))
          ($level (once (match &self (BaseRisk $class $l) $l))))
     $level))

; Fallback: unknown asset → Critical
(= (resolve-risk-level $asset)
   (let $known (collapse (match &self (AssetClass $asset $_) True))
     (if (== $known ()) Critical $known)))


; ─── HELPER: get-max-position ────────────────────────────────
(= (get-max-position $level)
   (once (match &self (MaxPositionPct $level $pct) $pct)))


; ─── HELPER: action-permitted? ───────────────────────────────
(= (action-permitted? $action $level)
   (let $found (collapse (match &self (ActionAllowed $action $level) True))
     (if (== $found ()) False True)))


; ─── CHECK 1: Global Circuit Breaker ─────────────────────────
(= (check-circuit-breaker)
   (let $state (match &self (GlobalMarketState $s) $s)
     (if (or (== $state Panic) (== $state Shutdown))
       (Denied circuit-breaker $state)
       Allowed)))


; ─── CHECK 2: Daily Loss Limit ───────────────────────────────
(= (check-daily-loss $action)
   (let* (($pnl    (match &self (DailyPnL $p) $p))
          ($limit  (match &self (CircuitBreakerThreshold DailyLossLimit $l) $l))
          ($breach (< $pnl (* -1.0 $limit))))
     (if (and (== $action Buy) $breach)
       (Denied daily-loss-limit $pnl)
       Allowed)))


; ─── CHECK 3: Trade Rate Throttle ────────────────────────────
(= (check-trade-rate)
   (let* (($count (match &self (TradesThisHour $n) $n))
          ($limit (match &self (CircuitBreakerThreshold MaxTradesPerHour $l) $l)))
     (if (>= $count $limit)
       (Denied trade-rate-throttle $count)
       Allowed)))


; ─── CHECK 4: Asset Risk Class Gate ─────────────────────────
(= (check-asset-risk $action $asset)
   (let* (($level     (resolve-risk-level $asset))
          ($permitted (action-permitted? $action $level)))
     (if (== $level Critical)
       (Denied unknown-asset $asset)
       (if $permitted
         Allowed
         (Denied action-blocked $action $level)))))


; ─── CHECK 5: Position Size Limit ────────────────────────────
(= (check-position-size $asset $req-pct)
   (let* (($level   (resolve-risk-level $asset))
          ($max-pct (get-max-position $level)))
     (if (>= $req-pct 100.0)
       (Denied position-too-large $req-pct $max-pct)
       (if (> $req-pct $max-pct)
         (Denied position-too-large $req-pct $max-pct)
         Allowed))))


; ─── CHECK 6: Volatility Sentinel ────────────────────────────
(= (check-volatility $asset $action)
   (let* (($vol   (match &self (AssetVolatility $asset $v) $v))
          ($limit (match &self (CircuitBreakerThreshold VolatilityIndex $l) $l)))
     (if (and (> $vol $limit) (== $action Buy))
       (Denied excessive-volatility $vol)
       Allowed)))


; ─── CHECK 7: Sentiment Alignment ────────────────────────────
(= (check-sentiment $asset $action)
   (let* (($raw-s (match &self (AssetSentiment $asset $s) $s))
          ($state (match &self (SentimentSignal $raw-s $st) $st)))
     (if (and (== $action Buy) (== $state Unfavourable))
       (Warned sentiment-unfavourable $raw-s)
       Allowed)))


; ─── MASTER VERIFIER ─────────────────────────────────────────
; Hierarchy: Circuit Breaker → Daily Loss → Rate → Asset Risk
;            → Position Size → Volatility → Sentiment
; First Denied short-circuits. Returns structured proof atom.
; Simplified for PeTTa compatibility - less nesting

(= (verify-trade-step1 $action $asset $size-pct)
   (let $cb (check-circuit-breaker)
     (if (not (== $cb Allowed))
       (Verdict Deny $asset $action $cb)
       (verify-trade-step2 $action $asset $size-pct))))

(= (verify-trade-step2 $action $asset $size-pct)
   (let $dl (check-daily-loss $action)
     (if (not (== $dl Allowed))
       (Verdict Deny $asset $action $dl)
       (verify-trade-step3 $action $asset $size-pct))))

(= (verify-trade-step3 $action $asset $size-pct)
   (let $tr (check-trade-rate)
     (if (not (== $tr Allowed))
       (Verdict Deny $asset $action $tr)
       (verify-trade-step4 $action $asset $size-pct))))

(= (verify-trade-step4 $action $asset $size-pct)
   (let $ar (check-asset-risk $action $asset)
     (if (not (== $ar Allowed))
       (Verdict Deny $asset $action $ar)
       (verify-trade-step5 $action $asset $size-pct))))

(= (verify-trade-step5 $action $asset $size-pct)
   (let $ps (check-position-size $asset $size-pct)
     (if (not (== $ps Allowed))
       (Verdict Deny $asset $action $ps)
       (verify-trade-step6 $action $asset $size-pct))))

(= (verify-trade-step6 $action $asset $size-pct)
   (let $vl (check-volatility $asset $action)
     (if (not (== $vl Allowed))
       (Verdict Deny $asset $action $vl)
       (verify-trade-step7 $action $asset $size-pct))))

(= (verify-trade-step7 $action $asset $size-pct)
   (let $sn (check-sentiment $asset $action)
     (if (not (== $sn Allowed))
       (Verdict Warn $asset $action $sn)
       (Verdict Allow $asset $action (size $size-pct)))))

(= (verify-trade $action $asset $size-pct)
   (verify-trade-step1 $action $asset $size-pct))


; ─── EXPLAIN-VERDICT ─────────────────────────────────────────
; Returns a structured explanation atom consumed by the LangChain formatter.

(= (explain-verdict (Verdict Allow $asset $action (size $pct)))
   (TradeApproved $asset $action $pct "All 7 risk checks passed."))

(= (explain-verdict (Verdict Deny $asset $action (Denied unknown-asset $asset)))
   (TradeDenied $asset $action "UNKNOWN ASSET: Asset not recognized in knowledge base. Only known assets can be traded."))

(= (explain-verdict (Verdict Deny $asset $action (Denied circuit-breaker $state)))
   (TradeDenied $asset $action "GLOBAL HALT: Market state is Panic/Shutdown. No trades permitted."))

(= (explain-verdict (Verdict Deny $asset $action (Denied daily-loss-limit $pnl)))
   (TradeDenied $asset $action "DAILY LOSS LIMIT BREACH: Portfolio down beyond safe threshold. Buy suspended."))

(= (explain-verdict (Verdict Deny $asset $action (Denied trade-rate-throttle $count)))
   (TradeDenied $asset $action "TRADE THROTTLE: Maximum trades per hour reached. Cool-down required."))

(= (explain-verdict (Verdict Deny $asset $action (Denied action-blocked $act $level)))
   (TradeDenied $asset $action "RISK CLASS BLOCK: Action not permitted for this asset risk tier."))

(= (explain-verdict (Verdict Deny $asset $action (Denied position-too-large $req $max)))
   (TradeDenied $asset $action "POSITION SIZE BREACH: Requested size exceeds maximum allowed for this tier."))
(= (explain-verdict (Verdict Deny $asset $action (Denied position-too-large $req $max)))
   (TradeDenied $asset $action "FULL PORTFOLIO: Cannot allocate 100% to single asset. Maximum is 50% for any position."))

(= (explain-verdict (Verdict Deny $asset $action (Denied excessive-volatility $vol)))
   (TradeDenied $asset $action "VOLATILITY HALT: Asset volatility exceeds safety threshold. Wait for stabilisation."))

(= (explain-verdict (Verdict Warn $asset $action (Warned sentiment-unfavourable $sent)))
   (TradeWarned $asset $action "SENTIMENT ALERT: Market sentiment is unfavourable. Trade permitted but proceed cautiously."))


; ─── PORTFOLIO RISK PROFILE ──────────────────────────────────
(= (get-risk-profile)
   (collapse
     (let* (($sym   (match &self (HoldingPct $s $_) $s))
            ($class (match &self (AssetClass $sym $c) $c))
            ($level (match &self (BaseRisk $class $l) $l)))
       (AssetRisk $sym $class $level))))
