"""Re-export SSE manager from app.platform.sse for backward compatibility."""

from app.platform.sse import SSEConnectionManager, get_sse_manager

__all__ = ["SSEConnectionManager", "get_sse_manager"]
