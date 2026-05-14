"""Pipeline logger — outputs plain text with verdict flags."""

class ChatLogger:
    """Logs pipeline steps and chat history."""

    def __init__(self):
        self.history = []
        self._step = 0

    def step_header(self, label):
        """Print section divider."""
        self._step += 1
        width = 60
        pad = max(0, width - len(label) - 6)
        print(f"\n[{label}]{'-' * pad}")
        self.history.append({"role": "step", "label": label})

    def user_says(self, text):
        print(f"  You : {text}")
        self.history.append({"role": "user", "content": text})

    def llm_says(self, text, tag="LLM"):
        """Print LLM output with clean indentation."""
        lines = text.strip().split("\n")
        print(f"  {tag} : {lines[0]}")
        for ln in lines[1:]:
            print(f"         {ln}")
        self.history.append({"role": "assistant", "tag": tag, "content": text})

    def metta_query(self, expr, result):
        print(f"  query: !({expr})")
        print(f"  result: {result}")
        self.history.append({"role": "metta", "query": expr, "result": result})

    def metta_verdict(self, verdict, asset, action):
        """Print verdict in plain text."""
        v = (verdict or "").strip()
        if v not in ("Allow", "Deny", "Warn", "Error"):
            v = f"{v} (unexpected)"
        print(f"  verdict: {v.upper()} — {action} {asset}")
        if verdict.lower() == "deny":
            print(f"  -> trade blocked by symbolic engine")
        elif verdict.lower() == "warn":
            print(f"  -> approved with caution flag")
        else:
            print(f"  -> trade cleared")

    def system_note(self, text):
        print(f"  note: {text}")
        self.history.append({"role": "system", "content": text})

    def final_answer(self, user_message, response, verdict):
        """Print final You/ACO exchange."""
        icon_map = {"Allow": "[APPROVED]", "Warn": "[WARNING]", "Deny": "[DENIED]"}
        icon = icon_map.get(verdict, "[RESULT]")
        print(f"\n{'=' * 60}")
        print(f"  You : {user_message}")
        print(f"  ACO {icon}: {response}")
        print(f"{'=' * 60}\n")
        self.history.append({"role": "final", "verdict": verdict, "user": user_message, "aco": response})

    def export(self):
        return list(self.history)
