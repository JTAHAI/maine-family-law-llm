from __future__ import annotations

from dataclasses import dataclass

from .authz import RBACPolicy, UserContext


@dataclass(frozen=True)
class MatterReference:
    matter_id: str
    tenant_id: str
    owner_user_id: str | None = None


class MatterAccessPolicy:
    def __init__(self, rbac: RBACPolicy | None = None):
        self.rbac = rbac or RBACPolicy()

    def can_access(self, user: UserContext, matter: MatterReference, permission: str) -> bool:
        if user.tenant_id != matter.tenant_id:
            return False
        if matter.matter_id not in user.matter_ids and "admin" not in user.roles:
            return False
        return self.rbac.can(user, permission)

    def assert_access(self, user: UserContext, matter: MatterReference, permission: str) -> None:
        if not self.can_access(user, matter, permission):
            raise PermissionError(
                f"user {user.user_id} cannot {permission} matter {matter.matter_id} in tenant {matter.tenant_id}"
            )
