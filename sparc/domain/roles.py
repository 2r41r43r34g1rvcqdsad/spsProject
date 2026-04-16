from enum import Enum
from sparc.domain.errors import BadRequestError

class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

class Permission(str, Enum):
    PROVISION_TENANT = "provision_tenant"
    TRANSITION_TENANT = "transition_tenant"
    MANAGE_USER_ROLES = "manage_user_roles"
    MANAGE_FEATURE_FLAGS = "manage_feature_flags"
    READ_FEATURE_FLAGS = "read_feature_flags"
    READ_AUDIT_LOGS = "read_audit_logs"
    READ_TENANT_DATA = "read_tenant_data"
    WRITE_TENANT_DATA = "write_tenant_data"
    SUBMIT_FILE = "submit_file"
    SUBMIT_CSV_IMPORT = "submit_csv_import"
    SUBMIT_EMAIL = "submit_email"

ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: set(Permission),
    Role.TENANT_ADMIN: {
        Permission.TRANSITION_TENANT,
        Permission.MANAGE_USER_ROLES,
        Permission.MANAGE_FEATURE_FLAGS,
        Permission.READ_FEATURE_FLAGS,
        Permission.READ_AUDIT_LOGS,
        Permission.READ_TENANT_DATA,
        Permission.WRITE_TENANT_DATA,
        Permission.SUBMIT_FILE,
        Permission.SUBMIT_CSV_IMPORT,
        Permission.SUBMIT_EMAIL,
    },
    Role.ANALYST: {
        Permission.READ_FEATURE_FLAGS,
        Permission.READ_TENANT_DATA,
        Permission.WRITE_TENANT_DATA,
        Permission.SUBMIT_FILE,
        Permission.SUBMIT_CSV_IMPORT,
    },
    Role.VIEWER: {
        Permission.READ_FEATURE_FLAGS,
        Permission.READ_TENANT_DATA,
    },
}

def parse_role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError as error:
        raise BadRequestError(f"Invalid role '{value}'") from error

def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
