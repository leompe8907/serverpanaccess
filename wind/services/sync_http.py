"""
Helpers para sync HTTP vía Celery (roadmap #26).
"""
import os

from rest_framework import status
from rest_framework.response import Response


def sync_http_async_enabled() -> bool:
    """POST /wind/sync-* encola Celery por defecto."""
    return os.getenv("SYNC_HTTP_ASYNC", "true").lower() in ("true", "1", "yes")


def parse_sync_limit(request, default: int = 100) -> int:
    if request.method == "GET":
        limit = int(request.query_params.get("limit", default))
    else:
        data = request.data if isinstance(request.data, dict) else {}
        limit = int(data.get("limit", default))
    return min(max(limit, 1), 1000)


def celery_enqueue_response(async_result, *, limit: int, label: str) -> Response:
    return Response(
        {
            "success": True,
            "message": f"{label} encolado",
            "task_id": async_result.id,
            "limit": limit,
            "status_url": f"/api/v1/tasks/{async_result.id}/",
        },
        status=status.HTTP_202_ACCEPTED,
    )


def sync_get_info_response(*, endpoint: str, task_name: str, async_default: bool) -> Response:
    return Response(
        {
            "success": True,
            "message": "Use POST para ejecutar. Con SYNC_HTTP_ASYNC=true (default) responde 202 y task_id.",
            "endpoint": endpoint,
            "celery_task": task_name,
            "sync_http_async": sync_http_async_enabled(),
            "async_default": async_default,
        },
        status=status.HTTP_200_OK,
    )
