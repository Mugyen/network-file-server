"""Access-request workflow — a user asks to be allowlisted on a mount;
the mount owner OR a relay admin approves/denies.
"""

from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from accounts import Role, SubjectType, UserNotFoundError
from relay.app.dependencies import get_current_identity, is_admin_username
from relay.app.enums import AccessRequestStatus
from relay.app.exceptions import AccessRequestNotFoundError, MountNotFoundError
from relay.app.services.account_store import get_account_store
from relay.app.services.mount_registry import get_registry
from relay.app.services.session import SessionIdentity

router = APIRouter(prefix="/requests", tags=["access-requests"])


class CreateAccessRequest(BaseModel):
    code: str


class ResolveAction(str, Enum):
    APPROVE = "approve"
    DENY = "deny"


class ResolveBody(BaseModel):
    action: ResolveAction
    role: Role | None = None


def _serialize_with_username(req, username: str | None) -> dict[str, object]:
    return {
        "id": req.id,
        "code": req.code,
        "user_id": req.user_id,
        "username": username,
        "status": req.status.value,
        "created_at": req.created_at,
    }


async def _serialize(req) -> dict[str, object]:
    try:
        username = (await get_account_store().get_user_by_id(req.user_id)).username
    except UserNotFoundError:
        username = None
    return _serialize_with_username(req, username)


@router.post("")
async def create_request(
    body: CreateAccessRequest,
    identity: SessionIdentity = Depends(get_current_identity),
) -> dict[str, object]:
    registry = get_registry()
    req = await registry.create_access_request(body.code, identity.user_id)
    return await _serialize(req)


@router.get("")
async def list_requests(
    identity: SessionIdentity = Depends(get_current_identity),
) -> list[dict[str, object]]:
    registry = get_registry()
    if is_admin_username(identity.username):
        reqs = await registry.list_all_access_requests()
    else:
        mine = await registry.list_access_requests_for_user(identity.user_id)
        owned = await registry.list_access_requests_for_owner(identity.user_id)
        by_id = {r.id: r for r in mine}
        by_id.update({r.id: r for r in owned})
        reqs = sorted(by_id.values(), key=lambda r: r.id, reverse=True)
    # One batch query for all usernames instead of one query per request row.
    users = await get_account_store().get_users_by_ids([r.user_id for r in reqs])
    return [
        _serialize_with_username(
            r, users[r.user_id].username if r.user_id in users else None
        )
        for r in reqs
    ]


@router.post("/{request_id}/resolve")
async def resolve_request(
    request_id: int,
    body: ResolveBody,
    identity: SessionIdentity = Depends(get_current_identity),
) -> dict[str, object]:
    registry = get_registry()
    try:
        req = await registry.get_access_request(request_id)
    except AccessRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Request not found") from exc

    try:
        policy = await registry.get_policy(req.code)
    except MountNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mount not found") from exc

    is_owner = (
        policy.owner_user_id is not None
        and policy.owner_user_id == identity.user_id
    )
    if not (is_owner or is_admin_username(identity.username)):
        raise HTTPException(
            status_code=403, detail="Only the mount owner or an admin may resolve"
        )

    if body.action is ResolveAction.APPROVE:
        role = body.role if body.role is not None else Role.READ
        await registry.add_policy_entry(
            req.code, SubjectType.USER, req.user_id, role
        )
        await registry.resolve_access_request(
            request_id, AccessRequestStatus.APPROVED
        )
        return {"id": request_id, "status": "approved", "role": role.value}

    await registry.resolve_access_request(request_id, AccessRequestStatus.DENIED)
    return {"id": request_id, "status": "denied"}
