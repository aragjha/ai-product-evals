"""Live system: one Claude call per question, prompt chosen by variant.

Optional. Needs `pip install anthropic` and ANTHROPIC_API_KEY. CI never imports it.
"""
from __future__ import annotations

import json
import os

from .. import data, schema
from ..pricing import cost_usd

DEFAULT_MODEL = "claude-opus-5-5"


class ClaudeSystem:
    label = "measured: live model run"

    def __init__(self, variant: str, model: str | None = None, client=None, max_tokens: int = 2000):
        self.variant = variant
        self.model = model or os.environ.get("PEVALS_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        prompt_path = data.ROOT / "prompts" / f"{variant}.md"
        if not prompt_path.exists():
            raise SystemExit(f"No prompt at prompts/{variant}.md")
        self.system_prompt = prompt_path.read_text()
        self.docs = "\n\n".join(f'<doc id="{k}">\n{v.strip()}\n</doc>' for k, v in data.corpus().items())
        if client is None:
            try:
                import anthropic
            except ImportError:
                raise SystemExit("The claude system needs the SDK: pip install anthropic")
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise SystemExit("Set ANTHROPIC_API_KEY (see .env.example) or use --system offline.")
            client = anthropic.Anthropic()
        self.client = client

    def answer(self, question: str) -> tuple[str, dict]:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": f"<docs>\n{self.docs}\n</docs>\n\nQuestion: {question}"}],
            output_config={"format": {"type": "json_schema", "schema": schema.OUTPUT_SCHEMA}},
        )
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        usage["cost_usd"] = cost_usd(self.model, usage["input_tokens"], usage["output_tokens"])
        if resp.stop_reason == "refusal":
            return json.dumps({"refusal": True}), usage  # graded as a schema failure, never dropped
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return text, usage
