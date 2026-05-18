"""Admin-only user/group/membership management.

Every route is gated by :func:`require_admin`. Admins are configured via
``RELAY_ADMIN_USERS`` (relay config); users self-register but cannot manage
groups.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from accounts import (
    DuplicateMembershipError,
    GroupCycleError,
    GroupNameTakenError,
    GroupNotFoundError,
    MembershipNotFoundError,
    SubjectType,
    UserNotFoundError,
)
from relay.app.dependencies import require_admin
from relay.app.services.account_store import get_account_store

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class SetActiveRequest(BaseModel):
    is_active: bool


class CreateGroupRequest(BaseModel):
    name: str


class AddMemberRequest(BaseModel):
    member_type: SubjectType
    member_ref: str  # username (USER) or group name (GROUP)


class RemoveMemberRequest(BaseModel):
    member_type: SubjectType
    member_id: int


# --- Users -----------------------------------------------------------------


@router.get("/users")
async def list_users() -> list[dict[str, object]]:
    store = get_account_store()
    users = await store.list_users()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/users/{user_id}/active")
async def set_user_active(user_id: int, body: SetActiveRequest) -> dict[str, object]:
    store = get_account_store()
    try:
        await store.set_user_active(user_id, body.is_active)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    return {"user_id": user_id, "is_active": body.is_active}


# --- Groups ----------------------------------------------------------------


@router.get("/groups")
async def list_groups() -> list[dict[str, object]]:
    store = get_account_store()
    groups = await store.list_groups()
    return [
        {"id": g.id, "name": g.name, "created_at": g.created_at} for g in groups
    ]


@router.post("/groups")
async def create_group(body: CreateGroupRequest) -> dict[str, object]:
    store = get_account_store()
    try:
        group = await store.create_group(body.name)
    except GroupNameTakenError as exc:
        raise HTTPException(status_code=409, detail="Group name already taken") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": group.id, "name": group.name}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int) -> dict[str, object]:
    store = get_account_store()
    try:
        await store.delete_group(group_id)
    except GroupNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Group not found") from exc
    return {"status": "ok"}


# --- Memberships -----------------------------------------------------------


@router.get("/groups/{group_id}/members")
async def list_group_members(group_id: int) -> list[dict[str, object]]:
    store = get_account_store()
    try:
        members = await store.list_group_members(group_id)
    except GroupNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Group not found") from exc
    return [
        {"member_type": m.member_type.value, "member_id": m.member_id}
        for m in members
    ]


async def _resolve_member_id(member_type: SubjectType, member_ref: str) -> int:
    """Resolve a username/group-name to its id. Raises 404 if unknown."""
    store = get_account_store()
    try:
        if member_type is SubjectType.USER:
            return (await store.get_user_by_username(member_ref)).id
        return (await store.get_group_by_name(member_ref)).id
    except (UserNotFoundError, GroupNotFoundError) as exc:
        raise HTTPException(
            status_code=404, detail=f"{member_type.value} {member_ref!r} not found"
        ) from exc


@router.post("/groups/{group_id}/members")
async def add_group_member(
    group_id: int, body: AddMemberRequest
) -> dict[str, object]:
    store = get_account_store()
    member_id = await _resolve_member_id(body.member_type, body.member_ref)
    try:
        await store.add_member(group_id, body.member_type, member_id)
    except GroupNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Group not found") from exc
    except GroupCycleError as exc:
        raise HTTPException(
            status_code=409, detail="Membership would create a group cycle"
        ) from exc
    except DuplicateMembershipError as exc:
        raise HTTPException(
            status_code=409, detail="Membership already exists"
        ) from exc
    return {
        "group_id": group_id,
        "member_type": body.member_type.value,
        "member_id": member_id,
    }


@router.delete("/groups/{group_id}/members")
async def remove_group_member(
    group_id: int, body: RemoveMemberRequest
) -> dict[str, object]:
    store = get_account_store()
    try:
        await store.remove_member(group_id, body.member_type, body.member_id)
    except MembershipNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Membership not found") from exc
    return {"status": "ok"}
