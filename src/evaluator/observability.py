"""Centralized observability and tracing helper for Langfuse integration."""

import logging
from typing import Optional, Callable
from src.config import (
    is_langfuse_enabled,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LANGFUSE_HOST,
    OPENAI_API_KEY,
)

logger = logging.getLogger("upsc-observability")

_langfuse_client = None


def get_langfuse_client():
    """Retrieve or initialize the Langfuse client if enabled."""
    global _langfuse_client
    if not is_langfuse_enabled():
        return None

    if _langfuse_client is None:
        try:
            import langfuse

            _langfuse_client = langfuse.get_client()
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse client: {e}")
            _langfuse_client = None
    return _langfuse_client


def observe_stage(
    name: Optional[str] = None,
    as_type: Optional[str] = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable:
    """Decorator to trace execution stages with Langfuse. Falls back to no-op if Langfuse is disabled."""
    if not is_langfuse_enabled():

        def noop_decorator(func: Callable) -> Callable:
            return func

        return noop_decorator

    try:
        from langfuse import observe

        return observe(
            name=name,
            as_type=as_type,
            capture_input=capture_input,
            capture_output=capture_output,
        )
    except Exception as e:
        logger.warning(f"Could not load Langfuse observe decorator: {e}")

        def fallback_decorator(func: Callable) -> Callable:
            return func

        return fallback_decorator


def get_async_openai_client(api_key: Optional[str] = None):
    """Return Langfuse-wrapped AsyncOpenAI client when enabled, or standard AsyncOpenAI otherwise."""
    key = api_key or OPENAI_API_KEY or "sk-dummy-key-for-testing"
    if is_langfuse_enabled():
        try:
            from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI

            return LangfuseAsyncOpenAI(api_key=key)
        except Exception as e:
            logger.warning(f"Failed to instantiate Langfuse AsyncOpenAI wrapper, falling back: {e}")

    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=key)


def get_current_trace_id() -> Optional[str]:
    """Retrieve the current active Langfuse trace ID if available."""
    client = get_langfuse_client()
    if client:
        try:
            return client.get_current_trace_id()
        except Exception:
            pass
    return None


def get_current_trace_url(trace_id: Optional[str] = None) -> Optional[str]:
    """Retrieve the web URL to the trace in the Langfuse dashboard."""
    client = get_langfuse_client()
    if client:
        try:
            return client.get_trace_url(trace_id=trace_id)
        except Exception:
            pass
    return None


def flush_observability():
    """Flush pending Langfuse trace events to ensure telemetry is dispatched immediately."""
    client = get_langfuse_client()
    if client:
        try:
            client.flush()
        except Exception as e:
            logger.debug(f"Langfuse flush error: {e}")
