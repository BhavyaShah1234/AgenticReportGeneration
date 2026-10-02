"""FastAPI dependencies: `current_user`, `require_designer`."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.security import COOKIE_NAME, decode_token
from app.db import get_session
from app.models import User


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    data = decode_token(token) if token else None
    if not data or data.get("purpose") != "session":
        raise HTTPException(401, "Not authenticated")
    user = session.get(User, data.get("sub"))
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user


def require_designer(user: User = Depends(current_user)) -> User:
    if user.role != "designer":
        raise HTTPException(403, "Only designers can do this")
    return user
