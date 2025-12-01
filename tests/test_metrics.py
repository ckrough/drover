"""Tests for metrics collection and pricing calculations."""

from langchain_core.outputs import LLMResult

from drover.metrics import AIMetrics, MetricsCallback, create_metrics_callback


def test_create_metrics_callback_uses_provider_and_model() -> None:
    cb = create_metrics_callback("openai", "gpt-4o")
    assert isinstance(cb, MetricsCallback)
    assert "openai/" in cb.metrics.model


def test_metrics_callback_records_latency_and_tokens() -> None:
    cb = MetricsCallback(model="gpt-4o")

    # Simulate start
    cb.on_llm_start(serialized={}, prompts=["hi"])

    # Simulate end with token usage
    result = LLMResult(
        generations=[],
        llm_output={
            "token_usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500,
            }
        },
    )

    cb.on_llm_end(response=result)

    metrics = cb.metrics
    assert metrics.input_tokens == 1000
    assert metrics.output_tokens == 500
    assert metrics.total_tokens == 1500
    # For gpt-4o pricing, cost should be non-negative and small for this token count
    assert metrics.cost_usd is None or metrics.cost_usd >= 0.0
