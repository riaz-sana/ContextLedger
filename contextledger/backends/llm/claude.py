"""Claude LLMClient implementation.

Uses the Anthropic API for real LLM completions.
Requires: pip install anthropic
"""

import os


class ClaudeLLMClient:
    """LLMClient backed by Claude via the Anthropic API."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-5"):
        # Load API key from global and local .env
        try:
            from dotenv import load_dotenv
            _global_env = os.path.join(os.path.expanduser("~/.contextledger"), ".env")
            if os.path.exists(_global_env):
                load_dotenv(_global_env)
            load_dotenv()
        except ImportError:
            pass

        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found.\n"
                "Add it to ~/.contextledger/.env or set in environment."
            )

        self.client = anthropic.Anthropic(api_key=resolved_key)
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Send a completion request to Claude. Returns response text."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
