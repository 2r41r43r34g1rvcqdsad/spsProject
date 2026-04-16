# SPARC API - Execution Flow

## 1. Application Startup

```
main.py
  │
  ├─> FastAPI app created with lifespan context manager
  │
  ├─> lifespan() runs on startup:
  │     │
  │     ├─> get_database()        → Cosmos DB or InMemoryDatabase
  │     ├─> get_redis()           → Redis or InMemoryRedis
  │     │
  │     ├─> Create repositories:
  │     │     ├─> TenantScopedRepository("tenants")
  │     │     ├─> TenantScopedRepository("user_roles")
  │     │     ├─> TenantScopedRepository("feature_flags")
  │     │     └─> TenantScopedRepository("audit_logs")
  │     │
  │     ├─> Initialize services:
  │     │     ├─> TenantService(tenant_repo, redis)
  │     │     ├─> UserRoleService(user_role_repo, redis)
  │     │     ├─> FeatureFlagService(feature_flag_repo, redis)
  │     │     └─> AuditService(audit_repo)
  │     │
  │     └─> Store in app.state
  │
  ├─> Add TenantMiddleware
  │
  └─> Include routers:
        ├─> admin_tenants
        ├─> admin_feature_flags
        ├─> tenant_users
        └─> tenant_feature_flags
```

## 2. Request Flow (with Tenant)

```
Client Request
       │
       ▼
TenantMiddleware.dispatch()
       │
       ├─> [EXCLUDED PATHS] → /health, /ready, /docs, /redoc, /openapi.json
       │         │
       │         └─> Allow through (no tenant check)
       │
       ├─> [MISSING HEADER] → No x-tenant-id?
       │         │
       │         └─> 400: "Missing tenant context"
       │
       ├─> [TENANT NOT FOUND] → Invalid tenant_id?
       │         │
       │         └─> 403: "Tenant not found"
       │
       ├─> [TENANT SUSPENDED] → Status not active/trial?
       │         │
       │         └─> 403: "Tenant access denied: status=suspended"
       │
       └─> [OK] → Set request.state.tenant, request.state.tenant_id
                 │
                 ▼
           Router Handler
```

## 3. Admin Tenant Flow (Super Admin)

```
POST /admin/tenants
       │
       ├─> @require_role("super_admin")
       │     │
       │     ├─> Check x-user-role header
       │     └─> Verify ROLE_HIERARCHY[user_role] >= 4
       │           If fail → 403 + audit log
       │
       ├─> Create tenant_doc with status="provisioning"
       │
       ├─> tenant_repo.insert_one(tenant_id, tenant_doc)
       │
       ├─> audit_service.log_event(
       │       tenant_id="GLOBAL",
       │       action="tenant_created"
       │  )
       │
       └─> Return {tenantId, status: "provisioning"}
```

## 4. Tenant Status Transition Flow

```
POST /admin/tenants/{tenant_id}/suspend
       │
       ├─> tenant_service.get_tenant(tenant_id)
       │     │
       │     ├─> Check Redis cache "tenant:{tenant_id}"
       │     │     ├─> Hit → return cached
       │     │     │
       │     │     └─> Miss → query Cosmos DB
       │     │           └─> Cache result (5 min TTL)
       │     │
       │     └─> Return tenant doc
       │
       ├─> Validate transition: current → new_status
       │     VALID_TRANSITIONS = {
       │         "provisioning": ["active", "trial", "cancelled"],
       │         "trial": ["active", "suspended", "cancelled"],
       │         "active": ["suspended", "cancelled"],
       │         "suspended": ["active", "cancelled"]
       │     }
       │     If invalid → raise ValueError
       │
       ├─> Update status in DB
       │
       ├─> Invalidate Redis cache
       │
       └─> Return {status: "suspended"}
```

## 5. Feature Flag Flow

```
GET /tenant/feature-flags/{flag_key}
       │
       ├─> Check cache: "ff:{tenant_id}:{flag_key}"
       │     ├─> Hit → return cached value
       │     │
       │     └─> Miss → continue
       │
       ├─> Query tenant-specific flag
       │     tenant_repo.find_one(tenant_id, {flagKey})
       │
       ├─> [NOT FOUND] → Fall back to GLOBAL
       │     tenant_repo.find_one("GLOBAL", {flagKey})
       │
       ├─> Cache result (60s TTL)
       │
       └─> Return enabled bool

POST /admin/feature-flags/{flag_key}
       │
       ├─> @require_role("super_admin")
       │
       ├─> Update flag in DB
       │
       └─> Invalidate cache: redis.delete(f"ff:{tenant_id}:{flag_key}")
```

## 6. RBAC Access Check Flow

```
@require_role("tenant_admin")
       │
       ├─> Extract Request from args/kwargs
       │
       ├─> Get x-user-role header
       │
       ├─> Check: ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required]
       │     ROLE_HIERARCHY = {
       │         "super_admin": 4,
       │         "tenant_admin": 3,
       │         "analyst": 2,
       │         "viewer": 1
       │     }
       │
       ├─> [ACCESS DENIED]
       │     ├─> Log audit event: action="access_denied"
       │     └─> Raise 403 HTTPException
       │
       └─> [ACCESS OK] → Execute handler
```

## 7. User Role Flow

```
GET /tenant/users
       │
       ├─> @require_role("tenant_admin")
       │
       ├─> Get tenant_id from request.state
       │
       ├─> user_role_repo.find_many(tenant_id, {})
       │
       └─> Return user list

POST /tenant/users
       │
       ├─> @require_role("tenant_admin")
       │
       ├─> Create user_role doc with role
       │
       ├─> Upsert to DB (create or update)
       │
       └─> Invalidate cache: redis.delete(f"user_role:{user_id}:{tenant_id}")
```

## 8. Audit Log Flow

```
audit_service.log_event(
    tenant_id: str,
    action: str,
    actor_role: str,
    details: dict,
    outcome: str,
    actor_user_id: str,
    actor_email: str
)
       │
       ├─> Build audit_doc:
       │     {
       │         "auditId": "aud_{12_char_hex}",
       │         "action": action,
       │         "actor": {userId, email, role},
       │         "details": details,
       │         "outcome": outcome,
       │         "timestamp": ISO8601,
       │         "_schema_version": "1.0"
       │     }
       │
       └─> repo.insert_one(tenant_id, audit_doc)
           (Write-once: no updates or deletes)
```

## 9. Shutdown Flow

```
lifespan() exits
       │
       └─> redis.close() if available
```
