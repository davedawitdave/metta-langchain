"""
chat_logger.py — Standalone ChatLogger (no external dependencies).
Tracks every pipeline step and prints in You/ACO chat format.
Imported by both langchain_pipeline.py and the test suite.
"""


class ChatLogger:
    """
    Prints each pipeline step as a chat message and tracks history.

    Format:
      ┌─ [STEP N: Label] ────────────────────────────────┐
      │ You: <input>
      │ ACO [model]: <response>
      └───────────────────────────────────────────────────┘
    """

    def __init__(self):
        self.history: list[dict] = []
        self._step = 0

    def user(self, text: str, step_label: str = "") -> None:
        self._step += 1
        label = step_label or f"Step {self._step}"
        pad   = max(0, 54 - len(label) - 4)
        print(f"\n┌─ [{label}] {'─' * pad}┐")
        print(f"│ You: {text}")
        self.history.append({"role": "user", "step": label, "content": text})

    def ai(self, text: str, model_tag: str = "LLM") -> None:
        lines  = text.strip().split("\n")
        prefix = f"│ ACO [{model_tag}]:"
        print(f"{prefix} {lines[0]}")
        for ln in lines[1:]:
            print(f"│   {ln}")
        print(f"└{'─' * 59}┘")
        self.history.append({"role": "assistant", "model": model_tag, "content": text})

    def system(self, text: str) -> None:
        print(f"│ [SYS] {text}")
        self.history.append({"role": "system", "content": text})

    def metta(self, expr: str, result: str) -> None:
        print(f"│ [MeTTa] !(  {expr}  )")
        print(f"│ [MeTTa] ←   {result}")
        self.history.append({"role": "metta", "query": expr, "result": result})

    def verdict_banner(self, verdict: str, asset: str, action: str) -> None:
        icons = {"Allow": "✅", "Deny": "🚫", "Warn": "⚠️ ", "Error": "❌"}
        icon  = icons.get(verdict, "❓")
        print(f"│")
        print(f"│  {icon}  METTA VERDICT: {verdict.upper()}  ─  {action} {asset}")
        print(f"│")

    def export(self) -> list[dict]:
        return list(self.history)
