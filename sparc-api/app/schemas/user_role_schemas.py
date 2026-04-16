from pydantic import BaseModel
from typing import Optional
from app.models.user_role import UserRole

class AssignRoleRequest(BaseModel):
    userId: str
    email: str
    role: str

class UserRoleResponse(UserRole):
    pass

