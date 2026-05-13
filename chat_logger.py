"""
chat_logger.py
Step-by-step pipeline logger.
Prints plain text for internal steps.
Emojis appear ONLY in the final ACO answer line.
No external dependencies.
"""


class ChatLogger:
    """
    Logs every pipeline step to stdout in a readable chat format.

    Internal steps (Steps 1-3) use plain text headers.
    The final You/ACO exchange uses the verdict icons (approved/denied/warned).
    History is stored for audit export.
    """

    def __init__(self):
        self.history: list[dict] = []
        self._step = 0

    # --- step headers ----------------------------------------

    def step_header(self, label: str) -> None:
        """Print a plain-text section divider."""
        self._step += 1
        width = 60
        pad   = max(0, width - len(label) - 6)
        print(f"\n[{label}]{'-' * pad}")
        self.history.append({"role": "step", "label": label})

    # --- You/ACO lines ---------------------------------------

    def user_says(self, text: str) -> None:
        print(f"  You : {text}")
        self.history.append({"role": "user", "content": text})

    def llm_says(self, text: str, tag: str = "LLM") -> None:
        """Print LLM output. Multi-line text is indented cleanly."""
        lines = text.strip().split("\n")
        print(f"  {tag} : {lines[0]}")
        for ln in lines[1:]:
            print(f"         {ln}")
        self.history.append({"role": "assistant", "tag": tag, "content": text})

    # --- MeTTa step ------------------------------------------

    def metta_query(self, expr: str, result: str) -> None:
        print(f"  query: !({expr})")
        print(f"  result: {result}")
        self.history.append({"role": "metta", "query": expr, "result": result})

    def metta_verdict(self, verdict: str, asset: str, action: str) -> None:
        """Print the MeTTa verdict in plain text — no icons here."""
        v = (verdict or "").strip()
        if v not in ("Allow", "Deny", "Warn", "Error"):
            v = f"{v} (unexpected — check PeTTa output parsing)"
        print(f"  verdict: {v.upper()} — {action} {asset}")
        if verdict.lower() == "deny":
            print(f"  -> trade blocked by symbolic engine")
        elif verdict.lower() == "warn":
            print(f"  -> trade approved with caution flag")
        else:
            print(f"  -> trade cleared")

    def system_note(self, text: str) -> None:
        print(f"  note: {text}")
        self.history.append({"role": "system", "content": text})

    # --- Final answer ----------------------------------------

    def final_answer(self, user_message: str, response: str, verdict: str) -> None:
        """
        Print the final You/ACO exchange.
        Only here do we use verdict icons for clarity.
        """
        icon_map = {"Allow": "[APPROVED]", "Warn": "[WARNING]", "Deny": "[DENIED]"}
        icon = icon_map.get(verdict, "[RESULT]")
        print(f"\n{'=' * 60}")
        print(f"  You : {user_message}")
        print(f"  ACO {icon}: {response}")
        print(f"{'=' * 60}\n")
        self.history.append({"role": "final", "verdict": verdict,
                              "user": user_message, "aco": response})

    # --- Export ----------------------------------------------

    def export(self) -> list[dict]:
        return list(self.history)
        