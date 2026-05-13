; ============================================================
; CRYPTO ACO — MAIN LOGIC (stub)
; Public API rules now live at the end of risk_hierarchy.metta
; so the Python bridge only needs three import! passes (PeTTa
; was hanging on a fourth import of this file).
;
; Composite runner (same as metta_bridge._build_script):
;   !(import! &self "knowledge_base.metta")
;   !(import! &self "market_state.metta")
;   !(import! &self "risk_hierarchy.metta")
;   !(check-trade Buy BTC 5.0)
; ============================================================
