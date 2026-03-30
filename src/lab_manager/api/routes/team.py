"""Team management endpoints: invite, list, update role, deactivate."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import ROLE_LEVELS, get_permissions, require_permission
from lab_manager.api.deps import get_db
from lab_manager.api.pagination import paginate
from lab_manager.api.validation import is_valid_email_address
from lab_manager.config import get_settings
from lab_manager.models.invitation import Invitation
from lab_manager.models.staff import Staff

logger = logging.getLogger(__name__)

router = APIRouter()

# Invitation tokens expire after 7 days (seconds).
_INVITE_MAX_AGE = 7 * 24 * 3600


def _get_invite_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    if not settings.admin_secret_key:
        raise RuntimeError("ADMIN_SECRET_KEY must be set")
    return URLSafeTimedSerializer(settings.admin_secret_key, salt="lab-invite")


# ---------------------------------------------------------------------------
# List members
# ---------------------------------------------------------------------------


@router.get("/")
def list_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = Query(None),
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """List all team members."""
    q = select(Staff).order_by(Staff.role_level.asc(), Staff.name.asc())
    if is_active is not None:
        q = q.where(Staff.is_active == is_active)
    return paginate(q, db, page, page_size)


# ---------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------


@router.post("/invite")
def create_invitation(
    email: str = Body(...),
    name: str = Body(...),
    role: str = Body("grad_student"),
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """Create an invitation for a new team member."""
    email = email.strip().lower()
    name = name.strip()

    if not name or len(name) > 200:
        raise HTTPException(
            status_code=422, detail="Name must be between 1 and 200 characters"
        )
    if not is_valid_email_address(email):
        raise HTTPException(status_code=422, detail="Invalid email address")
    if role not in ROLE_LEVELS:
        raise HTTPException(status_code=422, detail=f"Invalid role: {role}")

    # Cannot invite at a higher level than own
    caller_level = staff.get("role_level", 99)
    target_level = ROLE_LEVELS[role]
    if target_level < caller_level:
        raise HTTPException(
            status_code=403,
            detail="Cannot invite a member at a role above your own level",
        )

    # Check if email already has an active staff account
    existing = db.scalars(
        select(Staff).where(Staff.email == email, Staff.is_active.is_(True))
    ).first()
    if existing:
        raise HTTPException(
            status_code=409, detail="A user with this email already exists"
        )

    # Check for pending invitation
    pending = db.scalars(
        select(Invitation).where(
            Invitation.email == email, Invitation.status == "pending"
        )
    ).first()
    if pending:
        raise HTTPException(
            status_code=409,
            detail="A pending invitation already exists for this email",
        )

    # Generate signed token
    serializer = _get_invite_serializer()
    token_data = {"email": email, "role": role, "nonce": secrets.token_hex(8)}
    token = serializer.dumps(token_data)

    import datetime as _dt

    invitation = Invitation(
        email=email,
        name=name,
        role=role,
        token=token,
        invited_by=staff.get("id"),
        status="pending",
        expires_at=datetime.now(timezone.utc) + _dt.timedelta(seconds=_INVITE_MAX_AGE),
    )
    db.add(invitation)
    db.flush()
    db.refresh(invitation)

    logger.info(
        "Invitation created: email=%s role=%s by staff_id=%s",
        email,
        role,
        staff.get("id"),
    )
    return {
        "id": invitation.id,
        "email": invitation.email,
        "name": invitation.name,
        "role": invitation.role,
        "status": invitation.status,
        "created_at": invitation.created_at.isoformat()
        if invitation.created_at
        else None,
        "expires_at": invitation.expires_at.isoformat()
        if invitation.expires_at
        else None,
    }


# ---------------------------------------------------------------------------
# List pending invitations
# ---------------------------------------------------------------------------


@router.get("/invitations/")
def list_invitations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """List all invitations (pending by default)."""
    q = select(Invitation).order_by(Invitation.created_at.desc())
    return paginate(q, db, page, page_size)


# ---------------------------------------------------------------------------
# Cancel invitation
# ---------------------------------------------------------------------------


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(
    invitation_id: int,
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """Cancel a pending invitation."""
    invitation = db.get(Invitation, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "pending":
        raise HTTPException(
            status_code=400, detail="Only pending invitations can be cancelled"
        )
    invitation.status = "cancelled"
    db.flush()
    logger.info(
        "Invitation cancelled: id=%s by staff_id=%s",
        invitation_id,
        staff.get("id"),
    )
    return {"status": "ok", "message": "Invitation cancelled"}


# ---------------------------------------------------------------------------
# Member detail
# ---------------------------------------------------------------------------


@router.get("/{member_id}")
def get_member(
    member_id: int,
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """Get a single team member."""
    member = db.get(Staff, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    perms = get_permissions(member.role)
    return {
        "id": member.id,
        "name": member.name,
        "email": member.email,
        "role": member.role,
        "role_level": member.role_level,
        "is_active": member.is_active,
        "last_login_at": member.last_login_at.isoformat()
        if member.last_login_at
        else None,
        "access_expires_at": (
            member.access_expires_at.isoformat() if member.access_expires_at else None
        ),
        "invited_by": member.invited_by,
        "permissions": sorted(perms),
    }


# ---------------------------------------------------------------------------
# Update role
# ---------------------------------------------------------------------------


@router.patch("/{member_id}")
def update_member(
    member_id: int,
    role: str = Body(..., embed=True),
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """Update a member's role. Cannot promote above own level."""
    if role not in ROLE_LEVELS:
        raise HTTPException(status_code=422, detail=f"Invalid role: {role}")

    member = db.get(Staff, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    caller_level = staff.get("role_level", 99)
    target_level = ROLE_LEVELS[role]

    # Cannot promote someone to a level higher (numerically lower) than own
    if target_level < caller_level:
        raise HTTPException(
            status_code=403,
            detail="Cannot promote a member above your own role level",
        )

    # Cannot change a member who is at a higher level than caller
    member_level = ROLE_LEVELS.get(member.role, 99)
    if member_level < caller_level:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify a member with a higher role than yours",
        )

    member.role = role
    member.role_level = target_level
    db.flush()
    db.refresh(member)
    logger.info(
        "Role updated: staff_id=%s -> role=%s by staff_id=%s",
        member_id,
        role,
        staff.get("id"),
    )
    return {
        "id": member.id,
        "name": member.name,
        "email": member.email,
        "role": member.role,
        "role_level": member.role_level,
        "is_active": member.is_active,
    }


# ---------------------------------------------------------------------------
# Deactivate member
# ---------------------------------------------------------------------------


@router.delete("/{member_id}")
def deactivate_member(
    member_id: int,
    staff=Depends(require_permission("manage_users")),
    db: Session = Depends(get_db),
):
    """Deactivate (soft-delete) a team member. Cannot deactivate self."""
    if member_id == staff.get("id"):
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    member = db.get(Staff, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot deactivate a member with higher privilege
    caller_level = staff.get("role_level", 99)
    member_level = ROLE_LEVELS.get(member.role, 99)
    if member_level < caller_level:
        raise HTTPException(
            status_code=403,
            detail="Cannot deactivate a member with a higher role than yours",
        )

    member.is_active = False
    db.flush()
    logger.info(
        "Member deactivated: staff_id=%s by staff_id=%s",
        member_id,
        staff.get("id"),
    )
    return {"status": "ok", "message": f"Member {member.name} deactivated"}


# ---------------------------------------------------------------------------
# Accept invitation (public — no auth required)
# ---------------------------------------------------------------------------


@router.post("/join/{token}")
def accept_invitation(
    token: str,
    password: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Accept an invitation and create an account. No auth required."""
    if len(password) < 8:
        raise HTTPException(
            status_code=422, detail="Password must be at least 8 characters"
        )
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=422, detail="Password must be 72 bytes or fewer"
        )

    # Verify token signature and age
    serializer = _get_invite_serializer()
    try:
        data = serializer.loads(token, max_age=_INVITE_MAX_AGE)
    except BadSignature:
        raise HTTPException(
            status_code=400, detail="Invalid or expired invitation token"
        )

    email = data.get("email", "")
    role = data.get("role", "grad_student")

    # Find the matching pending invitation with a row lock to prevent
    # TOCTOU races when two concurrent requests use the same token.
    invitation = db.scalars(
        select(Invitation)
        .where(Invitation.token == token, Invitation.status == "pending")
        .with_for_update()
    ).first()
    if not invitation:
        raise HTTPException(
            status_code=400, detail="Invitation not found or already used"
        )

    # Check if email already taken by active staff (also under row lock)
    existing = db.scalars(
        select(Staff)
        .where(Staff.email == email, Staff.is_active.is_(True))
        .with_for_update()
    ).first()
    if existing:
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        )

    # Create or reactivate staff record
    staff = db.scalars(select(Staff).where(Staff.email == email)).first()
    if staff:
        staff.name = invitation.name
        staff.role = role
        staff.role_level = ROLE_LEVELS.get(role, 4)
        staff.is_active = True
        staff.invited_by = invitation.invited_by
    else:
        staff = Staff(
            name=invitation.name,
            email=email,
            role=role,
            role_level=ROLE_LEVELS.get(role, 4),
            is_active=True,
            invited_by=invitation.invited_by,
        )
        db.add(staff)

    staff.password_hash = _bcrypt.hashpw(
        password.encode("utf-8"), _bcrypt.gensalt()
    ).decode("utf-8")

    # Mark invitation as accepted
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)

    db.flush()
    db.refresh(staff)

    logger.info(
        "Invitation accepted: email=%s staff_id=%s role=%s",
        email,
        staff.id,
        role,
    )
    return {
        "status": "ok",
        "message": "Account created successfully. You can now sign in.",
        "user": {
            "id": staff.id,
            "name": staff.name,
            "email": staff.email,
            "role": staff.role,
        },
    }
