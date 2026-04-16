"""
Audit Service - Logs All API Events for Compliance

This service provides audit logging for all API operations.
It creates immutable audit log entries for compliance and security purposes.

Features:
    1. Write-once logs - Once created, cannot be modified or deleted
    2. Captures all context - action, actor, details, outcome, timestamp
    3. Tenant isolation - Each tenant's logs are isolated
    4. Schema versioned - Supports future migrations

Audit Document Structure:
    {
        "auditId": "aud_<12_char_hex>",  # Unique ID
        "action": "tenant_created",       # Action performed
        "actor": {
            "userId": "user_123",       # User who performed action
            "email": "user@ex.com",      # User email
            "role": "super_admin"       # Role at time of action
        },
        "details": {...},              # Additional details
        "outcome": "success",           # "success" or "failure"
        "timestamp": "2024-01-01T00:00:00Z",  # UTC timestamp
        "_schema_version": "1.0"         # Schema version
    }

Common Actions Logged:
    - tenant_created
    - tenant_suspended
    - tenant_reactivated
    - access_denied
    - user_invited
    - user_removed
    - flag_created
    - flag_updated
"""

from datetime import datetime, timezone
import uuid
from app.db.tenant_scoped_repository import TenantScopedRepository


class AuditService:
    """
    Service for logging audit events.
    
    Provides write-once audit logging for compliance and security.
    All audit logs are immutable once created.
    
    Attributes:
        repo: TenantScopedRepository for audit_logs collection
    """
    
    def __init__(self, repo: TenantScopedRepository):
        """
        Initialize AuditService.
        
        Args:
            repo: TenantScopedRepository for audit_logs collection
        """
        self.repo = repo
    
    async def log_event(
        self, 
        tenant_id: str, 
        action: str, 
        actor_role: str = "",
        details: dict = None, 
        outcome: str = "success",
        actor_user_id: str = "", 
        actor_email: str = ""
    ):
        """
        Log an audit event.
        
        Creates an immutable audit log entry with all context.
        The entry cannot be modified or deleted after creation.
        
        Args:
            tenant_id: Tenant ID (use "GLOBAL" for system-wide events)
            action: The action being logged (e.g., "tenant_created")
            actor_role: Role of the user performing the action
            details: Additional context-specific details
            outcome: "success" or "failure"
            actor_user_id: ID of the user performing the action
            actor_email: Email of the user performing the action
        
        Audit Document Created:
            - auditId: Unique 12-char hex ID
            - action: The action performed
            - actor: {userId, email, role}
            - details: Additional details dict
            - outcome: success or failure
            - timestamp: ISO8601 UTC
            - _schema_version: "1.0"
        """
        # Create unique audit ID
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        
        # Build audit document
        audit_doc = {
            "auditId": audit_id,
            "action": action,
            "actor": {
                "userId": actor_user_id,
                "email": actor_email,
                "role": actor_role
            },
            "details": details or {},
            "outcome": outcome,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_schema_version": "1.0"
        }
        
        # Insert into audit_logs collection (write-once)
        await self.repo.insert_one(tenant_id, audit_doc)