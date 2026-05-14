; CRYPTO ACO — RISK HIERARCHY ENGINE (risk_hierarchy.metta)
; Recursive verification logic returning structured proof atoms.
;
; Checks: 1=circuit-breaker, 2=daily-loss, 3=trade-rate, 4=asset-risk,
; 5=position-size, 6=total-class-exposure, 7=liquidity, 8=divergence, 9=sentiment

; --- HELPERS ---

(= (resolve-risk-level $asset)
   (let $classes (collapse (match &self (AssetClass $asset $c) $c))
     (if (== $classes ()) Critical
       (let* (($class (once (match &self (AssetClass $asset $c) $c)))
              ($level (once (match &self (BaseRisk $class $l) $l))))
         $level))))

(= (get-max-position $level)
   (once (match &self (MaxPositionPct $level $pct) $pct)))

(= (action-permitted? $action $level)
   (if (== (collapse (match &self (ActionAllowed $action $level) True)) ())
     False True))

(= (sum-exposure-by-level $level)
   (once (match &self (CurrentExposure $level $sum) $sum)))

; --- CHECKS ---

(= (check-circuit-breaker)
   (let $state (once (match &self (GlobalMarketState $s) $s))
     (if (or (== $state Panic) (== $state Shutdown))
       (Denied circuit-breaker $state) Allowed)))

(= (check-daily-loss $action)
   (let* (($pnl (once (match &self (DailyPnL $p) $p)))
          ($limit (once (match &self (CircuitBreakerThreshold DailyLossLimit $l) $l))))
     (if (and (== $action Buy) (< $pnl (* -1.0 $limit)))
       (Denied daily-loss-limit $pnl) Allowed)))

(= (check-trade-rate)
   (let* (($count (once (match &self (TradesThisHour $n) $n)))
          ($limit (once (match &self (CircuitBreakerThreshold MaxTradesPerHour $l) $l))))
     (if (>= $count $limit) (Denied trade-rate-throttle $count) Allowed)))

(= (check-asset-risk $action $asset)
   (let* (($level (resolve-risk-level $asset))
          ($permitted (action-permitted? $action $level)))
     (if (== $level Critical) (Denied unknown-or-critical $asset)
       (if $permitted Allowed (Denied action-blocked $action $level)))))

(= (check-position-size $action $asset $req-pct)
   (if (or (== $action Hold) (== $action Sell)) Allowed
     (let* (($level (resolve-risk-level $asset))
            ($max-pct (get-max-position $level)))
       (if (> $req-pct $max-pct)
         (Denied position-too-large $req-pct $max-pct) Allowed))))

(= (check-total-exposure $action $asset $req-pct)
   (if (or (== $action Hold) (== $action Sell)) Allowed
     (let* (($level (resolve-risk-level $asset))
            ($current (sum-exposure-by-level $level))
            ($limit (once (match &self (MaxTotalClassExposure $level $l) $l)))
            ($after (+ $current $req-pct)))
       (if (> $after $limit)
         (Denied total-class-exposure $level $after $limit) Allowed))))

(= (check-liquidity $action $asset $req-pct)
   (if (not (== $action Buy)) Allowed
     (let* (($balance (once (match &self (PortfolioBalance $b) $b)))
            ($vol24h (once (match &self (AssetVolume24h $asset $v) $v)))
            ($guard-pct (once (match &self (LiquidityGuardPct $g) $g)))
            ($order-val (* (/ $req-pct 100.0) $balance))
            ($max-order (* (/ $guard-pct 100.0) $vol24h)))
       (if (> $order-val $max-order)
         (Denied low-liquidity $asset $order-val $max-order) Allowed))))

(= (check-divergence $asset $action)
   (let* (($sentiment (once (match &self (AssetSentiment $asset $s) $s)))
          ($trend (once (match &self (AssetTrend $asset $t) $t))))
     (if (and (== $action Buy) (and (== $sentiment Pumping) (== $trend Bearish)))
       (Denied sentiment-divergence $asset $sentiment $trend) Allowed)))

(= (check-sentiment $asset $action)
   (let* (($raw-s (once (match &self (AssetSentiment $asset $s) $s)))
          ($state (once (match &self (SentimentSignal $raw-s $st) $st))))
     (if (and (== $action Buy) (== $state Unfavourable))
       (Warned sentiment-unfavourable $raw-s) Allowed)))

; --- VERIFICATION CHAIN ---
; Split to avoid deep nesting that symbolic engine versions struggle with.

(= (verify-trade $action $asset $size-pct)
   (verify-step1 $action $asset $size-pct))

(= (verify-step1 $action $asset $size-pct)
   (let $r (check-circuit-breaker)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step2 $action $asset $size-pct))))

(= (verify-step2 $action $asset $size-pct)
   (let $r (check-daily-loss $action)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step3 $action $asset $size-pct))))

(= (verify-step3 $action $asset $size-pct)
   (let $r (check-trade-rate)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step4 $action $asset $size-pct))))

(= (verify-step4 $action $asset $size-pct)
   (let $r (check-asset-risk $action $asset)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step5 $action $asset $size-pct))))

(= (verify-step5 $action $asset $size-pct)
   (let $r (check-position-size $action $asset $size-pct)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step6 $action $asset $size-pct))))

(= (verify-step6 $action $asset $size-pct)
   (let $r (check-total-exposure $action $asset $size-pct)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step7 $action $asset $size-pct))))

(= (verify-step7 $action $asset $size-pct)
   (let $r (check-liquidity $action $asset $size-pct)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step8 $action $asset $size-pct))))

(= (verify-step8 $action $asset $size-pct)
   (let $r (check-divergence $asset $action)
     (if (not (== $r Allowed))
       (Verdict Deny $asset $action $r) (verify-step9 $action $asset $size-pct))))

(= (verify-step9 $action $asset $size-pct)
   (let $r (check-sentiment $asset $action)
     (if (not (== $r Allowed))
       (Verdict Warn $asset $action $r) (Verdict Allow $asset $action (size $size-pct)))))

; --- VERDICT EXPLANATION ---

(= (explain-verdict (Verdict Allow $asset $action (size $pct)))
   (TradeApproved $asset $action $pct "All checks passed."))

(= (explain-verdict (Verdict Deny $asset $action (Denied circuit-breaker $state)))
   (TradeDenied $asset $action "Market is in Panic/Shutdown. No trades allowed."))

(= (explain-verdict (Verdict Deny $asset $action (Denied daily-loss-limit $pnl)))
   (TradeDenied $asset $action "Daily loss limit reached."))

(= (explain-verdict (Verdict Deny $asset $action (Denied trade-rate-throttle $count)))
   (TradeDenied $asset $action "Hourly trade limit reached."))

(= (explain-verdict (Verdict Deny $asset $action (Denied unknown-or-critical $asset)))
   (TradeDenied $asset $action "Asset is unknown or Critical risk. Buys not permitted."))

(= (explain-verdict (Verdict Deny $asset $action (Denied action-blocked $act $level)))
   (TradeDenied $asset $action "Action not permitted for this risk tier."))

(= (explain-verdict (Verdict Deny $asset $action (Denied position-too-large $req $max)))
   (TradeDenied $asset $action "Position exceeds single-asset size limit."))

(= (explain-verdict (Verdict Deny $asset $action (Denied total-class-exposure $level $after $limit)))
   (TradeDenied $asset $action "Total tier exposure would exceed portfolio limit."))

(= (explain-verdict (Verdict Deny $asset $action (Denied low-liquidity $asset $order $max)))
   (TradeDenied $asset $action "Order value exceeds liquidity guard. High slippage risk."))

(= (explain-verdict (Verdict Deny $asset $action (Denied sentiment-divergence $asset $sentiment $trend)))
   (TradeDenied $asset $action "Hype/math divergence: Sentiment pumping but trend bearish."))

(= (explain-verdict (Verdict Warn $asset $action (Warned sentiment-unfavourable $sent)))
   (TradeWarned $asset $action "Market sentiment unfavourable. Proceed with caution."))

; --- PUBLIC API ---

(= (get-risk-profile)
   (collapse (match &self (AssetRisk $sym $class $level) (AssetRisk $sym $class $level))))

(= (check-trade $action $asset $pct)
   (let $verdict (verify-trade $action $asset $pct)
     (explain-verdict $verdict)))

(= (asset-info $asset)
   (let* (($class (once (match &self (AssetClass $asset $c) $c)))
          ($level (once (match &self (BaseRisk $class $l) $l)))
          ($max (once (match &self (MaxPositionPct $level $m) $m)))
          ($price (once (match &self (AssetPrice $asset $p) $p)))
          ($vol (once (match &self (AssetVolatility $asset $v) $v)))
          ($sent (once (match &self (AssetSentiment $asset $s) $s)))
          ($trend (once (match &self (AssetTrend $asset $t) $t))))
     (AssetInfo $asset $class $level $max $price $vol $sent $trend)))

(= (market-summary)
   (let* (($state (once (match &self (GlobalMarketState $s) $s)))
          ($balance (once (match &self (PortfolioBalance $b) $b)))
          ($pnl (once (match &self (DailyPnL $p) $p)))
          ($trades (once (match &self (TradesThisHour $t) $t))))
     (MarketSummary $state $balance $pnl $trades)))

(= (portfolio-risk)
   (collapse (match &self (AssetRisk $sym $class $level) (AssetRisk $sym $class $level))))
