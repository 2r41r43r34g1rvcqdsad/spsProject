from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, Request

ROLE_HIERARCHY = {"super_admin": 4, "tenant_admin": 3, "analyst": 2, "viewer": 1}


def _extract_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request:
    request = kwargs.get("request")
    if isinstance(request, Request):
        return request

    for arg in args:
        if isinstance(arg, Request):
            return arg

    raise RuntimeError("RBAC decorator requires a FastAPI Request argument.")


def require_role(minimum_role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that validates `x-user-role` against ROLE_HIERARCHY."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _extract_request(args, kwargs)
            user_role = request.headers.get("x-user-role", "")
            has_access = ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(
                minimum_role, 999
            )
            if not has_access:
                audit_service = getattr(request.app.state, "audit_service", None)
                if audit_service is not None:
                    await audit_service.log_event(
                        tenant_id=getattr(request.state, "tenant_id", "GLOBAL"),
                        action="access_denied",
                        actor_role=user_role,
                        details={
                            "required_role": minimum_role,
                            "endpoint": str(request.url),
                        },
                        outcome="failure",
                    )
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{minimum_role}' or above required",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
