; ============================================================
; CRYPTO ACO — MAIN LOGIC (main_logic.metta)
; Public API definitions — used when running pettaSH directly.
; The Python bridge builds composite scripts inline instead of
; using this file, but this lets you test MeTTa standalone:
;
;   petta sh metta/main_logic.metta
;   Then type: !(check-trade Buy BTC 5.0)
; ============================================================

; NOTE: When using pettaSH REPL directly, load deps first:
;   !(import! &self "metta/knowledge_base.metta")
;   !(import! &self "metta/market_state.metta")
;   !(import! &self "metta/risk_hierarchy.metta")


; ─── PUBLIC API ──────────────────────────────────────────────

; check-trade: main entry point
; (check-trade <action> <asset> <pct>) → TradeApproved | TradeDenied | TradeWarned
(= (check-trade $action $asset $pct)
   (let $verdict (verify-trade $action $asset $pct)
     (explain-verdict $verdict)))


; asset-info: full metadata for one asset
(= (asset-info $asset)
   (let* (($class (once (match &self (AssetClass $asset $c) $c)))
          ($level (once (match &self (BaseRisk $class $l) $l)))
          ($max   (once (match &self (MaxPositionPct $level $m) $m)))
          ($price (once (match &self (AssetPrice $asset $p) $p)))
          ($vol   (once (match &self (AssetVolatility $asset $v) $v)))
          ($sent  (once (match &self (AssetSentiment $asset $s) $s)))
          ($trend (once (match &self (AssetTrend $asset $t) $t))))
     (AssetInfo $asset $class $level $max $price $vol $sent $trend)))


; market-summary: global state snapshot
(= (market-summary)
   (let* (($state   (once (match &self (GlobalMarketState $s) $s)))
          ($balance (once (match &self (PortfolioBalance $b) $b)))
          ($pnl     (once (match &self (DailyPnL $p) $p)))
          ($trades  (once (match &self (TradesThisHour $t) $t))))
     (MarketSummary $state $balance $pnl $trades)))


; portfolio-risk: risk profile for all held assets
(= (portfolio-risk)
   (get-risk-profile))


; ─── QUICK-TEST QUERIES (uncomment in pettaSH REPL) ──────────
; !(check-trade Buy BTC 5.0)        → TradeApproved
; !(check-trade Buy PEPE 10.0)      → TradeDenied (Critical)
; !(check-trade Buy ETH 50.0)       → TradeDenied (size)
; !(check-trade Sell DOGE 5.0)      → TradeApproved (sell always ok)
; !(check-trade Buy USDC 30.0)      → TradeApproved (Safe)
; !(asset-info SOL)
; !(market-summary)
; !(portfolio-risk)
