"""Claude LLMClient implementation.

Uses the Anthropic API for real LLM completions.
Requires: pip install anthropic
"""


class ClaudeLLMClient:
    """LLMClient backed by Claude via the Anthropic API."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-6"):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Send a completion request to Claude. Returns response text."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
