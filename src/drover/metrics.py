"""AI performance metrics collection.

Captures LangChain callback data for model comparison including
token counts, latency, and cost estimation.
"""

import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from pydantic import BaseModel, Field

# Token pricing per 1M tokens (as of 2024)
# Format: (input_price, output_price)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Anthropic
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-opus-latest": (15.00, 75.00),
    # Ollama (local, free)
    "llama3.2:latest": (0.0, 0.0),
    "llama3.1:latest": (0.0, 0.0),
    "mistral:latest": (0.0, 0.0),
}


class AIMetrics(BaseModel):
    """Metrics for a single AI classification call."""

    model: str = Field(description="Provider and model identifier")
    input_tokens: int = Field(default=0, description="Prompt token count")
    output_tokens: int = Field(default=0, description="Completion token count")
    total_tokens: int = Field(default=0, description="Sum of input + output tokens")
    latency_ms: float = Field(default=0.0, description="Request latency in milliseconds")
    cost_usd: float | None = Field(default=None, description="Estimated cost in USD")


class MetricsCallback(BaseCallbackHandler):
    """LangChain callback handler for collecting metrics."""

    def __init__(self, model: str) -> None:
        """Initialize metrics callback.

        Args:
            model: Model identifier for pricing lookup.
        """
        super().__init__()
        self.model = model
        self._start_time: float | None = None
        self._metrics = AIMetrics(model=model)

    @property
    def metrics(self) -> AIMetrics:
        """Get collected metrics."""
        return self._metrics

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts generating."""
        self._start_time = time.perf_counter()

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes generating."""
        # Calculate latency
        if self._start_time is not None:
            elapsed = time.perf_counter() - self._start_time
            self._metrics.latency_ms = elapsed * 1000

        # Extract token usage if available
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            self._metrics.input_tokens = token_usage.get("prompt_tokens", 0)
            self._metrics.output_tokens = token_usage.get("completion_tokens", 0)
            self._metrics.total_tokens = token_usage.get("total_tokens", 0)

            # Fallback calculation
            if self._metrics.total_tokens == 0:
                self._metrics.total_tokens = (
                    self._metrics.input_tokens + self._metrics.output_tokens
                )

        # Calculate cost
        self._metrics.cost_usd = self._calculate_cost()

    def _calculate_cost(self) -> float | None:
        """Calculate estimated cost based on token usage.

        Returns:
            Estimated cost in USD, or None if pricing unavailable.
        """
        # Find pricing for model
        pricing = MODEL_PRICING.get(self.model)
        if pricing is None:
            # Try partial match
            for model_name, prices in MODEL_PRICING.items():
                if model_name in self.model or self.model in model_name:
                    pricing = prices
                    break

        if pricing is None:
            return None

        input_price, output_price = pricing
        input_cost = (self._metrics.input_tokens / 1_000_000) * input_price
        output_cost = (self._metrics.output_tokens / 1_000_000) * output_price

        return round(input_cost + output_cost, 6)


def create_metrics_callback(provider: str, model: str) -> MetricsCallback:
    """Create a metrics callback for the given provider/model.

    Args:
        provider: AI provider (ollama, openai, anthropic).
        model: Model identifier.

    Returns:
        MetricsCallback instance.
    """
    full_model = f"{provider}/{model}"
    return MetricsCallback(model=full_model)
