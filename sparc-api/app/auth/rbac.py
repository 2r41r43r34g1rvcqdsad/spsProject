"""
RBAC (Role-Based Access Control) - Authentication & Authorization

This module provides role-based access control for the API.
It defines role hierarchy and provides a decorator for endpoint protection.

Features:
    1. Role hierarchy - Defines role levels (super_admin > tenant_admin > analyst > viewer)
    2. @require_role() decorator - Protects endpoints by minimum required role
    3. Audit logging - Logs access denied events

Role Hierarchy (highest to lowest):
    super_admin:   4 (can manage all tenants, create/delete tenants, manage feature flags)
    tenant_admin: 3 (can manage users within their tenant)
    analyst:     2 (can view data and run analysis)
    viewer:      1 (can only view data)

Usage:
    @router.get("/endpoint")
    @require_role("tenant_admin")
    async def endpoint(request: Request):
        # Only tenant_admin or higher can access
        pass

Request Headers Required:
    - x-user-role: The role of the requesting user

Response Codes:
    - 403: If user role < minimum required role
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, Request

# Role hierarchy - higher number = more permissions
# Used to compare if user has sufficient permissions
ROLE_HIERARCHY = {
    "super_admin": 4,    # Highest - can manage all tenants
    "tenant_admin": 3,    # Can manage tenant users
    "analyst": 2,       # Can run analysis
    "viewer": 1          # Lowest - can only view
}


def _extract_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request:
    """
    Extract the FastAPI Request object from decorator arguments.
    
    The @require_role decorator receives the request as either:
    - First positional argument, OR
    - keyword argument named "request"
    
    Args:
        args: Positional arguments passed to decorated function
        kwargs: Keyword arguments passed to decorated function
        
    Returns:
        The FastAPI Request object
        
    Raises:
        RuntimeError: If request not found in args or kwargs
    """
    # Check kwargs first
    request = kwargs.get("request")
    if isinstance(request, Request):
        return request
    
    # Check positional args
    for arg in args:
        if isinstance(arg, Request):
            return arg
    
    # Not found
    raise RuntimeError("RBAC decorator requires a FastAPI Request argument.")


def require_role(minimum_role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that validates user role against required minimum.
    
    Flow:
        1. Extract request object from arguments
        2. Read x-user-role header
        3. Compare user's role level to minimum required
        4. If insufficient:
           - Log access_denied audit event
           - Raise 403 HTTPException
        5. If sufficient: Execute endpoint
    
    Args:
        minimum_role: Minimum role required to access the endpoint
                     (e.g., "viewer", "analyst", "tenant_admin", "super_admin")
    
    Usage:
        @router.get("/protected")
        @require_role("tenant_admin")
        async def protected(request: Request):
            pass
    
    Returns:
        Decorator function that wraps the endpoint
    """
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract request from arguments
            request = _extract_request(args, kwargs)
            
            # Get user role from header
            user_role = request.headers.get("x-user-role", "")
            
            # Get role levels for comparison
            user_level = ROLE_HIERARCHY.get(user_role, 0)
            required_level = ROLE_HIERARCHY.get(minimum_role, 999)
            
            # Check if user has sufficient permissions
            has_access = user_level >= required_level
            
            # If insufficient role, log and deny access
            if not has_access:
                # Get audit service to log the access denied event
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
                
                # Return 403 Forbidden
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{minimum_role}' or above required",
                )
            
            # User has sufficient role - execute the endpoint
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator