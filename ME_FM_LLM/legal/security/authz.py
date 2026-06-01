from __future__ import annotations

from dataclasses import dataclass, field

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "matter:create",
        "matter:read",
        "matter:write",
        "matter:delete",
        "source:read",
        "eval:run",
        "audit:read",
        "export:create",
        "settings:write",
    },
    "attorney": {
        "matter:create",
        "matter:read",
        "matter:write",
        "source:read",
        "export:create",
        "audit:read_own_matter",
    },
    "paralegal": {"matter:read", "matter:write", "source:read", "export:create"},
    "reviewer": {"matter:read", "source:read", "audit:read_own_matter"},
    "viewer": {"matter:read", "source:read"},
}


@dataclass(frozen=True)
class UserContext:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    matter_ids: tuple[str, ...] = field(default_factory=tuple)


class RBACPolicy:
    def __init__(self, role_permissions: dict[str, set[str]] | None = None):
        self.role_permissions = role_permissions or ROLE_PERMISSIONS

    def permissions_for(self, user: UserContext) -> set[str]:
        permissions: set[str] = set()
        for role in user.roles:
            permissions.update(self.role_permissions.get(role, set()))
        return permissions

    def can(self, user: UserContext, permission: str) -> bool:
        return permission in self.permissions_for(user)

    def require(self, user: UserContext, permission: str) -> None:
        if not self.can(user, permission):
            raise PermissionError(f"user {user.user_id} lacks permission {permission}")
