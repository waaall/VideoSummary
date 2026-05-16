"""Root-level test configuration and shared fixtures.

This conftest.py provides shared fixtures and utilities for all tests.
Module-specific fixtures should be placed in their respective conftest.py files.
"""

import os
from pathlib import Path

import pytest

# 可选依赖：dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# 可选依赖：OpenTelemetry 追踪
try:
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk import trace as trace_sdk
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    tracer_provider = trace_sdk.TracerProvider()
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces"))
    )
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
except ImportError:
    pass

from app.core.asr.asr_data import ASRData, ASRDataSeg
from app.core.utils import cache


# Disable cache for testing
cache.disable_cache()


# ============================================================================
# Shared Data Fixtures
# ============================================================================


@pytest.fixture
def sample_asr_data():
    """Create sample ASR data for testing.

    Returns:
        ASRData with 3 English segments
    """
    segments = [
        ASRDataSeg(
            start_time=0,
            end_time=1000,
            text="I am a student",
        ),
        ASRDataSeg(
            start_time=1000,
            end_time=2000,
            text="You are a teacher",
        ),
        ASRDataSeg(
            start_time=2000,
            end_time=3000,
            text="VideoSummary is a tool for captioning videos",
        ),
    ]
    return ASRData(segments)


# ============================================================================
# Shared Utility Fixtures
# ============================================================================


@pytest.fixture
def check_env_vars():
    """Check if required environment variables are set.

    Returns:
        Function that takes variable names and skips test if any are missing

    Example:
        def test_api(check_env_vars):
            check_env_vars("LLM_API_KEY", "LLM_BASE_URL")
            # Test continues only if both variables are set
    """

    def _check(*var_names):
        missing = [var for var in var_names if not os.getenv(var)]
        if missing:
            pytest.skip(f"Required environment variables not set: {', '.join(missing)}")

    return _check
