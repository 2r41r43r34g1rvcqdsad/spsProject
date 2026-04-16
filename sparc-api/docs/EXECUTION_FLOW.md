# SPARC API - Code Documentation

## Table of Contents
1. [Application Entry Point](#appmainpy)
2. [Database Layer](#database-layer)
3. [Services](#services)
4. [Routers](#routers)
5. [Middleware](#middleware)
6. [Authentication](#authentication)
7. [Models](#models)

---

## 1. Application Entry Point (`app/main.py`)

### Overview
FastAPI application with lifecycle management for database/Redis connections.

### Functions

| Function | Purpose |
|----------|---------|
| `lifespan(app)` | Async context manager that runs on startup/shutdown. Initializes: database, Redis, repositories (tenants, user_roles, feature_flags, audit_logs), services (TenantService, UserRoleService, FeatureFlagService, AuditService). On shutdown, closes Redis connection. |
| `health()` | Health check endpoint - returns `{"status": "ok"}` |
| `ready()` | Readiness check - verifies Redis is available |

### Routers Included
- `admin_tenants.router` - `/admin/tenants`
- `admin_feature_flags.router` - `/admin/feature-flags`
- `tenant_users.router` - `/tenant/users`
- `tenant_feature_flags.router` - `/tenant/feature-flags`

---

## 2. Database Layer

### a) `app/db/cosmos_client.py`

| Function/Class | Purpose |
|---------------|---------|
| `get_database()` | Returns Cosmos DB client or InMemoryDatabase fallback. Uses `settings.cosmos_connection_string` from config. Falls back to in-memory for local development. |
| `InMemoryDatabase` | In-memory storage for local dev without Cosmos DB |
| `InMemoryCollection` | Simulates MongoDB collection with in-memory dict |
| `InMemoryCursor` | Pagination helper for in-memory queries |

### b) `app/db/redis_client.py`

| Function | Purpose |
|----------|---------|
| `get_redis()` | Returns Redis client (or InMemoryRedis fallback). Used for caching tenant data, feature flags, user roles. |

### c) `app/db/tenant_scoped_repository.py`

**Purpose**: Base repository ensuring tenant data isolation. Every query automatically includes `tenantId` in the filter.

| Method | Purpose |
|--------|---------|
| `find_one(tenant_id, filter)` | Find single document scoped to tenant |
| `find_many(tenant_id, filter, skip, limit)` | Find multiple documents |
| `find_many_unscoped(filter, skip, limit)` | Admin-only: query without tenant scoping (e.g., list all tenants) |
| `insert_one(tenant_id, document)` | Insert document with tenantId added |
| `update_one(tenant_id, filter, update_dict)` | Update document (scoped) |
| `upsert_one(tenant_id, filter, update_dict)` | Insert or update |
| `delete_one(tenant_id, filter)` | Delete document |

---

## 3. Services

### a) `app/services/tenant_service.py`

| Method | Purpose |
|--------|---------|
| `get_tenant(tenant_id)` | Get tenant: check Redis cache (5 min TTL), fallback to Cosmos DB |
| `transition_status(tenant_id, new_status)` | State machine: enforce valid status transitions. Valid transitions: provisioning→[active/trial/cancelled], trial→[active/suspended/cancelled], active→[suspended/cancelled], suspended→[active/cancelled]. Invalid transitions raise ValueError. |

### b) `app/services/feature_flag_service.py`

| Method | Purpose |
|--------|---------|
| `is_enabled(tenant_id, flag_key)` | Check flag: Redis cache (60s TTL) → tenant-specific flag → GLOBAL fallback |
| `set_flag(tenant_id, flag_key, enabled, modified_by)` | Toggle flag and invalidate cache |

### c) `app/services/audit_service.py`

| Method | Purpose |
|--------|---------|
| `log_event(tenant_id, action, actor_role, details, outcome, actor_user_id, actor_email)` | Write-once audit log. Stores: auditId, action, actor (userId, email, role), details, outcome, timestamp, _schema_version. No updates/deletes allowed. |

### d) `app/services/user_role_service.py`

| Method | Purpose |
|--------|---------|
| `get_user_role(tenant_id, user_id)` | Get user role: Redis cache (5 min TTL) → Cosmos DB |
| `set_user_role(tenant_id, user_id, role, assigned_by)` | Set/update user role with timestamp |
| `list_users(tenant_id, skip, limit)` | List all users in tenant |

---

## 4. Routers

### a) `app/routers/admin_tenants.py` (`/admin/tenants`)

| Endpoint | Method | Purpose | Auth |
|----------|--------|--------|------|
| `/admin/tenants` | POST | Create new tenant (provisioning status) | super_admin |
| `/admin/tenants` | GET | List all tenants (global, not scoped) | super_admin |
| `/admin/tenants/{tenant_id}` | GET | Get single tenant details | super_admin |
| `/admin/tenants/{tenant_id}` | PATCH | Update tenant (name, plan) | super_admin |
| `/admin/tenants/{tenant_id}/suspend` | POST | Suspend tenant (immediate 403) | super_admin |
| `/admin/tenants/{tenant_id}/reactivate` | POST | Reactivate tenant | super_admin |

### b) `app/routers/admin_feature_flags.py` (`/admin/feature-flags`)

| Endpoint | Method | Purpose | Auth |
|----------|--------|--------|------|
| `/admin/feature-flags` | GET | List GLOBAL flags | super_admin |
| `/admin/feature-flags` | POST | Create flag | super_admin |
| `/admin/feature-flags/{flag_key}` | PATCH | Toggle flag | super_admin |
| `/admin/feature-flags/{flag_key}` | DELETE | Delete flag | super_admin |

### c) `app/routers/tenant_feature_flags.py` (`/tenant/feature-flags`)

| Endpoint | Method | Purpose | Auth |
|----------|--------|--------|------|
| `/tenant/feature-flags` | GET | List tenant-specific flags | tenant_admin |
| `/tenant/feature-flags/{flag_key}` | GET | Check if flag enabled | tenant_admin |

### d) `app/routers/tenant_users.py` (`/tenant/users`)

| Endpoint | Method | Purpose | Auth |
|----------|--------|--------|------|
| `/tenant/users` | GET | List users | tenant_admin |
| `/tenant/users` | POST | Invite user | tenant_admin |
| `/tenant/users/{user_id}` | PATCH | Update user role | tenant_admin |
| `/tenant/users/{user_id}` | DELETE | Remove user | tenant_admin |

---

## 5. Middleware

### `app/middleware/tenant_middleware.py`

| Path Type | Behavior |
|-----------|----------|
| Excluded (`/health`, `/ready`, `/docs`, `/redoc`, `/openapi.json`) | Bypass tenant check |
| Missing `x-tenant-id` header | 400: "Missing tenant context" |
| Invalid tenant_id | 403: "Tenant not found" |
| Status not active/trial | 403: "Tenant access denied: status={status}" |
| Valid request | Set `request.state.tenant` and `request.state.tenant_id`, continue to handler |

---

## 6. Authentication (`app/auth/rbac.py`)

### Role Hierarchy
```
super_admin: 4  (highest)
tenant_admin: 3
analyst: 2
viewer: 1
```

### Decorator: `@require_role(minimum_role)`
- Reads `x-user-role` header
- Validates against `ROLE_HIERARCHY`
- Logs `access_denied` audit event on failure
- Returns 403 if insufficient role

---

## 7. Models

### `app/models/tenant.py`
```python
class Tenant:
    tenantId: str
    tenantName: str
    plan: str
    adminUserId: str
    status: str  # provisioning, trial, active, suspended, cancelled
```

### `app/models/feature_flag.py`
```python
class FeatureFlag:
    flagKey: str
    enabled: bool
    description: str
    lastModifiedBy: str
    lastModifiedAt: datetime
```

### `app/models/user_role.py`
```python
class UserRole:
    userId: str
    email: str
    role: str  # super_admin, tenant_admin, analyst, viewer
    assignedBy: str
    assignedAt: datetime
    status: str  # active, inactive
```

---

## Request Flow Summary

```
1. Request arrives
2. TenantMiddleware checks:
   - x-tenant-id header present?
   - tenant exists in DB?
   - status is active/trial?
3. Route handler executes with @require_role decorator
   - x-user-role header validated
4. Service performs business logic
5. Results returned (or 403 if role insufficient)
```